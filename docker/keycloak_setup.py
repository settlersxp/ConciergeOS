#!/usr/bin/env python3
"""Keycloak Setup Script for ConciergeOS.

This is a thin wrapper that delegates to the keycloak_setup package.
Provisions realms, users, roles, and client configuration for ConciergeOS.

Usage: python keycloak_setup.py [keycloak_host] [keycloak_port]
Example: python keycloak_setup.py localhost 8080
"""

from keycloak_setup.summary import main

if __name__ == "__main__":
    main()