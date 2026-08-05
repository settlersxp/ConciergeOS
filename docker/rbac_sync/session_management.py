"""Session Management module for Valkey session invalidation.

Handles session invalidation via Valkey and event persistence
for tracking sync state and processed events.
"""

import logging
import time

import valkey

from .config import SESSION_KEY_PREFIX, VALKEY_URL

logger = logging.getLogger(__name__)

# Event persistence keys
_CHECKPOINT_KEY = "role_sync:sync_ts"
_SEEN_KEY = "role_sync:seen"


def _get_valkey_client():
    """Return a Valkey client or None if unreachable.

    Returns:
        Valkey client instance or None
    """
    try:
        r = valkey.from_url(VALKEY_URL)
        r.ping()
        return r
    except Exception as e:
        logger.debug("Valkey unreachable: %s", e)
        return None


def invalidate_all_sessions() -> int:
    """Delete all oauth2-proxy sessions from Valkey.

    Returns:
        Number of session keys deleted
    """
    logger.info(
        "Starting session invalidation from Valkey (URL: %s, pattern: %s*)",
        VALKEY_URL, SESSION_KEY_PREFIX
    )

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

    while True:
        cursor, keys = r.scan(cursor=cursor, match=pattern, count=batch_size)
        if keys:
            del_count = r.delete(*keys)
            deleted += del_count
            logger.info("  Deleted %d session key(s)", del_count)
        if cursor == 0:
            break

    logger.info(
        "Session invalidation complete: %d total session(s) deleted from Valkey",
        deleted
    )
    return deleted


def load_sync_timestamp() -> float | None:
    """Return the last-sync UNIX timestamp, or None.

    Returns:
        UNIX timestamp of last successful sync, or None
    """
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
    """True if a successful sync happened within the last 2xSYNC_INTERVAL.

    Returns:
        True if sync is considered current, False otherwise
    """
    from .config import SYNC_INTERVAL

    ts = load_sync_timestamp()
    if ts is None:
        return False
    age = time.time() - ts
    ok = age < SYNC_INTERVAL * 2
    if not ok:
        logger.info(
            "Last sync was %.0fs ago (threshold %ds) - routes may be stale",
            age, SYNC_INTERVAL * 2
        )
    return ok


def load_seen_ids() -> set[str]:
    """Load today's set of already-processed event IDs.

    Returns:
        Set of event IDs that have been processed
    """
    r = _get_valkey_client()
    if r is None:
        return set()
    raw = r.smembers(_SEEN_KEY)
    if not raw:
        return set()
    return {m.decode("utf-8") for m in raw}


def save_seen_ids(ids: set[str]) -> None:
    """Replace today's seen set.

    Args:
        ids: Set of event IDs to mark as seen
    """
    if not ids:
        return
    r = _get_valkey_client()
    if r is None:
        return
    r.delete(_SEEN_KEY)
    r.sadd(_SEEN_KEY, *ids)
    logger.debug("Stored %d seen event ID(s)", len(ids))


def filter_new_events(events: list[dict], seen: set[str]) -> list[dict]:
    """Return only events whose IDs are not in *seen*.

    Args:
        events: List of events to filter
        seen: Set of already-processed event IDs

    Returns:
        List of new (unprocessed) events
    """
    new: list[dict] = []
    for evt in events:
        evt_id = evt.get("id", "")
        if evt_id and evt_id in seen:
            continue
        new.append(evt)
    return new


def collect_event_ids(events: list[dict]) -> set[str]:
    """Extract every event ID from a list of events.

    Args:
        events: List of event dictionaries

    Returns:
        Set of event IDs
    """
    return {evt["id"] for evt in events if evt.get("id")}