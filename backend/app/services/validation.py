"""LLM-based validation service for performance testing."""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a strict validation engine. Your job is to compare ground-truth guest "
    "information (provided as JSON) against an LLM-generated text response and determine "
    "whether the response correctly contains **all** of the guest's information.\n\n"
    "You must check EVERY field in the ground truth:\n"
    "1. **Guest fields**: guest_id, first_name, last_name, date_of_birth, "
    "is_special_guest, special_preferences\n"
    "2. **Each reservation**: reservation_id, room_id, room_name, check_in_date, "
    "check_out_date, status, booking_source\n\n"
    "Rules:\n"
    "- is_match = true ONLY if the LLM response contains correct information for ALL "
    "ground-truth fields and ALL reservations.\n"
    "- If the response lists the correct guest among several candidates but does not "
    "include full reservation details for that guest, is_match = false.\n"
    "- If any reservation from the ground truth is missing from the response, "
    "is_match = false.\n"
    "- If any field value differs between ground truth and response, is_match = false.\n"
    "- If the response is empty or clearly unrelated, is_match = false.\n\n"
    "Respond with a JSON object having two fields:\n"
    "- 'is_match' (boolean)\n"
    "- 'reasoning' (string) — list every field that is missing or incorrect, "
    "and which reservations are missing."
)


def validate_single_pair(
    ground_truth_json: str,
    ground_truth_name: str,
    response_content: str | None,
    use_cache: bool = True,
) -> tuple[bool | None, str | None, bool]:
    """Validate a single guest-response pair using the LLM.

    Compares the full ground-truth JSON against the LLM response field-by-field.
    Uses response caching to avoid redundant LLM calls for repeated validations.

    Args:
        ground_truth_json: JSON string of ground-truth guest data.
        ground_truth_name: Guest full name used as validation identifier.
        response_content: The LLM response to validate.
        use_cache: If True, check/use response cache for this validation.

    Returns:
        A tuple of (is_match, llm_reasoning, was_cached).
        is_match is True/False on success, None on error.
        was_cached is True if the result was served from cache.
    """
    from app.services.response_cache import (
        _get_cache,
        generate_cache_key,
    )

    user_prompt = (
        f"Ground-truth guest name: {ground_truth_name}\n\n"
        f"Ground-truth JSON:\n{ground_truth_json}\n\n"
        f"LLM response to validate:\n{response_content or '(empty response)'}\n\n"
        "Compare the LLM response against the ground-truth JSON field by field. "
        "Return your answer as a JSON object with 'is_match' (boolean) and "
        "'reasoning' (string)."
    )

    # Generate cache key from the validation inputs (system prompt + user prompt)
    cache_input = f"{SYSTEM_PROMPT}\n\n{user_prompt}"
    cache_key = generate_cache_key(cache_input)

    logger.info(
        f"[VALIDATE] Starting validation for guest '{ground_truth_name}' | "
        f"cache_key={cache_key[:12]}... | use_cache={use_cache}"
    )

    # Check cache first if enabled
    if use_cache:
        cached_entry = _get_cache().get(cache_key)
        if cached_entry is not None:
            logger.info(
                f"[VALIDATE] [CACHE] HIT for '{ground_truth_name}' | "
                f"response_len={len(cached_entry.response)}"
            )
            try:
                parsed = json.loads(cached_entry.response)
                is_match = parsed.get("is_match")
                reasoning = parsed.get("reasoning", "")
                return is_match, reasoning, True
            except (json.JSONDecodeError, AttributeError):
                logger.warning(
                    f"[VALIDATE] Cached response for '{ground_truth_name}' is malformed, "
                    f"falling back to LLM call"
                )

    logger.info(f"[VALIDATE] [CACHE] MISS for '{ground_truth_name}' | calling LLM")

    # Call LLM using the cached implementation
    try:
        from app.services.llm import get_llm_config

        client, model = get_llm_config()

        from openai import OpenAI

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        answer = resp.choices[0].message.content or "{}"

        parsed = json.loads(answer)
        is_match = parsed.get("is_match")
        reasoning = parsed.get("reasoning", "")

        # Store in cache if enabled
        if use_cache:
            _get_cache().set(cache_key, answer)
            logger.info(
                f"[VALIDATE] [CACHE] STORED for '{ground_truth_name}' | "
                f"is_match={is_match}"
            )

        return is_match, reasoning, False
    except Exception as e:
        logger.error(
            f"[VALIDATE] Error validating '{ground_truth_name}': {e}",
            exc_info=True,
        )
        return None, f"Validation error: {e}", False