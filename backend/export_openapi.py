#!/usr/bin/env python3
"""
Export the FastAPI OpenAPI JSON specification.

Usage:
    uv run python backend/export_openapi.py
    uv run python backend/export_openapi.py output.json
"""

import json
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent))

from app.main import app


def export_openapi(output_path: str = "backend/openapi.json") -> None:
    """Export the FastAPI OpenAPI spec to a JSON file."""
    spec = app.openapi()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(spec, indent=2))
    print(f"OpenAPI spec exported to {output.absolute()}")
    print(f"Total endpoints: {len(_count_endpoints(spec))}")


def _count_endpoints(spec: dict) -> dict:
    """Count endpoints by method from the OpenAPI spec."""
    endpoints = {}
    for path, methods in spec.get("paths", {}).items():
        for method in methods:
            if method in ("get", "post", "put", "patch", "delete", "options", "head"):
                endpoints[method.upper()] = endpoints.get(method.upper(), 0) + 1
    return endpoints


if __name__ == "__main__":
    output = sys.argv[1] if len(sys.argv) > 1 else "backend/openapi.json"
    export_openapi(output)