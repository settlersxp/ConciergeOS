#!/usr/bin/env python3
"""Role Sync Service for ConciergeOS RBAC.

Polls Keycloak's Admin Events API to detect role-related changes,
then regenerates Caddy deny rules from the role-to-path mapping file
and pushes them via the Caddy Admin API.

Environment Variables:
    KEYCLOAK_URL         - Keycloak server URL (e.g., http://keycloak:8080)
    KEYCLOAK_REALM       - Realm to monitor (default: production)
    KEYCLOAK_ADMIN_USER  - Admin username for Keycloak API
    KEYCLOAK_ADMIN_PASSWORD - Admin password for Keycloak API
    CADDY_ADMIN_URL      - Caddy Admin API URL (default: http://caddy:2019)
    SYNC_INTERVAL        - Polling interval in seconds (default: 30)
    MAPPING_FILE         - Path to role-to-path mapping YAML file
"""

import os
import sys
import time

# Disable stdout buffering so logs appear immediately in Docker
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True)

from datetime import datetime, timedelta, timezone

import requests
import yaml


# ------------------------------------------------------------------
# Configuration from environment
# ------------------------------------------------------------------

KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://keycloak:8080/auth")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "production")
KEYCLOAK_ADMIN_USER = os.environ.get("KEYCLOAK_ADMIN_USER", "admin")
KEYCLOAK_ADMIN_PASSWORD = os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "admin")
CADDY_ADMIN_URL = os.environ.get("CADDY_ADMIN_URL", "http://caddy:2019")
SYNC_INTERVAL = int(os.environ.get("SYNC_INTERVAL", "30"))
MAPPING_FILE = os.environ.get("MAPPING_FILE", "/app/rbac_routes.yaml")

# Admin events we care about
ROLE_EVENT_TYPES = ["CREATE", "UPDATE", "DELETE"]


# ------------------------------------------------------------------
# Keycloak API Helpers
# ------------------------------------------------------------------


def authenticate_keycloak() -> str:
    """Authenticate as admin to the master realm and return access token."""
    resp = requests.post(
        f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": KEYCLOAK_ADMIN_USER,
            "password": KEYCLOAK_ADMIN_PASSWORD,
        },
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("Failed to authenticate to Keycloak admin.")
    return token


def fetch_all_roles(token: str) -> set[str]:
    """Fetch all role names in the configured realm."""
    resp = requests.get(
        f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}/roles",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return {role["name"] for role in resp.json()}


def poll_admin_events(token: str, since: datetime) -> list[dict]:
    """Poll Keycloak admin events since the given timestamp.

    Note: Keycloak 26 does NOT accept 'type=ADMIN' as a valid EventType enum value.
    The /admin/realms/{realm}/events endpoint returns both user and admin events.
    We filter admin events by their 'resourceType' field in the response.
    """
    # Keycloak 26 expects dates in yyyy-MM-dd format (not milliseconds).
    date_from = since.strftime("%Y-%m-%d")
    date_to = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Do NOT pass type=ADMIN — it causes IllegalArgumentException in Keycloak 26.
    # The endpoint returns all events; we filter client-side by resourceType.
    resp = requests.get(
        f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}/events",
        params={
            "dateFrom": date_from,
            "dateTo": date_to,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    all_events = resp.json()

    # Filter to admin-only events: admin events have operationType but no userId/clientId
    # (they are performed by the admin console, not end users)
    admin_events = [
        e for e in all_events
        if e.get("resourceType") in ("ROLE", "CLIENT", "REALM", "USER", "GROUP", "IDENTITY_PROVIDER", "SCOPE")
        or e.get("operationType") in ("CREATE", "UPDATE", "DELETE", "LOGIN", "VIEW")
        and "authServer" in str(e.get("representation", "")).lower()
        or e.get("resourceType") == "ROLE"
    ]

    # Return all events; has_role_events() will further filter for ROLE events
    return all_events


def has_role_events(events: list[dict]) -> bool:
    """Check if any event is a role-related admin event."""
    for event in events:
        operation = event.get("operationType", "")
        resource_type = event.get("resourceType", "")
        if resource_type == "ROLE" and operation in ROLE_EVENT_TYPES:
            return True
    return False


# ------------------------------------------------------------------
# Mapping File
# ------------------------------------------------------------------


def load_mapping() -> list[dict]:
    """Load the role-to-path mapping YAML file."""
    if not os.path.exists(MAPPING_FILE):
        print(f"WARNING: Mapping file not found: {MAPPING_FILE}")
        return []

    with open(MAPPING_FILE, "r") as f:
        data = yaml.safe_load(f)

    if not data:
        return []

    return data


# ------------------------------------------------------------------
# Caddy Route Generation
# ------------------------------------------------------------------


def generate_deny_rules(mapping: list[dict], available_roles: set[str]) -> list[dict]:
    """Generate Caddy deny rules from the mapping file.

    Only generates rules for roles that exist in both the mapping file
    and Keycloak. Logs warnings for mismatches.
    """
    deny_rules = []

    for entry in mapping:
        role_name = entry.get("role", "")
        paths = entry.get("paths", [])
        message = entry.get("message", f"Access denied: this resource requires the {role_name} role.")

        if not role_name or not paths:
            continue

        if role_name not in available_roles:
            print(f"  WARNING: Role '{role_name}' in mapping file does not exist in Keycloak. Skipping.")
            continue

        # Generate deny rule: deny access unless user has the matching role
        rule = {
            "handle": [
                {
                    "handler": "static_response",
                    "status_code": "403",
                    "body": message,
                }
            ],
            "match": [
                {
                    "path": paths,
                    "not": [
                        {
                            "header_regexp": {
                                "X-Forwarded-Groups": {
                                    "pattern": f".*role:{role_name}.*"
                                }
                            }
                        }
                    ],
                }
            ],
            "terminal": True,
        }
        deny_rules.append(rule)
        print(f"  ✓ Generated deny rule for role '{role_name}' on {len(paths)} path(s)")

    return deny_rules


def build_caddy_routes(deny_rules: list[dict]) -> list[dict]:
    """Build the full internal-server routes array.

    Order:
      1. Static assets (always allowed)
      2. Deny rules (from mapping)
      3. Catch-all proxy to frontend
    """
    # Static assets route (always first)
    static_assets_route = {
        "handle": [
            {
                "handler": "reverse_proxy",
                "upstreams": [
                    {
                        "dial": "frontend:80"
                    }
                ],
            }
        ],
        "match": [
            {
                "path": [
                    "/assets/*",
                    "/favicon.svg",
                    "/icons.svg",
                    "/vite.svg",
                    "/react.svg",
                    "/hero.png",
                    "/*.css",
                    "/*.js",
                    "/*.map",
                    "/*.svg",
                    "/*.png",
                    "/*.jpg",
                    "/*.gif",
                    "/*.ico",
                    "/*.woff",
                    "/*.woff2",
                    "/*.ttf",
                    "/*.eot",
                ]
            }
        ],
        "terminal": True,
    }

    # Catch-all proxy (always last)
    catch_all_route = {
        "handle": [
            {
                "handler": "reverse_proxy",
                "upstreams": [
                    {
                        "dial": "frontend:80"
                    }
                ],
            }
        ],
    }

    return [static_assets_route] + deny_rules + [catch_all_route]


# ------------------------------------------------------------------
# Caddy Admin API
# ------------------------------------------------------------------


def push_routes_to_caddy(routes: list[dict]) -> bool:
    """Push the updated routes to Caddy via the Admin API."""
    # Build the full config patch: only update the internal-server routes
    config_patch = {
        "apps": {
            "http": {
                "servers": {
                    "internal-server": {
                        "routes": routes,
                    }
                }
            }
        }
    }

    resp = requests.patch(
        f"{CADDY_ADMIN_URL}/config",
        json=config_patch,
        headers={"Content-Type": "application/json"},
    )

    if resp.status_code == 200:
        print(f"  ✓ Routes pushed to Caddy ({len(routes)} total routes)")
        return True
    else:
        print(f"  ERROR: Failed to push routes to Caddy: HTTP {resp.status_code}")
        print(f"  Response: {resp.text}")
        return False


def verify_caddy_routes() -> list[dict]:
    """Read current routes from Caddy for verification/debugging."""
    resp = requests.get(
        f"{CADDY_ADMIN_URL}/config/apps/http/servers/internal-server/routes"
    )
    if resp.status_code == 200:
        return resp.json()
    return []


# ------------------------------------------------------------------
# Sync Logic
# ------------------------------------------------------------------


def initial_sync() -> bool:
    """Perform initial full sync on startup.

    Fetches all roles from Keycloak, loads mapping file, generates routes,
    and pushes to Caddy. This ensures idempotent behavior on restart.
    """
    print("=" * 60)
    print("Initial Sync: Building routes from scratch")
    print("=" * 60)

    try:
        token = authenticate_keycloak()
    except Exception as e:
        print(f"  ERROR: Failed to authenticate to Keycloak: {e}")
        return False

    # Fetch all roles from Keycloak
    available_roles = fetch_all_roles(token)
    print(f"  Found {len(available_roles)} roles in realm '{KEYCLOAK_REALM}':")
    for role in sorted(available_roles):
        print(f"    - {role}")

    # Load mapping file
    mapping = load_mapping()
    print(f"  Loaded {len(mapping)} role-to-path mappings from {MAPPING_FILE}")

    # Generate deny rules
    deny_rules = generate_deny_rules(mapping, available_roles)
    print(f"  Generated {len(deny_rules)} deny rules")

    # Build full routes
    routes = build_caddy_routes(deny_rules)

    # Push to Caddy
    if push_routes_to_caddy(routes):
        print("  ✓ Initial sync complete!\n")
        return True
    else:
        print("  ✗ Initial sync failed.\n")
        return False


def poll_and_sync() -> bool:
    """Poll Keycloak for role changes and sync if needed."""
    try:
        token = authenticate_keycloak()
    except Exception as e:
        print(f"  ERROR: Failed to authenticate to Keycloak: {e}")
        return False

    # Calculate "since" as SYNC_INTERVAL seconds ago
    since = datetime.now(timezone.utc)

    # Poll admin events
    try:
        events = poll_admin_events(token, since - timedelta(seconds=SYNC_INTERVAL))
    except Exception as e:
        print(f"  ERROR: Failed to poll admin events: {e}")
        return False

    if not has_role_events(events):
        return True  # No role changes, nothing to do

    # Role events detected — perform full re-sync
    print("  → Role change detected! Regenerating routes...")

    available_roles = fetch_all_roles(token)
    mapping = load_mapping()
    deny_rules = generate_deny_rules(mapping, available_roles)
    routes = build_caddy_routes(deny_rules)

    if push_routes_to_caddy(routes):
        print("  ✓ Incremental sync complete!")
        return True
    else:
        print("  ✗ Incremental sync failed.")
        return False


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main() -> None:
    print("=" * 60)
    print("Role Sync Service for ConciergeOS RBAC")
    print("=" * 60)
    print(f"  Keycloak URL:     {KEYCLOAK_URL}")
    print(f"  Keycloak Realm:   {KEYCLOAK_REALM}")
    print(f"  Caddy Admin URL:  {CADDY_ADMIN_URL}")
    print(f"  Sync Interval:    {SYNC_INTERVAL}s")
    print(f"  Mapping File:     {MAPPING_FILE}")
    print()

    # Wait for Keycloak and Caddy to be ready
    print("Waiting for Keycloak and Caddy to be ready...")
    max_retries = 30
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            # Check if Caddy admin API is reachable
            resp = requests.get(f"{CADDY_ADMIN_URL}/config", timeout=3)
            if resp.status_code == 200:
                print("  ✓ Caddy admin API is ready")
                break
        except requests.RequestException:
            pass

        if attempt % 5 == 0 and attempt > 0:
            print(f"  Waiting... (attempt {attempt + 1}/{max_retries})")

        time.sleep(retry_delay)
    else:
        print("  ERROR: Caddy admin API did not become ready in time.")
        sys.exit(1)

    # Perform initial sync
    if not initial_sync():
        print("  WARNING: Initial sync failed. Will retry on next poll cycle.")
        print()

    # Enter polling loop
    print("=" * 60)
    print(f"Entering polling loop (interval: {SYNC_INTERVAL}s)")
    print("=" * 60)
    print()

    while True:
        time.sleep(SYNC_INTERVAL)

        try:
            poll_and_sync()
        except Exception as e:
            print(f"  ERROR during poll cycle: {e}")
            print("  Retrying on next cycle...")


if __name__ == "__main__":
    main()