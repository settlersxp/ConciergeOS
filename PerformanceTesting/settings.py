"""Configuration settings and constants for performance testing."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Constants ────────────────────────────────────────────────────────────────

_DEFAULT_MODEL = "Qwen/Qwen3.6-27B"
_DEFAULT_MAX_TOKENS = 4096
_TOOL_CALL_MAX_TOKENS = 1024
_DEFAULT_TEMPERATURE = 0
_TOOL_CALL_TEMPERATURE = 0.1
_MAX_TOOL_TURNS = 10
_MODELS_ENDPOINT = "http://localhost:8000/v1/models"
_API_KEY_PLACEHOLDER = "sk-placeholder"  # Dummy API key for vLLM (not validated)
_MODEL_INFO_TIMEOUT = 10  # Seconds to wait for /v1/models response

_BATCH_TYPE_SEQUENTIAL = "sequential"
_BATCH_TYPE_CONCURRENT = "concurrent"


# ── TestSettings ─────────────────────────────────────────────────────────────


@dataclass
class TestSettings:
    """All configurable settings for a performance test run."""
    customer_name: str = "عائشة إبراهيم"
    vllm_url: str = ""  # Derived from models_endpoint if not provided
    models_endpoint: str = _MODELS_ENDPOINT
    database_path: Path = field(
        default_factory=lambda: Path(__file__).parent.parent.parent / "database.db"
    )
    sequential_batch_size: int = 5
    concurrent_batch_size: int = 8
    # Test mode: "single" (one guest for all tests) or "multi" (different guest per test)
    test_mode: str = "single"
    # Guest names for multi-guest mode (first N for sequential, remaining for concurrent)
    guest_names: list[str] = field(default_factory=list)
    # Batch identification
    batch_uuid: str = ""
    friendly_name: str = ""
    # Model metadata (auto-filled from vLLM API, but editable by user)
    model_name: str = ""
    vllm_version: str = ""
    thinking_enabled: bool = False
    # Prompt settings
    system_prompt: str = ""  # Set externally from app.services.llm
    user_prompt: str = ""  # If-empty, auto-built from customer_name + DB data
    # Response format expectation
    expected_response_format: str = "auto"  # "json", "text", or "auto"
    # Data format: which file format to embed in the user prompt
    data_format: str = "csv"  # "csv", "json", "xml", or "tool_calling"
    # Tool calling support
    use_tool_calling: bool = False  # Whether to use function/tool calling instead of embedding data
    tool_definitions: list[dict[str, Any]] = field(default_factory=list)  # Tool definitions to send to LLM
    # Runtime variables for {table.field} placeholders in user_prompt templates
    runtime_variables: dict[str, str] = field(default_factory=dict)
    # Prompt versioning support (used to call query_guest_with_llm with prompt resolution)
    prompt_id: str = ""  # e.g., "guest-search"
    prompt_version: int | None = None  # e.g., 1, None for latest
    # Response cache toggle
    response_cache_enabled: bool = True

    def resolve_vllm_url(self) -> str:
        """Return the configured vLLM URL, falling back to models_endpoint base."""
        if self.vllm_url:
            return self.vllm_url
        # Derive from models_endpoint by stripping /v1/models
        endpoint = self.models_endpoint.rstrip("/")
        if endpoint.endswith("/v1/models"):
            return endpoint[:-len("/v1/models")] or endpoint
        return endpoint


# ── Exported constants for external use ──────────────────────────────────────

DEFAULT_MODEL = _DEFAULT_MODEL
DEFAULT_MAX_TOKENS = _DEFAULT_MAX_TOKENS
TOOL_CALL_MAX_TOKENS = _TOOL_CALL_MAX_TOKENS
DEFAULT_TEMPERATURE = _DEFAULT_TEMPERATURE
TOOL_CALL_TEMPERATURE = _TOOL_CALL_TEMPERATURE
MAX_TOOL_TURNS = _MAX_TOOL_TURNS
API_KEY_PLACEHOLDER = _API_KEY_PLACEHOLDER
MODEL_INFO_TIMEOUT = _MODEL_INFO_TIMEOUT
BATCH_TYPE_SEQUENTIAL = _BATCH_TYPE_SEQUENTIAL
BATCH_TYPE_CONCURRENT = _BATCH_TYPE_CONCURRENT
