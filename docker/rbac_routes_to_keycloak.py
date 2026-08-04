#!/usr/bin/env python3
"""Sync RBAC routes to Keycloak role attributes.

This script reads docker/rbac_routes.json and updates Keycloak roles with
their corresponding path and message attributes.

Usage:
    python3 rbac_routes_to_keycloak.py

The script will:
1. Parse the JSON file
2. Authenticate to Keycloak
3. For each role: create if not exists, or update attributes
4. Print a summary of all operations
"""

import logging
import sys
from pathlib import Path

from rbac_sync import (
    RBAC_ROUTES_FILE,
    sync_all_roles,
    print_summary,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    # Allow override via command line
    routes_path = RBAC_ROUTES_FILE
    create_if_missing = True

    if len(sys.argv) > 1:
        routes_path = Path(sys.argv[1])

    if "--no-create" in sys.argv:
        create_if_missing = False

    if not routes_path.exists():
        logger.error(f"Routes file not found: {routes_path}")
        sys.exit(1)

    # Run sync
    results = sync_all_roles(routes_path, create_if_missing)

    # Print summary
    print_summary(results)

    # Exit with error if any failed
    if any(v == "failed" for v in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()