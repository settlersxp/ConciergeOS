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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rbac_sync import session_management, SYNC_INTERVAL

from fixtures import sample_events, _valkey_flush


# ======================================================================
# TestSyncTimestamp (checkpoint)
# ======================================================================


class TestSyncTimestamp:

    def test_save_and_load(self, _valkey_flush):
        session_management.save_sync_timestamp()
        ts = session_management.load_sync_timestamp()
        assert ts is not None
        assert isinstance(ts, float)
        assert ts <= time.time()

    def test_load_none_when_empty(self, monkeypatch):
        monkeypatch.setattr(session_management, "_CHECKPOINT_KEY", "role_sync:__none__")
        assert session_management.load_sync_timestamp() is None

    def test_sync_is_current_after_save(self, _valkey_flush):
        session_management.save_sync_timestamp()
        assert session_management.sync_is_current() is True

    def test_sync_is_current_stale(self, monkeypatch, _valkey_flush):
        session_management.save_sync_timestamp()
        stale_ts = time.time() - (SYNC_INTERVAL * 3)
        monkeypatch.setattr(session_management, "load_sync_timestamp", lambda: stale_ts)
        assert session_management.sync_is_current() is False

    def test_sync_is_current_no_checkpoint(self, monkeypatch):
        monkeypatch.setattr(session_management, "load_sync_timestamp", lambda: None)
        assert session_management.sync_is_current() is False

    def test_survives_overwrite(self, _valkey_flush):
        session_management.save_sync_timestamp()
        ts1 = session_management.load_sync_timestamp()
        time.sleep(0.05)
        session_management.save_sync_timestamp()
        ts2 = session_management.load_sync_timestamp()
        assert ts2 is not None and ts1 is not None and ts2 >= ts1


# ======================================================================
# TestSeenIds
# ======================================================================


class TestSeenIds:

    def test_save_and_load(self, _valkey_flush):
        ids = {"a", "b", "c"}
        session_management.save_seen_ids(ids)
        assert session_management.load_seen_ids() == ids

    def test_load_empty_when_none(self, _valkey_flush):
        assert session_management.load_seen_ids() == set()

    def test_save_empty_is_noop(self, _valkey_flush):
        session_management.save_seen_ids(set())
        assert session_management.load_seen_ids() == set()

    def test_overwrite_replaces(self, _valkey_flush):
        session_management.save_seen_ids({"old"})
        session_management.save_seen_ids({"new1", "new2"})
        assert session_management.load_seen_ids() == {"new1", "new2"}

    def test_union_with_existing(self, _valkey_flush):
        """Simulate poll_and_sync pattern: load_seen | new_ids → save."""
        session_management.save_seen_ids({"first"})
        seen = session_management.load_seen_ids() | {"second"}
        session_management.save_seen_ids(seen)
        assert session_management.load_seen_ids() == {"first", "second"}


# ======================================================================
# TestFilterNewEvents (pure function)
# ======================================================================


class TestFilterNewEvents:

    def test_all_new_when_seen_empty(self, sample_events):
        new = session_management.filter_new_events(sample_events, set())
        assert len(new) == 3

    def test_filters_known_ids(self, sample_events):
        seen = {"evt-001", "evt-002"}
        new = session_management.filter_new_events(sample_events, seen)
        assert len(new) == 1
        assert new[0]["id"] == "evt-003"

    def test_filters_all(self, sample_events):
        seen = {"evt-001", "evt-002", "evt-003"}
        assert session_management.filter_new_events(sample_events, seen) == []

    def test_empty_list(self):
        assert session_management.filter_new_events([], {"x"}) == []

    def test_event_without_id_passed_through(self):
        events = [{"operationType": "VIEW"}]  # no id
        new = session_management.filter_new_events(events, set())
        assert len(new) == 1

    def test_mixed_known_and_new(self):
        events = [
            {"id": "old-1"},
            {"id": "new-1"},
            {"id": "old-2"},
            {"id": "new-2"},
        ]
        seen = {"old-1", "old-2"}
        new = session_management.filter_new_events(events, seen)
        assert {e["id"] for e in new} == {"new-1", "new-2"}


# ======================================================================
# TestCollectEventIds (pure function)
# ======================================================================


class TestCollectEventIds:

    def test_collects_all_ids(self):
        events = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        assert session_management.collect_event_ids(events) == {"a", "b", "c"}

    def test_skips_events_without_id(self):
        events = [{"id": "x"}, {"operationType": "VIEW"}, {}]
        assert session_management.collect_event_ids(events) == {"x"}

    def test_empty_list(self):
        assert session_management.collect_event_ids([]) == set()


# ======================================================================
# TestIntegration: Full Persistence Flow
# ======================================================================


class TestPersistenceFlow:

    def test_two_poll_cycles(self, sample_events, _valkey_flush):
        """Cycle 1: all events new. Cycle 2: all events seen."""
        # Cycle 1
        seen = session_management.load_seen_ids()
        new_1 = session_management.filter_new_events(sample_events, seen)
        assert len(new_1) == 3

        # Persist
        all_ids = session_management.collect_event_ids(sample_events) | seen
        session_management.save_seen_ids(all_ids)

        # Cycle 2
        seen_2 = session_management.load_seen_ids()
        new_2 = session_management.filter_new_events(sample_events, seen_2)
        assert len(new_2) == 0

    def test_mixed_across_cycles(self, _valkey_flush):
        """Some events already seen, some new."""
        session_management.save_seen_ids({"old-1", "old-2"})

        events = [
            {"id": "old-1"},
            {"id": "new-1"},
            {"id": "old-2"},
            {"id": "new-2"},
        ]
        seen = session_management.load_seen_ids()
        new = session_management.filter_new_events(events, seen)
        assert {e["id"] for e in new} == {"new-1", "new-2"}

    def test_initial_sync_fast_path(self, _valkey_flush):
        """After save_sync_timestamp, sync_is_current is True."""
        session_management.save_sync_timestamp()
        assert session_management.sync_is_current() is True

    def test_initial_sync_slow_path(self, _valkey_flush):
        """When no checkpoint, sync_is_current is False."""
        # Fixture already flushed keys
        assert session_management.sync_is_current() is False

    def test_constants(self):
        assert session_management._CHECKPOINT_KEY == "role_sync:sync_ts"
        assert session_management._SEEN_KEY == "role_sync:seen"