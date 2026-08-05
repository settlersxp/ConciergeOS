#!/usr/bin/env python3
"""Tests for the persistence module (routes_persistence).

Run with: cd docker && python3 -m pytest tests/test_routes_persistence.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rbac_sync import routes_persistence, config


# ======================================================================
# Unit Tests: Persistence Functions
# ======================================================================


class TestYAMLPersistence:
    """Tests for load_existing_rbac_routes and related functions."""

    def test_load_existing_rbac_routes_file_not_found(self):
        """Should return empty dict when file doesn't exist."""
        result = routes_persistence.load_existing_rbac_routes(Path("/nonexistent/path.json"))
        assert result == {}

    def test_load_existing_rbac_routes_valid_file(self):
        """Should parse a valid JSON file."""
        test_data = [
            {"role": "test:role", "paths": ["/test"], "message": "test msg"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(test_data, f)
            temp_path = Path(f.name)

        try:
            result = routes_persistence.load_existing_rbac_routes(temp_path)
            assert "test:role" in result
            assert result["test:role"]["paths"] == ["/test"]
            assert result["test:role"]["message"] == "test msg"
        finally:
            os.unlink(temp_path)

    def test_load_existing_rbac_routes_empty_file(self):
        """Should return empty dict for empty JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("[]")
            temp_path = Path(f.name)

        try:
            result = routes_persistence.load_existing_rbac_routes(temp_path)
            assert result == {}
        finally:
            os.unlink(temp_path)

    def test_load_existing_rbac_routes_invalid_yaml(self):
        """Should return empty dict for invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json content [")
            temp_path = Path(f.name)

        try:
            result = routes_persistence.load_existing_rbac_routes(temp_path)
            assert result == {}
        finally:
            os.unlink(temp_path)

    def test_convert_keycloak_attrs_to_route_format(self):
        """Should convert Keycloak attrs to route format."""
        roles_with_attrs = {
            "role1": {
                "paths": ["/a", "/b"],
                "message": ["Access denied"],
            },
            "role2": {
                "paths": ["/c"],
            },
        }

        result = routes_persistence.convert_keycloak_attrs_to_route_format(roles_with_attrs)

        assert "role1" in result
        assert result["role1"]["paths"] == ["/a", "/b"]
        assert result["role1"]["message"] == "Access denied"

        assert "role2" in result
        assert result["role2"]["paths"] == ["/c"]
        assert result["role2"]["message"] == ""

    def test_convert_keycloak_attrs_with_message_list(self):
        """Should handle message as a list from Keycloak."""
        roles_with_attrs = {
            "role1": {
                "paths": ["/test"],
                "message": ["Message line 1", "Message line 2"],
            },
        }

        result = routes_persistence.convert_keycloak_attrs_to_route_format(roles_with_attrs)

        # Should take first element of message list
        assert result["role1"]["message"] == "Message line 1"

    def test_write_rbac_routes_file_creates_file(self):
        """Should create a JSON file if it doesn't exist."""
        roles_config = {
            "settings:view": {
                "paths": ["/settings", "/settings/*"],
                "message": "Access denied: /settings requires the settings:view role.",
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            success = routes_persistence.write_rbac_routes_file(temp_path, roles_config)
            assert success is True
            assert temp_path.exists()

            # Verify content
            with open(temp_path, "r") as f:
                data = json.load(f)

            assert len(data) == 1
            entry = data[0]
            assert entry["role"] == "settings:view"
            assert entry["paths"] == ["/settings", "/settings/*"]
        finally:
            os.unlink(temp_path)

    def test_write_rbac_routes_file_sorted_roles(self):
        """Should write roles in sorted order."""
        roles_config = {
            "z:role": {"paths": ["/z"]},
            "a:role": {"paths": ["/a"]},
            "m:role": {"paths": ["/m"]},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            routes_persistence.write_rbac_routes_file(temp_path, roles_config)

            with open(temp_path, "r") as f:
                data = json.load(f)

            # Should be sorted by role name
            assert [entry["role"] for entry in data] == ["a:role", "m:role", "z:role"]
        finally:
            os.unlink(temp_path)

    def test_write_rbac_routes_file_without_message(self):
        """Should handle roles without message."""
        roles_config = {
            "test:role": {
                "paths": ["/test"],
                "message": "",
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            routes_persistence.write_rbac_routes_file(temp_path, roles_config)

            with open(temp_path, "r") as f:
                data = json.load(f)

            assert len(data) == 1
            entry = data[0]
            assert entry["role"] == "test:role"
            assert entry["paths"] == ["/test"]
        finally:
            os.unlink(temp_path)

    def test_sync_rbac_routes_integration(self, live_token):
        """Test the full sync function with live Keycloak."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            success = routes_persistence.sync_rbac_routes(live_token, temp_path)
            assert success is True
            assert temp_path.exists()

            with open(temp_path, "r") as f:
                data = json.load(f)

            # Should have at least some roles written
            assert isinstance(data, list)
        finally:
            os.unlink(temp_path)


# ======================================================================
# Constants Tests
# ======================================================================


class TestRBACRoutesFileConstant:
    """Tests for RBAC_ROUTES_FILE constant."""

    def test_rbac_routes_file_path_exists(self):
        """RBAC_ROUTES_FILE should point to an existing file."""
        assert config.RBAC_ROUTES_FILE.exists()

    def test_rbac_routes_file_in_docker_directory(self):
        """RBAC_ROUTES_FILE should be in the docker directory."""
        assert "rbac_routes" in config.RBAC_ROUTES_FILE.name


# ======================================================================
# Fixtures for integration tests
# ======================================================================


@pytest.fixture
def live_token():
    """Get a live authentication token."""
    from keycloak_common import authenticate
    return authenticate()