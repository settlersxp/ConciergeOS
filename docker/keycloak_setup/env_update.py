#!/usr/bin/env python3
"""Environment file updates for Keycloak setup.

Handles updating .env files with client secrets.
"""

import os


# ------------------------------------------------------------------
# Environment File Management
# ------------------------------------------------------------------


def _find_env_file() -> str | None:
    """Find the docker .env file.

    Searches:
    1. Same directory as this script
    2. Parent directory (project root .env)
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, ".env"),
        os.path.join(script_dir, "..", ".env"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)
    return None


def _update_env_file(env_path: str, secret: str) -> None:
    """Update OIDC_CLIENT_SECRET in the .env file in place."""
    try:
        with open(env_path, "r") as f:
            lines = f.readlines()

        new_lines: list[str] = []
        updated = False
        for line in lines:
            if line.startswith("OIDC_CLIENT_SECRET="):
                new_lines.append(f"OIDC_CLIENT_SECRET={secret}\n")
                updated = True
            else:
                new_lines.append(line)

        if not updated:
            # Append if not found
            new_lines.append(f"\n# -- OIDC --\nOIDC_CLIENT_SECRET={secret}\n")

        with open(env_path, "w") as f:
            f.writelines(new_lines)

        print(f"  ✓ Updated OIDC_CLIENT_SECRET in {env_path}")
    except OSError as e:
        print(f"  ⚠ Failed to update {env_path}: {e}")


def _update_env_file_client_api(env_path: str, secret: str) -> None:
    """Update CLIENT_API_CLIENT_SECRET in the .env file in place."""
    try:
        with open(env_path, "r") as f:
            lines = f.readlines()

        new_lines: list[str] = []
        updated = False
        for line in lines:
            if line.startswith("CLIENT_API_CLIENT_SECRET="):
                new_lines.append(f"CLIENT_API_CLIENT_SECRET={secret}\n")
                updated = True
            else:
                new_lines.append(line)

        if not updated:
            # Ensure previous line ends with newline before appending
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"
            new_lines.append(f"CLIENT_API_CLIENT_SECRET={secret}\n")

        with open(env_path, "w") as f:
            f.writelines(new_lines)

        print(f"  ✓ Updated CLIENT_API_CLIENT_SECRET in {env_path}")
    except OSError as e:
        print(f"  ⚠ Failed to update {env_path}: {e}")


def update_oidc_configs(actual_secret: str, client_api_secret: str) -> None:
    """Print and automatically update the Keycloak client secrets in .env files.

    Updates both OIDC_CLIENT_SECRET (for oauth2-proxy) and
    CLIENT_API_CLIENT_SECRET (for the client-backend service).
    """
    print(f"  ✓ concierge client secret: {actual_secret}")
    print(f"  ✓ client-api client secret: {client_api_secret}")

    # Auto-update .env files
    env_path = _find_env_file()
    if env_path:
        _update_env_file(env_path, actual_secret)
        _update_env_file_client_api(env_path, client_api_secret)
    else:
        print("  ⚠ No .env file found. Set secrets manually.")