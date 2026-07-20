#!/usr/bin/env python3
"""
Utility functions for normalizing LLM endpoint URLs.

Provides helpers to ensure consistent /v1/models endpoint formatting
across the codebase, eliminating URL normalization duplication.
"""


def normalize_models_endpoint(raw_url: str) -> str:
    """Normalize a URL to end with /v1/models.

    - If already ending with /v1/models -> use as-is
    - If ending with /v1 -> append /models
    - Otherwise -> append /v1/models

    Args:
        raw_url: Raw endpoint URL string (may be empty)

    Returns:
        Normalized URL ending with /v1/models

    Examples:
        >>> normalize_models_endpoint("http://localhost:8000")
        'http://localhost:8000/v1/models'
        >>> normalize_models_endpoint("http://localhost:8000/v1")
        'http://localhost:8000/v1/models'
        >>> normalize_models_endpoint("http://localhost:8000/v1/models")
        'http://localhost:8000/v1/models'
        >>> normalize_models_endpoint("http://localhost:8000/v1/models/")
        'http://localhost:8000/v1/models'
    """
    url = raw_url.strip().rstrip("/")
    if not url:
        return url

    if url.endswith("/v1/models"):
        return url
    if url.endswith("/v1"):
        return f"{url}/models"
    return f"{url}/v1/models"


