#!/usr/bin/env python3
"""Keycloak event helpers.

Provides URL constants and utilities for interacting with the Keycloak
Admin Events API.
"""

from keycloak_common import kc_request

# ------------------------------------------------------------------
# URL Constants
# ------------------------------------------------------------------

EVENTS_URL = "/admin/realms/{realm}/events"


# ------------------------------------------------------------------
# Event Helpers
# ------------------------------------------------------------------


def fetch_events_with_params(
    token: str,
    realm: str,
    params: dict,
) -> "Response":  # type: ignore[return]
    """Fetch realm events with custom query parameters.

    Returns the raw Response object (not parsed JSON) so callers can
    inspect status codes — useful for tests that assert on 4xx/5xx errors.

    Args:
        token: Keycloak admin token
        realm: Realm name
        params: Query parameters to pass to the events endpoint

    Returns:
        Raw requests.Response object
    """
    return kc_request(
        "GET",
        EVENTS_URL.format(realm=realm),
        token,
        params=params,
    )


def get_realm_events(
    token: str,
    realm: str,
    date_from: str,
    date_to: str,
) -> list[dict]:
    """Fetch realm admin events for a date range.

    Args:
        token: Keycloak admin token
        realm: Realm name
        date_from: Date in yyyy-MM-dd format
        date_to: Date in yyyy-MM-dd format

    Returns:
        List of event dictionaries
    """
    resp = kc_request(
        "GET",
        EVENTS_URL.format(realm=realm),
        token,
        params={"dateFrom": date_from, "dateTo": date_to},
    )
    resp.raise_for_status()
    return resp.json()
