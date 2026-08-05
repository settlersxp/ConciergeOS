"""Event Polling module for Keycloak admin events.

Handles polling Keycloak's Admin Events API to detect role-related changes,
user deletions, and session invalidations.
"""

import logging
from datetime import datetime, timedelta, timezone

from keycloak_common import has_events, kc_request
from .config import KEYCLOAK_REALM, ROLE_EVENT_TYPES, SESSION_EVENT_TYPES, USER_EVENT_TYPES

logger = logging.getLogger(__name__)


def poll_admin_events(token: str, since: datetime) -> list[dict]:
    """Poll Keycloak admin events since the given timestamp.

    Keycloak 26 has two separate endpoints:
    - /events: Returns user events (LOGIN, LOGOUT, CODE_TO_TOKEN, etc.) with 'type' field
    - /admin-events: Returns admin events (role/user/session CRUD) with 'operationType'/'resourceType'

    We use /admin-events for detecting role changes, user deletions, and session invalidations.

    Args:
        token: Admin access token
        since: Datetime to poll events from

    Returns:
        List of admin event dictionaries
    """
    date_from = since.strftime("%Y-%m-%d")
    date_to = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

    resp = kc_request(
        "GET",
        f"/admin/realms/{KEYCLOAK_REALM}/admin-events",
        token,
        params={"dateFrom": date_from, "dateTo": date_to},
    )
    resp.raise_for_status()
    return resp.json()


def has_role_events(events: list[dict]) -> bool:
    """Check if any event is a role-related admin event.

    Args:
        events: List of admin events to check

    Returns:
        True if any role-related events are found
    """
    return has_events(events, {"ROLE", "REALM_ROLE", "CLIENT_ROLE"}, set(ROLE_EVENT_TYPES))


def has_user_delete_events(events: list[dict]) -> bool:
    """Check if any event is a user DELETE or USER_SESSION DELETE event.

    Args:
        events: List of admin events to check

    Returns:
        True if any user deletion events are found
    """
    user_deleted = has_events(events, {"USER"}, set(USER_EVENT_TYPES))
    session_deleted = has_events(events, {"USER_SESSION"}, set(SESSION_EVENT_TYPES))

    for event in events:
        event_id = event.get("id", "unknown")
        realm = event.get("realmId", "unknown")
        user_id = event.get("userId", "")
        op = event.get("operationType", "")
        rt = event.get("resourceType", "")

        if rt == "USER" and op in USER_EVENT_TYPES:
            logger.info(
                "USER DELETE event detected: eventId=%s, userId=%s, realm=%s",
                event_id, user_id, realm
            )
        elif rt == "USER_SESSION" and op in SESSION_EVENT_TYPES:
            logger.info(
                "USER_SESSION DELETE event detected: eventId=%s, userId=%s, realm=%s",
                event_id, user_id, realm
            )

    return user_deleted or session_deleted