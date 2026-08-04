"""Sync Orchestrator module for RBAC role synchronization.

Contains the main sync logic that orchestrates polling, role synchronization,
and Caddy route updates.
"""

import logging
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

from keycloak_common import authenticate, fetch_all_roles_with_attrs
from .config import (
    KEYCLOAK_URL,
    KEYCLOAK_REALM,
    CADDY_ADMIN_URL,
    SYNC_INTERVAL,
    RBAC_ROUTES_FILE,
)
from .event_polling import (
    poll_admin_events,
    has_role_events,
    has_user_delete_events,
)
from .session_management import (
    invalidate_all_sessions,
    load_seen_ids,
    save_seen_ids,
    collect_event_ids,
    filter_new_events,
    save_sync_timestamp,
    sync_is_current,
)
from .caddy_routes import generate_deny_rules, build_caddy_routes, push_routes_to_caddy
from .routes_persistence import sync_rbac_routes

logger = logging.getLogger(__name__)


def initial_sync() -> bool:
    """Perform initial full sync on startup.

    Returns:
        True if successful, False otherwise
    """
    if sync_is_current():
        logger.info("Initial Sync: Last sync is current - skipping full re-sync")
        return True

    logger.info("=" * 60)
    logger.info("Initial Sync: Building routes from Keycloak role attributes")
    logger.info("=" * 60)

    try:
        token = authenticate()
        logger.debug("Keycloak admin authentication successful")
    except Exception as e:
        logger.error("Failed to authenticate to Keycloak: %s", e, exc_info=True)
        return False

    roles_with_attrs = fetch_all_roles_with_attrs(token)
    available_roles = set(roles_with_attrs.keys())
    logger.info(
        "Found %d role(s) in realm '%s': %s",
        len(available_roles), KEYCLOAK_REALM, sorted(available_roles)
    )

    deny_rules = generate_deny_rules(roles_with_attrs)
    logger.info("Generated %d deny rule(s)", len(deny_rules))

    routes = build_caddy_routes(deny_rules)
    logger.debug("Built %d total route(s) for Caddy", len(routes))

    if push_routes_to_caddy(routes):
        logger.info("Initial sync complete!")

        # Also write to file for persistence
        if sync_rbac_routes(token, RBAC_ROUTES_FILE):
            logger.info("Sync complete!")
        else:
            logger.warning("Sync failed - routes pushed to Caddy but not persisted to file")

        save_sync_timestamp()
        return True
    else:
        logger.error("Initial sync failed!")
        return False


def poll_and_sync() -> bool:
    """Poll Keycloak for role changes and sync if needed.

    Returns:
        True if successful, False otherwise
    """
    logger.debug("- Poll cycle started -")

    try:
        token = authenticate()
        logger.debug("Keycloak admin authentication successful for poll cycle")
    except Exception as e:
        logger.error("Failed to authenticate to Keycloak during poll: %s", e, exc_info=True)
        return False

    since = datetime.now(timezone.utc)
    since_offset = since - timedelta(seconds=SYNC_INTERVAL)
    logger.debug(
        "Polling admin events from %s to %s",
        since_offset.strftime("%Y-%m-%dT%H:%M:%S"),
        since.strftime("%Y-%m-%dT%H:%M:%S")
    )

    seen = load_seen_ids()
    logger.debug("Loaded %d seen event ID(s) from Valkey", len(seen))

    try:
        events = poll_admin_events(token, since_offset)
        logger.debug("Fetched %d admin event(s) from Keycloak", len(events))

        new_events = filter_new_events(events, seen)
        logger.debug("New (unprocessed) event(s): %d / %d total", len(new_events), len(events))

        for evt in new_events:
            logger.debug(
                "  [NEW] Event[id=%s, op=%s, resource=%s, realm=%s, user=%s]",
                evt.get("id", "?"),
                evt.get("operationType", "?"),
                evt.get("resourceType", "?"),
                evt.get("realmId", "?"),
                evt.get("userId", "?")
            )
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

    roles_with_attrs = fetch_all_roles_with_attrs(token)
    available_roles = set(roles_with_attrs.keys())
    logger.info("Current roles in Keycloak: %s", sorted(available_roles))

    deny_rules = generate_deny_rules(roles_with_attrs)
    routes = build_caddy_routes(deny_rules)

    if push_routes_to_caddy(routes):
        logger.info("Incremental sync complete!")

        # Also write to file for persistence
        if sync_rbac_routes(token, RBAC_ROUTES_FILE):
            logger.info("Sync complete!")
        else:
            logger.warning("Sync failed - routes pushed to Caddy but not persisted to file")

        save_sync_timestamp()
        return True
    else:
        logger.error("Incremental sync failed!")
        return False


def wait_for_dependencies(max_retries: int = 60, retry_delay: int = 2) -> bool:
    """Wait for Keycloak and Caddy to be ready.

    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Seconds between retries

    Returns:
        True if both dependencies are ready, False otherwise
    """
    logger.info("Waiting for Keycloak and Caddy to be ready...")

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
                logger.debug(
                    "Caddy not reachable yet (attempt %d/%d): %s",
                    attempt + 1, max_retries, e
                )

        if not keycloak_ready:
            try:
                resp = requests.get(f"{KEYCLOAK_URL}/realms/master", timeout=3)
                if resp.status_code == 200:
                    logger.info("Keycloak is ready (HTTP 200)")
                    keycloak_ready = True
            except requests.RequestException as e:
                logger.debug(
                    "Keycloak not reachable yet (attempt %d/%d): %s",
                    attempt + 1, max_retries, e
                )

        if caddy_ready and keycloak_ready:
            break

        if attempt % 5 == 0 and attempt > 0:
            logger.info(
                "Still waiting for dependencies... (attempt %d/%d, caddy=%s, keycloak=%s)",
                attempt + 1, max_retries, caddy_ready, keycloak_ready
            )

        time.sleep(retry_delay)

    if not caddy_ready:
        logger.error("Caddy admin API did not become ready in time (%d attempts)", max_retries)
    if not keycloak_ready:
        logger.error("Keycloak did not become ready in time (%d attempts)", max_retries)

    return caddy_ready and keycloak_ready


def run_sync_service() -> None:
    """Main entry point for the sync service."""
    logger.info("=" * 60)
    logger.info("Role Sync Service for ConciergeOS RBAC")
    logger.info("=" * 60)
    logger.info("Keycloak URL:     %s", KEYCLOAK_URL)
    logger.info("Keycloak Realm:   %s", KEYCLOAK_REALM)
    logger.info("Caddy Admin URL:  %s", CADDY_ADMIN_URL)
    logger.info("Sync Interval:    %ds", SYNC_INTERVAL)

    if not wait_for_dependencies():
        logger.error("Startup aborted: dependencies did not become ready")
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