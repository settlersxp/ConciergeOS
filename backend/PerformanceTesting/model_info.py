"""Model metadata retrieval from vLLM /v1/models endpoint."""

from __future__ import annotations

from typing import Any

import requests

from .settings import API_KEY_PLACEHOLDER, MODEL_INFO_TIMEOUT


# ── Model info retrieval ────────────────────────────────────────────────────


def fetch_model_info(url: str) -> dict[str, Any]:
    """Fetch loaded model information from the vLLM /v1/models endpoint."""
    resp = requests.get(url, timeout=MODEL_INFO_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    models: list[dict[str, Any]] = data.get("data", [])
    if not models:
        return {"model_name": "unknown", "vllm_version": "unknown", "thinking_enabled": False}

    model: dict[str, Any] = models[0]
    model_name: str = str(model.get("id", model.get("model", "unknown")))

    # Try to extract vllm version from various possible fields
    vllm_version: str = str(model.get("vllm_version", ""))
    if not vllm_version or vllm_version == "None":
        extra = model.get("extra")
        if isinstance(extra, dict):
            vllm_version = str(extra.get("vllm_version", "unknown"))
        else:
            vllm_version = "unknown"

    # Check if thinking is enabled
    thinking_enabled: bool = False
    capabilities = model.get("capabilities")
    if isinstance(capabilities, dict):
        thinking_enabled = bool(capabilities.get("thinking", False))

    model_type = str(model.get("type", "")).lower()
    if "thinking" in model_type:
        thinking_enabled = True

    return {
        "model_name": model_name,
        "vllm_version": vllm_version,
        "thinking_enabled": thinking_enabled,
    }


# ── OpenAI client factory ───────────────────────────────────────────────────


def create_openai_client(base_url: str) -> Any:
    """Lazy-import and create an OpenAI client."""
    from openai import OpenAI
    return OpenAI(base_url=base_url, api_key=API_KEY_PLACEHOLDER)
