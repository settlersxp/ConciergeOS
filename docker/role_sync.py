#!/usr/bin/env python3
"""Role Sync Service for ConciergeOS RBAC.

Polls Keycloak's Admin Events API to detect role-related changes,
then regenerates Caddy deny rules from the role-to-path mapping file
and pushes them via the Caddy Admin API.

Environment Variables (see docker/settings.py for defaults):
    KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_ADMIN_USER, KEYCLOAK_ADMIN_PASSWORD
    CADDY_ADMIN_URL, SYNC_INTERVAL, MAPPING_FILE, VALKEY_URL, SESSION_COOKIE_NAME
"""

import logging
import os
import sys
import time

from datetime import datetime, timedelta, timezone

import requests
import valkey
import yaml

from settings import settings

# ------------------------------------------------------------------
# Logging Configuration
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    stream=sys.stdout,
    force=True,
)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

logger = logging.getLogger("role_sync")


# ------------------------------------------------------------------
# Configuration (loaded from shared settings module)
# ------------------------------------------------------------------
KEYCLOAK_URL = settings.KEYCLOAK_URL
KEYCLOAK_REALM = settings.KEYCLOAK_REALM
KEYCLOAK_ADMIN_USER = settings.KEYCLOAK_ADMIN_USER
KEYCLOAK_ADMIN_PASSWORD = settings.KEYCLOAK_ADMIN_PASSWORD
CADDY_ADMIN_URL = settings.CADDY_ADMIN_URL
SYNC_INTERVAL = settings.SYNC_INTERVAL
MAPPING_FILE = settings.MAPPING_FILE
VALKEY_URL = settings.VALKEY_URL
SESSION_COOKIE_NAME = settings.SESSION_COOKIE_NAME

# Admin events we care about
ROLE_EVENT_TYPES = ["CREATE", "UPDATE", "DELETE"]
USER_EVENT_TYPES = ["DELETE"]
SESSION_EVENT_TYPES = ["DELETE"]

SESSION_KEY_PREFIX = SESSION_COOKIE_NAME + "-"  # e.g., "_oauth2_proxy-"


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

    Keycloak 26 has two separate endpoints:
    - /events: Returns user events (LOGIN, LOGOUT, CODE_TO_TOKEN, etc.) with 'type' field
    - /admin-events: Returns admin events (role/user/session CRUD) with 'operationType'/'resourceType'

    We use /admin-events for detecting role changes, user deletions, and session invalidations.
    """
    date_from = since.strftime("%Y-%m-%d")
    date_to = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

    resp = requests.get(
        f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}/admin-events",
        params={
            "dateFrom": date_from,
            "dateTo": date_to,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


def has_role_events(events: list[dict]) -> bool:
    """Check if any event is a role-related admin event."""
    for event in events:
        operation = event.get("operationType", "")
        resource_type = event.get("resourceType", "")
        logger.debug("  Checking event: resourceType=%s, operationType=%s", resource_type, operation)
        if resource_type in ("ROLE", "REALM_ROLE", "CLIENT_ROLE") and operation in ROLE_EVENT_TYPES:
            logger.debug("  → Role event MATCHED: %s %s", operation, resource_type)
            return True
    logger.debug("  → No role events found in %d event(s)", len(events))
    return False


def has_user_delete_events(events: list[dict]) -> bool:
    """Check if any event is a user DELETE or USER_SESSION DELETE event."""
    found = False
    for event in events:
        operation_type = event.get("operationType", "")
        resource_type = event.get("resourceType", "")
        event_id = event.get("id", "unknown")
        realm = event.get("realmId", "unknown")
        userId = event.get("userId", "")

        if resource_type == "USER" and operation_type in USER_EVENT_TYPES:
            logger.info("USER DELETE event detected: eventId=%s, userId=%s, realm=%s", event_id, userId, realm)
            found = True
        if resource_type == "USER_SESSION" and operation_type in SESSION_EVENT_TYPES:
            logger.info("USER_SESSION DELETE event detected: eventId=%s, userId=%s, realm=%s", event_id, userId, realm)
            found = True
    if not found:
        logger.debug("No user/session delete events found in %d event(s)", len(events))
    return found


# ------------------------------------------------------------------
# Valkey Session Invalidation
# ------------------------------------------------------------------


def invalidate_all_sessions() -> int:
    """Delete all oauth2-proxy sessions from Valkey."""
    logger.info("Starting session invalidation from Valkey (URL: %s, pattern: %s*)", VALKEY_URL, SESSION_KEY_PREFIX)

    try:
        r = valkey.from_url(VALKEY_URL)
        r.ping()
        logger.debug("Valkey connection established (PING OK)")
    except Exception as e:
        logger.warning("Cannot connect to Valkey (%s): %s", VALKEY_URL, e)
        return 0

    deleted = 0
    cursor = 0
    batch_size = 100
    pattern = f"{SESSION_KEY_PREFIX}*"
    scan_iter = 0

    while True:
        scan_iter += 1
        cursor, keys = r.scan(cursor=cursor, match=pattern, count=batch_size)
        logger.debug("Valkey SCAN iter=%d cursor=%d keys_found=%d", scan_iter, cursor, len(keys))
        if keys:
            key_names = [k.decode("utf-8", errors="replace") for k in keys]
            logger.debug("  Keys to delete: %s", key_names)
            del_count = r.delete(*keys)
            deleted += del_count
            logger.info("  Deleted %d session key(s): %s", del_count, key_names)
        if cursor == 0:
            break

    logger.info("Session invalidation complete: %d total session(s) deleted from Valkey", deleted)
    return deleted


# ------------------------------------------------------------------
# Event Persistence (Valkey-backed)
# ------------------------------------------------------------------

_CHECKPOINT_KEY = "role_sync:sync_ts"
_SEEN_KEY = "role_sync:seen"


def _get_valkey_client():
    """Return a Valkey client or None if unreachable."""
    try:
        r = valkey.from_url(VALKEY_URL)
        r.ping()
        return r
    except Exception as e:
        logger.debug("Valkey unreachable: %s", e)
        return None


def load_sync_timestamp() -> float | None:
    """Return the last-sync UNIX timestamp, or None."""
    r = _get_valkey_client()
    if r is None:
        return None
    raw = r.get(_CHECKPOINT_KEY)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def save_sync_timestamp() -> None:
    """Record that a successful sync just completed."""
    r = _get_valkey_client()
    if r is None:
        return
    r.set(_CHECKPOINT_KEY, str(time.time()))


def sync_is_current() -> bool:
    """True if a successful sync happened within the last 2×SYNC_INTERVAL."""
    ts = load_sync_timestamp()
    if ts is None:
        return False
    age = time.time() - ts
    ok = age < SYNC_INTERVAL * 2
    if not ok:
        logger.info("Last sync was %.0fs ago (threshold %ds) — routes may be stale", age, SYNC_INTERVAL * 2)
    return ok


def load_seen_ids() -> set[str]:
    """Load today's set of already-processed event IDs."""
    r = _get_valkey_client()
    if r is None:
        return set()
    raw = r.smembers(_SEEN_KEY)
    if not raw:
        return set()
    return {m.decode("utf-8") for m in raw}


def save_seen_ids(ids: set[str]) -> None:
    """Replace today's seen set."""
    if not ids:
        return
    r = _get_valkey_client()
    if r is None:
        return
    r.delete(_SEEN_KEY)
    r.sadd(_SEEN_KEY, *ids)
    logger.debug("Stored %d seen event ID(s)", len(ids))


def filter_new_events(events: list[dict], seen: set[str]) -> list[dict]:
    """Return only events whose IDs are not in *seen*."""
    new: list[dict] = []
    for evt in events:
        evt_id = evt.get("id", "")
        if evt_id and evt_id in seen:
            logger.debug("Skipping already-seen event: %s", evt_id)
            continue
        new.append(evt)
    return new


def collect_event_ids(events: list[dict]) -> set[str]:
    """Extract every event ID from a list of events."""
    return {evt["id"] for evt in events if evt.get("id")}


# ------------------------------------------------------------------
# Mapping File
# ------------------------------------------------------------------


def load_mapping() -> list[dict]:
    """Load the role-to-path mapping YAML file."""
    if not os.path.exists(MAPPING_FILE):
        logger.warning("Mapping file not found: %s", MAPPING_FILE)
        return []

    with open(MAPPING_FILE, "r") as f:
        data = yaml.safe_load(f)

    if not data:
        logger.debug("Mapping file %s is empty", MAPPING_FILE)
        return []

    logger.debug("Loaded %d mapping entry/entries from %s", len(data), MAPPING_FILE)
    return data


# ------------------------------------------------------------------
# Caddy Route Generation
# ------------------------------------------------------------------


def generate_deny_rules(mapping: list[dict], available_roles: set[str]) -> list[dict]:
    """Generate Caddy deny rules from the mapping file."""
    deny_rules = []

    for entry in mapping:
        role_name = entry.get("role", "")
        paths = entry.get("paths", [])
        message = entry.get("message", f"Access denied: this resource requires the {role_name} role.")

        if not role_name or not paths:
            continue

        if role_name not in available_roles:
            logger.warning("Role '%s' in mapping file does not exist in Keycloak. Skipping.", role_name)
            continue

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
        logger.info("Generated deny rule for role '%s' on %d path(s): %s", role_name, len(paths), paths)

    return deny_rules


def build_caddy_routes(deny_rules: list[dict]) -> list[dict]:
    """Build the full internal-server routes array."""
    static_assets_route = {
        "handle": [
            {
                "handler": "reverse_proxy",
                "upstreams": [{"dial": "frontend:80"}],
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

    full_access_bypass_route = {
        "handle": [
            {
                "handler": "reverse_proxy",
                "upstreams": [{"dial": "frontend:80"}],
            }
        ],
        "match": [
            {
                "header_regexp": {
                    "X-Forwarded-Groups": {
                        "pattern": ".*role:full-access.*"
                    }
                }
            }
        ],
        "terminal": True,
    }

    catch_all_route = {
        "handle": [
            {
                "handler": "reverse_proxy",
                "upstreams": [{"dial": "frontend:80"}],
            }
        ],
    }

    return [static_assets_route, full_access_bypass_route] + deny_rules + [catch_all_route]


# ------------------------------------------------------------------
# Caddy Admin API
# ------------------------------------------------------------------


def push_routes_to_caddy(routes: list[dict]) -> bool:
    """Push the updated routes to Caddy via the Admin API."""
    resp = requests.get(
        f"{CADDY_ADMIN_URL}/config/",
        headers={"Content-Type": "application/json"},
    )
    if resp.status_code != 200:
        logger.error("Failed to fetch current Caddy config: HTTP %d, response: %s", resp.status_code, resp.text)
        return False

    full_config = resp.json()
    logger.debug("Fetched current Caddy config from %s", CADDY_ADMIN_URL)

    apps = full_config.setdefault("apps", {})
    http_app = apps.setdefault("http", {})
    servers = http_app.setdefault("servers", {})
    internal = servers.setdefault("internal-server", {})
    internal["routes"] = routes

    resp = requests.patch(
        f"{CADDY_ADMIN_URL}/config",
        json=full_config,
        headers={"Content-Type": "application/json"},
    )

    if resp.status_code == 200:
        logger.info("Routes pushed to Caddy successfully (%d total routes)", len(routes))
        return True
    else:
        logger.error("Failed to push routes to Caddy: HTTP %d, response: %s", resp.status_code, resp.text)
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
    """Perform initial full sync on startup."""
    if sync_is_current():
        logger.info("Initial Sync: Last sync is current — skipping full re-sync")
        return True

    logger.info("=" * 60)
    logger.info("Initial Sync: Building routes from scratch")
    logger.info("=" * 60)

    try:
        token = authenticate_keycloak()
        logger.debug("Keycloak admin authentication successful")
    except Exception as e:
        logger.error("Failed to authenticate to Keycloak: %s", e, exc_info=True)
        return False

    available_roles = fetch_all_roles(token)
    logger.info("Found %d role(s) in realm '%s': %s", len(available_roles), KEYCLOAK_REALM, sorted(available_roles))

    mapping = load_mapping()
    logger.info("Loaded %d role-to-path mapping(s) from %s", len(mapping), MAPPING_FILE)

    deny_rules = generate_deny_rules(mapping, available_roles)
    logger.info("Generated %d deny rule(s)", len(deny_rules))

    routes = build_caddy_routes(deny_rules)
    logger.debug("Built %d total route(s) for Caddy", len(routes))

    if push_routes_to_caddy(routes):
        logger.info("Initial sync complete!")
        save_sync_timestamp()
        return True
    else:
        logger.error("Initial sync failed!")
        return False


def poll_and_sync() -> bool:
    """Poll Keycloak for role changes and sync if needed."""
    logger.debug("— Poll cycle started —")

    try:
        token = authenticate_keycloak()
        logger.debug("Keycloak admin authentication successful for poll cycle")
    except Exception as e:
        logger.error("Failed to authenticate to Keycloak during poll: %s", e, exc_info=True)
        return False

    since = datetime.now(timezone.utc)
    since_offset = since - timedelta(seconds=SYNC_INTERVAL)
    logger.debug("Polling admin events from %s to %s", since_offset.strftime("%Y-%m-%dT%H:%M:%S"), since.strftime("%Y-%m-%dT%H:%M:%S"))

    seen = load_seen_ids()
    logger.debug("Loaded %d seen event ID(s) from Valkey", len(seen))

    try:
        events = poll_admin_events(token, since_offset)
        logger.debug("Fetched %d admin event(s) from Keycloak", len(events))

        new_events = filter_new_events(events, seen)
        logger.debug("New (unprocessed) event(s): %d / %d total", len(new_events), len(events))

        for evt in new_events:
            logger.debug("  [NEW] Event[id=%s, op=%s, resource=%s, realm=%s, user=%s]",
                         evt.get("id", "?"),
                         evt.get("operationType", "?"),
                         evt.get("resourceType", "?"),
                         evt.get("realmId", "?"),
                         evt.get("userId", "?"))
    except Exception as e:
        logger.error("Failed to poll admin events: %s", e, exc_info=True)
        return False

    all_ids = collect_event_ids(events) | seen
    save_seen_ids(all_ids)

    if not new_events:
        logger.debug("Poll cycle complete: no new events")
        save_sync_timestamp()
        return True

    if has_user_delete_events(new_events):
        logger.info("User/session deletion detected! Invalidating all sessions from Valkey...")
        invalidated = invalidate_all_sessions()
        if invalidated > 0:
            logger.info("Session invalidation complete: %d session(s) removed", invalidated)
        else:
            logger.info("No active sessions found in Valkey to invalidate.")

    if not has_role_events(new_events):
        logger.debug("Poll cycle complete: no role changes detected")
        save_sync_timestamp()
        return True

    logger.info("Role change detected! Regenerating Caddy routes...")

    available_roles = fetch_all_roles(token)
    logger.info("Current roles in Keycloak: %s", sorted(available_roles))

    mapping = load_mapping()
    deny_rules = generate_deny_rules(mapping, available_roles)
    routes = build_caddy_routes(deny_rules)

    if push_routes_to_caddy(routes):
        logger.info("Incremental sync complete!")
        save_sync_timestamp()
        return True
    else:
        logger.error("Incremental sync failed!")
        return False


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main() -> None:
    logger.info("=" * 60)
    logger.info("Role Sync Service for ConciergeOS RBAC")
    logger.info("=" * 60)
    logger.info("Keycloak URL:     %s", KEYCLOAK_URL)
    logger.info("Keycloak Realm:   %s", KEYCLOAK_REALM)
    logger.info("Caddy Admin URL:  %s", CADDY_ADMIN_URL)
    logger.info("Sync Interval:    %ds", SYNC_INTERVAL)
    logger.info("Mapping File:     %s", MAPPING_FILE)
    logger.info("Valkey URL:       %s", VALKEY_URL)
    logger.info("Session Key Prefix: %s", SESSION_KEY_PREFIX)

    logger.info("Waiting for Keycloak and Caddy to be ready...")
    max_retries = 60
    retry_delay = 2
    caddy_ready = False
    keycloak_ready = False

    for attempt in range(max_retries):
        if not caddy_ready:
            try:
                resp = requests.get(f"{CADDY_ADMIN_URL}/config", timeout=3)
                if resp.status_code == 200:
                    logger.info("Caddy admin API is ready (HTTP 200)")
                    caddy_ready = True
            except requests.RequestException as e:
                logger.debug("Caddy not reachable yet (attempt %d/%d): %s", attempt + 1, max_retries, e)

        if not keycloak_ready:
            try:
                resp = requests.get(f"{KEYCLOAK_URL}/realms/master", timeout=3)
                if resp.status_code == 200:
                    logger.info("Keycloak is ready (HTTP 200)")
                    keycloak_ready = True
            except requests.RequestException as e:
                logger.debug("Keycloak not reachable yet (attempt %d/%d): %s", attempt + 1, max_retries, e)

        if caddy_ready and keycloak_ready:
            break

        if attempt % 5 == 0 and attempt > 0:
            logger.info("Still waiting for dependencies... (attempt %d/%d, caddy=%s, keycloak=%s)",
                        attempt + 1, max_retries, caddy_ready, keycloak_ready)

        time.sleep(retry_delay)
    else:
        errors = []
        if not caddy_ready:
            logger.error("Caddy admin API did not become ready in time (%d attempts)", max_retries)
            errors.append("caddy")
        if not keycloak_ready:
            logger.error("Keycloak did not become ready in time (%d attempts)", max_retries)
            errors.append("keycloak")
        logger.error("Startup aborted: %s did not become ready", ", ".join(errors))
        sys.exit(1)

    logger.info("All dependencies ready, proceeding with initial sync")

    if not initial_sync():
        logger.warning("Initial sync failed. Will retry on next poll cycle.")

    logger.info("=" * 60)
    logger.info("Entering polling loop (interval: %ds)", SYNC_INTERVAL)
    logger.info("=" * 60)

    while True:
        time.sleep(SYNC_INTERVAL)

        try:
            poll_and_sync()
        except Exception as e:
            logger.error("Exception during poll cycle: %s", e, exc_info=True)
            logger.warning("Retrying on next cycle...")


if __name__ == "__main__":
    main()