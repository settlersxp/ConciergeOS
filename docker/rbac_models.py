"""Pydantic models for RBAC route definitions.

Provides typed models for the RBAC route configuration used by both
keycloak_setup and rbac_sync packages. Serves as the single source of
truth for RBAC route data structures.

Usage:
    from rbac_models import RBACRoute, RBACRoutes

    # Load from JSON
    routes = RBACRoutes.from_json("docker/rbac_routes.json")

    # Access by role
    for role, route in routes.by_role().items():
        print(f"{role}: {route.paths}")

    # Get role descriptions for Keycloak
    descriptions = routes.role_descriptions()
"""

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RBACRoute(BaseModel):
    """Single role-to-path mapping entry.

    Attributes:
        role: Role name (e.g., 'settings:view', 'models:admin')
        paths: List of path patterns protected by this role (frontend + API)
        menus: List of menu identifiers this role unlocks in the frontend
        message: Custom 403 denial message shown when access is denied
    """

    role: str = Field(..., min_length=1, description="Role name (e.g., 'settings:view')")
    paths: list[str] = Field(default_factory=list, description="Protected path patterns")
    menus: list[str] = Field(default_factory=list, description="Frontend menu identifiers this role unlocks")
    message: str = Field(default="", description="Custom 403 message")

    @property
    def description(self) -> str:
        """Derive a clean, human-readable description from the message field.

        Used for Keycloak role descriptions.

        Example input:  "Access denied: /settings requires the settings:view role."
        Example output: "/settings requires settings:view"
        """
        if not self.message:
            return f"Role: {self.role}"
        return (
            self.message
            .replace("Access denied: ", "")
            .replace(" role.", "")
            .replace(" requires the ", " requires ")
        )

    def to_dict(self) -> dict[str, Any]:
        """Return dict representation for backward compatibility."""
        return {
            "paths": self.paths,
            "menus": self.menus,
            "message": self.message,
        }


class RBACRoutes(BaseModel):
    """Collection of RBAC route definitions.

    Provides methods to load from JSON, convert to various formats,
    and persist back to disk.
    """

    routes: list[RBACRoute] = Field(default_factory=list)

    # ---- Lookup helpers ----

    def by_role(self) -> dict[str, RBACRoute]:
        """Return {role_name: RBACRoute} mapping."""
        return {r.role: r for r in self.routes}

    def role_definitions(self) -> dict[str, dict]:
        """Return {role_name: {'paths': [...], 'message': ''}} for backward compat."""
        return {r.role: r.to_dict() for r in self.routes}

    def role_descriptions(self) -> dict[str, str]:
        """Return {role_name: description} for Keycloak role creation."""
        return {r.role: r.description for r in self.routes}

    def get_role(self, role_name: str) -> RBACRoute | None:
        """Get a single RBACRoute by role name, or None if not found."""
        return self.by_role().get(role_name)

    # ---- File I/O ----

    @classmethod
    def from_json(cls, path: Path | str) -> "RBACRoutes":
        """Load RBAC routes from a JSON file.

        Args:
            path: Path to the JSON file

        Returns:
            RBACRoutes instance populated with data from the file

        Raises:
            FileNotFoundError: If the JSON file does not exist
        """
        path = Path(path) if not isinstance(path, Path) else path
        if not path.exists():
            raise FileNotFoundError(f"RBAC routes file not found: {path}")

        with open(path, "r") as f:
            data = json.load(f)

        routes = [RBACRoute(**entry) for entry in data if entry.get("role")]
        logger.debug("Loaded %d RBAC route(s) from %s", len(routes), path)
        return cls(routes=routes)

    def to_json(self, path: Path | str, indent: int = 2) -> bool:
        """Write RBAC routes to a JSON file.

        Args:
            path: Path to the JSON file to write
            indent: JSON indentation level

        Returns:
            True if successful, False otherwise
        """
        path = Path(path) if not isinstance(path, Path) else path

        try:
            # Sort routes by role name for consistent output
            sorted_routes = sorted(self.routes, key=lambda r: r.role)
            data = [r.model_dump(exclude_defaults=False) for r in sorted_routes]

            with open(path, "w") as f:
                json.dump(data, f, indent=indent)
                f.write("\n")

            logger.info("Wrote %d RBAC route(s) to %s", len(data), path)
            return True
        except Exception as e:
            logger.error("Failed to write JSON file %s: %s", path, e)
            return False

    # ---- Conversion helpers ----

    @classmethod
    def from_keycloak_attrs(cls, roles_with_attrs: dict[str, dict[str, list[str]]]) -> "RBACRoutes":
        """Create RBACRoutes from Keycloak role attributes.

        Converts the format returned by fetch_all_roles_with_attrs() into
        RBACRoutes.

        Args:
            roles_with_attrs: Dictionary from fetch_all_roles_with_attrs()
                {role_name: {"paths": [...], "menus": [...], "message": [...], ...}}

        Returns:
            RBACRoutes instance
        """
        routes = []
        for role_name, attrs in roles_with_attrs.items():
            paths = attrs.get("paths", [])
            menus = attrs.get("menus", [])
            # Keycloak stores message as a list, extract first element if present
            message_list = attrs.get("message", [])
            message = message_list[0] if message_list else ""

            routes.append(RBACRoute(role=role_name, paths=paths, menus=menus, message=message))

        return cls(routes=routes)

    def to_keycloak_attrs(self) -> dict[str, dict[str, list[str]]]:
        """Convert to Keycloak attribute format.

        Returns:
            Dictionary suitable for setting as Keycloak role attributes:
            {role_name: {"paths": [...], "menus": [...], "message": [...]}}
        """
        result = {}
        for route in self.routes:
            attrs: dict[str, list[str]] = {"paths": route.paths}
            if route.menus:
                attrs["menus"] = route.menus
            if route.message:
                attrs["message"] = [route.message]
            result[route.role] = attrs
        return result
