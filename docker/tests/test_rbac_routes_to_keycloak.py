#!/usr/bin/env python3
"""
Tests for rbac_routes_to_keycloak.py

Run with: cd docker && python3 -m pytest tests/test_rbac_routes_to_keycloak.py -v

Updated to use new modules from rbac_sync and keycloak_setup packages.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rbac_sync import routes_persistence
from rbac_sync.role_operations import sync_all_roles
from keycloak_common import authenticate, get_role_by_name
from keycloak_setup.roles import (
    create_role_with_attributes,
    delete_role,
    sync_role_to_keycloak,
    update_role_attributes,
)
from settings import settings


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def sample_rbac_json():
    """Sample RBAC routes JSON content for testing."""
    return [
        {
            "role": "test:role1",
            "paths": ["/test1", "/test1/*"],
            "message": "Access denied for test1",
        },
        {
            "role": "test:role2",
            "paths": ["/test2"],
            "message": "Access denied for test2",
        },
        {
            "role": "test:role3",
            "paths": ["/test3/a", "/test3/b", "/test3/c"],
            "message": "",
        },
    ]


@pytest.fixture
def json_file(sample_rbac_json):
    """Create a temporary JSON file with sample content."""
    import json
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_rbac_json, f)
        f.flush()
        yield Path(f.name)
    os.unlink(f.name)


@pytest.fixture
def live_token():
    """Get a live authentication token."""
    return authenticate()


@pytest.fixture
def test_role_name():
    """Generate a unique test role name."""
    import time
    return f"test:cof-rbac-{int(time.time())}"


# ======================================================================
# Unit Tests: YAML Parsing
# ======================================================================


class TestParseRbacRoutes:
    """Tests for parse_rbac_routes function."""

    def test_parse_basic_json(self, json_file):
        """Test parsing a basic JSON file."""
        result = routes_persistence.parse_rbac_routes(json_file)

        assert "test:role1" in result
        assert "test:role2" in result
        assert "test:role3" in result

        assert result["test:role1"]["paths"] == ["/test1", "/test1/*"]
        assert result["test:role1"]["message"] == "Access denied for test1"

        assert result["test:role2"]["paths"] == ["/test2"]
        assert result["test:role2"]["message"] == "Access denied for test2"

        assert result["test:role3"]["paths"] == ["/test3/a", "/test3/b", "/test3/c"]

    def test_parse_json_with_empty_message(self):
        """Test parsing JSON where message is optional."""
        import json
        json_content = [{"role": "test:role", "paths": ["/test"]}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            f.flush()
            json_path = Path(f.name)

        try:
            result = routes_persistence.parse_rbac_routes(json_path)
            assert result["test:role"]["paths"] == ["/test"]
            assert result["test:role"]["message"] == ""
        finally:
            os.unlink(json_path)

    def test_parse_json_with_empty_paths(self):
        """Test parsing JSON where paths is optional."""
        import json
        json_content = [{"role": "test:role", "message": "No paths defined"}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            f.flush()
            json_path = Path(f.name)

        try:
            result = routes_persistence.parse_rbac_routes(json_path)
            assert result["test:role"]["paths"] == []
            assert result["test:role"]["message"] == "No paths defined"
        finally:
            os.unlink(json_path)

    def test_parse_nonexistent_file(self):
        """Test that parsing a nonexistent file raises an error."""
        with pytest.raises(FileNotFoundError):
            routes_persistence.parse_rbac_routes(Path("/nonexistent/path.json"))


# ======================================================================
# Integration Tests: Keycloak Role Operations
# ======================================================================


class TestCreateRoleWithAttributes:
    """Tests for creating roles with attributes."""

    def test_create_role_with_paths_and_message(
        self, live_token, test_role_name
    ):
        """Test creating a role with paths and message attributes."""
        realm = settings.KEYCLOAK_REALM
        paths = ["/api/test", "/api/test/*"]
        message = "Test access denied message"

        success = create_role_with_attributes(
            live_token, realm, test_role_name, paths, message
        )

        assert success is True

        # Verify the role was created with correct attributes
        role_data = get_role_by_name(live_token, realm, test_role_name)
        assert role_data is not None
        assert role_data["name"] == test_role_name
        assert role_data.get("attributes", {}).get("paths") == paths
        assert role_data.get("attributes", {}).get("message") == [message]

    def test_create_role_without_message(
        self, live_token, test_role_name
    ):
        """Test creating a role without a message."""
        realm = settings.KEYCLOAK_REALM
        paths = ["/api/test"]

        success = create_role_with_attributes(
            live_token, realm, test_role_name, paths, ""
        )

        assert success is True

        role_data = get_role_by_name(live_token, realm, test_role_name)
        assert role_data is not None
        assert role_data.get("attributes", {}).get("paths") == paths
        assert role_data.get("attributes", {}).get("message") == []


class TestUpdateRoleAttributes:
    """Tests for updating role attributes."""

    def test_update_existing_role_attributes(
        self, live_token, test_role_name
    ):
        """Test updating an existing role's attributes."""
        realm = settings.KEYCLOAK_REALM

        # First create the role
        create_role_with_attributes(
            live_token, realm, test_role_name, ["/old/path"], "Old message"
        )

        # Now update the attributes
        new_paths = ["/new/path", "/new/path/*"]
        new_message = "New access denied message"

        success = update_role_attributes(
            live_token, realm, test_role_name, new_paths, new_message
        )

        assert success is True

        # Verify the update
        role_data = get_role_by_name(live_token, realm, test_role_name)
        assert role_data.get("attributes", {}).get("paths") == new_paths
        assert role_data.get("attributes", {}).get("message") == [new_message]

    def test_update_nonexistent_role(
        self, live_token, test_role_name
    ):
        """Test updating a role that doesn't exist."""
        realm = settings.KEYCLOAK_REALM

        success = update_role_attributes(
            live_token, realm, test_role_name, ["/test"], "Message"
        )

        assert success is False


class TestSyncRoleToKeycloak:
    """Tests for the sync_role_to_keycloak function."""

    def test_sync_creates_new_role(
        self, live_token, test_role_name
    ):
        """Test that sync creates a new role if it doesn't exist."""
        realm = settings.KEYCLOAK_REALM
        config = {
            "paths": ["/sync/test", "/sync/test/*"],
            "message": "Sync test message",
        }

        success, action = sync_role_to_keycloak(
            live_token, realm, test_role_name, config, create_if_missing=True
        )

        assert success is True
        assert action == "created"

        role_data = get_role_by_name(live_token, realm, test_role_name)
        assert role_data is not None
        assert role_data.get("attributes", {}).get("paths") == config["paths"]

    def test_sync_updates_existing_role(
        self, live_token, test_role_name
    ):
        """Test that sync updates an existing role."""
        realm = settings.KEYCLOAK_REALM

        # Create role with initial config
        create_role_with_attributes(
            live_token, realm, test_role_name, ["/initial"], "Initial"
        )

        # Sync with new config
        new_config = {
            "paths": ["/updated", "/updated/*"],
            "message": "Updated message",
        }

        success, action = sync_role_to_keycloak(
            live_token, realm, test_role_name, new_config, create_if_missing=True
        )

        assert success is True
        assert action == "updated"

        role_data = get_role_by_name(live_token, realm, test_role_name)
        assert role_data is not None
        assert role_data.get("attributes", {}).get("paths") == new_config["paths"]

    def test_sync_skips_if_not_create(
        self, live_token, test_role_name
    ):
        """Test that sync skips if role doesn't exist and create_if_missing=False."""
        realm = settings.KEYCLOAK_REALM
        config = {
            "paths": ["/test"],
            "message": "Test",
        }

        success, action = sync_role_to_keycloak(
            live_token, realm, test_role_name, config, create_if_missing=False
        )

        assert success is False
        assert action == "skipped"

        # Verify role was not created
        role_data = get_role_by_name(live_token, realm, test_role_name)
        assert role_data is None


# ======================================================================
# Integration Tests: Full Sync Flow
# ======================================================================


class TestSyncAllRoles:
    """Tests for the full sync flow."""

    def test_sync_all_roles_from_json(
        self, live_token, json_file
    ):
        """Test syncing all roles from a JSON file."""
        realm = settings.KEYCLOAK_REALM

        results = sync_all_roles(json_file, create_if_missing=True)

        # Check all roles were created
        assert "test:role1" in results
        assert "test:role2" in results
        assert "test:role3" in results

        # Check all succeeded
        assert results["test:role1"] == "created"
        assert results["test:role2"] == "created"
        assert results["test:role3"] == "created"

        # Verify roles exist with correct attributes
        for role_name in results:
            role_data = get_role_by_name(live_token, realm, role_name)
            assert role_data is not None

        # Cleanup: delete the test roles using keycloak_setup primitives
        for role_name in results:
            try:
                resp = delete_role(live_token, realm, role_name)
                assert resp.status_code in (204, 404)
            except Exception:
                pass
