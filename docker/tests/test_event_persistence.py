#!/usr/bin/env python3
"""
test_event_persistence.py - Tests for the Valkey-backed event persistence layer.

Tests filter_new_events, save/load sync timestamp, sync_is_current,
save/load seen IDs, and collect_event_ids.

Uses the LIVE Valkey container for persistence tests and pure-function tests
for filter_new_events / collect_event_ids logic.
"""

import os
import sys
import time

import pytest
import valkey

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import role_sync


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture()
def _valkey_flush():
    """Flush all role_sync:* keys from Valkey before and after each test.

    Gracefully skips if Valkey is unavailable (e.g., Docker not running).
    Only use this fixture on tests that actually touch Valkey.
    """
    r = valkey.from_url(role_sync.VALKEY_URL)
    try:
        r.ping()
    except Exception:
        # Valkey unavailable — skip flush (tests that require Valkey
        # will fail at the assertion level with a clearer message).
        yield
        return

    # Flush before
    cursor = 0
    while True:
        cursor, keys = r.scan(cursor=cursor, match="role_sync:*", count=100)
        if keys:
            r.delete(*keys)
        if cursor == 0:
            break
    yield
    # Flush after
    cursor = 0
    while True:
        cursor, keys = r.scan(cursor=cursor, match="role_sync:*", count=100)
        if keys:
            r.delete(*keys)
        if cursor == 0:
            break


@pytest.fixture
def sample_events():
    """Return a list of mock Keycloak admin events."""
    return [
        {"id": "evt-001", "operationType": "CREATE", "resourceType": "REALM_ROLE"},
        {"id": "evt-002", "operationType": "UPDATE", "resourceType": "ROLE"},
        {"id": "evt-003", "operationType": "LOGIN", "resourceType": "USER"},
    ]


# ======================================================================
# TestSyncTimestamp (checkpoint)
# ======================================================================


class TestSyncTimestamp:

    def test_save_and_load(self, _valkey_flush):
        role_sync.save_sync_timestamp()
        ts = role_sync.load_sync_timestamp()
        assert ts is not None
        assert isinstance(ts, float)
        assert ts <= time.time()

    def test_load_none_when_empty(self, monkeypatch):
        monkeypatch.setattr(role_sync, "_CHECKPOINT_KEY", "role_sync:__none__")
        assert role_sync.load_sync_timestamp() is None

    def test_sync_is_current_after_save(self, _valkey_flush):
        role_sync.save_sync_timestamp()
        assert role_sync.sync_is_current() is True

    def test_sync_is_current_stale(self, monkeypatch, _valkey_flush):
        role_sync.save_sync_timestamp()
        stale_ts = time.time() - (role_sync.SYNC_INTERVAL * 3)
        monkeypatch.setattr(role_sync, "load_sync_timestamp", lambda: stale_ts)
        assert role_sync.sync_is_current() is False

    def test_sync_is_current_no_checkpoint(self, monkeypatch):
        monkeypatch.setattr(role_sync, "load_sync_timestamp", lambda: None)
        assert role_sync.sync_is_current() is False

    def test_survives_overwrite(self, _valkey_flush):
        role_sync.save_sync_timestamp()
        ts1 = role_sync.load_sync_timestamp()
        time.sleep(0.05)
        role_sync.save_sync_timestamp()
        ts2 = role_sync.load_sync_timestamp()
        assert ts2 >= ts1


# ======================================================================
# TestSeenIds
# ======================================================================


class TestSeenIds:

    def test_save_and_load(self, _valkey_flush):
        ids = {"a", "b", "c"}
        role_sync.save_seen_ids(ids)
        assert role_sync.load_seen_ids() == ids

    def test_load_empty_when_none(self, _valkey_flush):
        assert role_sync.load_seen_ids() == set()

    def test_save_empty_is_noop(self, _valkey_flush):
        role_sync.save_seen_ids(set())
        assert role_sync.load_seen_ids() == set()

    def test_overwrite_replaces(self, _valkey_flush):
        role_sync.save_seen_ids({"old"})
        role_sync.save_seen_ids({"new1", "new2"})
        assert role_sync.load_seen_ids() == {"new1", "new2"}

    def test_union_with_existing(self, _valkey_flush):
        """Simulate poll_and_sync pattern: load_seen | new_ids → save."""
        role_sync.save_seen_ids({"first"})
        seen = role_sync.load_seen_ids() | {"second"}
        role_sync.save_seen_ids(seen)
        assert role_sync.load_seen_ids() == {"first", "second"}


# ======================================================================
# TestFilterNewEvents (pure function)
# ======================================================================


class TestFilterNewEvents:

    def test_all_new_when_seen_empty(self, sample_events):
        new = role_sync.filter_new_events(sample_events, set())
        assert len(new) == 3

    def test_filters_known_ids(self, sample_events):
        seen = {"evt-001", "evt-002"}
        new = role_sync.filter_new_events(sample_events, seen)
        assert len(new) == 1
        assert new[0]["id"] == "evt-003"

    def test_filters_all(self, sample_events):
        seen = {"evt-001", "evt-002", "evt-003"}
        assert role_sync.filter_new_events(sample_events, seen) == []

    def test_empty_list(self):
        assert role_sync.filter_new_events([], {"x"}) == []

    def test_event_without_id_passed_through(self):
        events = [{"operationType": "VIEW"}]  # no id
        new = role_sync.filter_new_events(events, set())
        assert len(new) == 1

    def test_mixed_known_and_new(self):
        events = [
            {"id": "old-1"},
            {"id": "new-1"},
            {"id": "old-2"},
            {"id": "new-2"},
        ]
        seen = {"old-1", "old-2"}
        new = role_sync.filter_new_events(events, seen)
        assert {e["id"] for e in new} == {"new-1", "new-2"}


# ======================================================================
# TestCollectEventIds (pure function)
# ======================================================================


class TestCollectEventIds:

    def test_collects_all_ids(self):
        events = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        assert role_sync.collect_event_ids(events) == {"a", "b", "c"}

    def test_skips_events_without_id(self):
        events = [{"id": "x"}, {"operationType": "VIEW"}, {}]
        assert role_sync.collect_event_ids(events) == {"x"}

    def test_empty_list(self):
        assert role_sync.collect_event_ids([]) == set()


# ======================================================================
# TestIntegration: Full Persistence Flow
# ======================================================================


class TestPersistenceFlow:

    def test_two_poll_cycles(self, sample_events, _valkey_flush):
        """Cycle 1: all events new. Cycle 2: all events seen."""
        # Cycle 1
        seen = role_sync.load_seen_ids()
        new_1 = role_sync.filter_new_events(sample_events, seen)
        assert len(new_1) == 3

        # Persist
        all_ids = role_sync.collect_event_ids(sample_events) | seen
        role_sync.save_seen_ids(all_ids)

        # Cycle 2
        seen_2 = role_sync.load_seen_ids()
        new_2 = role_sync.filter_new_events(sample_events, seen_2)
        assert len(new_2) == 0

    def test_mixed_across_cycles(self, _valkey_flush):
        """Some events already seen, some new."""
        role_sync.save_seen_ids({"old-1", "old-2"})

        events = [
            {"id": "old-1"},
            {"id": "new-1"},
            {"id": "old-2"},
            {"id": "new-2"},
        ]
        seen = role_sync.load_seen_ids()
        new = role_sync.filter_new_events(events, seen)
        assert {e["id"] for e in new} == {"new-1", "new-2"}

    def test_initial_sync_fast_path(self, _valkey_flush):
        """After save_sync_timestamp, sync_is_current is True."""
        role_sync.save_sync_timestamp()
        assert role_sync.sync_is_current() is True

    def test_initial_sync_slow_path(self, _valkey_flush):
        """When no checkpoint, sync_is_current is False."""
        # Fixture already flushed keys
        assert role_sync.sync_is_current() is False

    def test_constants(self):
        assert role_sync._CHECKPOINT_KEY == "role_sync:sync_ts"
        assert role_sync._SEEN_KEY == "role_sync:seen"
