# Graph Report - .  (2026-08-05)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 663 nodes · 1208 edges · 38 communities (30 shown, 8 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 37 edges (avg confidence: 0.78)
- Token cost: 5,713 input · 4,384 output

## Graph Freshness
- Built from commit: `1637d23c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- .KEYCLOAK_REALM
- rbac_sync/__init__.py
- routes_persistence.py
- ConciergeOS Docker Setup
- keycloak_setup/__init__.py
- test_rbac_routes_to_keycloak.py
- authenticate
- helpers.py
- kc_request
- Settings
- TestYAMLPersistence
- roles.py
- has_role_events
- Any
- fixtures.py
- keycloak_diagnose.py
- clients.py
- test_oidc_config.py
- TestSignInRedirect
- TestPersistenceFlow
- TestParseRbacRoutes
- update_oidc_configs
- TestPushRoutesToCaddyConfigPreservation
- authenticate
- sample_caddy_config
- TestSeenIds
- TestFilterNewEvents
- TestSyncTimestamp
- discovery_config_direct
- TestLiveKeycloakRoles
- TestComposeIssuerURL
- create_composite_role
- TestCollectEventIds
- TestComposeSessionConfig
- install-cert-linux.sh
- install-cert-macos.sh

## God Nodes (most connected - your core abstractions)
1. `kc_request()` - 36 edges
2. `poll_and_sync()` - 22 edges
3. `has_role_events()` - 21 edges
4. `Settings` - 20 edges
5. `authenticate()` - 17 edges
6. `get_role_by_name()` - 16 edges
7. `main()` - 15 edges
8. `RBACRoutes` - 15 edges
9. `sync_role_to_keycloak()` - 13 edges
10. `generate_deny_rules()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `authenticate()`  [EXTRACTED]
  keycloak_setup/summary.py → keycloak_common.py
- `initial_sync()` --calls--> `authenticate()`  [EXTRACTED]
  rbac_sync/sync_orchestrator.py → keycloak_common.py
- `poll_and_sync()` --calls--> `authenticate()`  [EXTRACTED]
  rbac_sync/sync_orchestrator.py → keycloak_common.py
- `assign_user_to_roles()` --calls--> `kc_request()`  [EXTRACTED]
  keycloak_setup/assignments.py → keycloak_common.py
- `configure_role_claim()` --calls--> `kc_request()`  [EXTRACTED]
  keycloak_setup/claims.py → keycloak_common.py

## Import Cycles
- None detected.

## Communities (38 total, 8 thin omitted)

### Community 0 - ".KEYCLOAK_REALM"
Cohesion: 0.05
Nodes (48): Session, _clear_sync_checkpoint(), Clear the Valkey sync timestamp and disable sync_is_current() so initial_sync()…, cleanup_user(), count_oauth2_proxy_sessions(), DockerExecValkeyClient, ensure_test_user(), get_valkey_client() (+40 more)

### Community 1 - "rbac_sync/__init__.py"
Cohesion: 0.06
Nodes (53): datetime, fetch_all_roles_with_attrs(), has_events(), Check if any event matches the given resource and operation types., Fetch all roles with their attributes from the given realm (defaults to…, build_caddy_routes(), push_routes_to_caddy(), Caddy Route Generation module. Handles generating Caddy deny rules from… (+45 more)

### Community 2 - "routes_persistence.py"
Cohesion: 0.07
Nodes (34): BaseModel, load_rbac_routes(), load_role_definitions(), load_role_descriptions(), Path, Shared RBAC utilities for ConciergeOS. This module provides common functions…, Load role definitions from RBAC routes file. Args: routes_path: Path to the…, Load role names with human-readable descriptions from RBAC routes file. This is… (+26 more)

### Community 3 - "ConciergeOS Docker Setup"
Cohesion: 0.04
Nodes (45): Accepted tradeoff, Access Control Flow, Accessing the Application, Architecture, Build images, Build & Start, Certificate not trusted, Certificate persistence (+37 more)

### Community 4 - "keycloak_setup/__init__.py"
Cohesion: 0.12
Nodes (30): assign_all_users_to_roles(), assign_user_to_roles(), Assign a user to realm roles., Assign all users to their respective roles in all realms., configure_all_role_claims(), configure_role_claim(), Ensure realm roles are included in the access token. Roles are included in the…, Configure role claim for all realms. (+22 more)

### Community 5 - "test_rbac_routes_to_keycloak.py"
Cohesion: 0.10
Nodes (24): get_role_by_name(), Return role data dict if found, else None., create_role_with_attributes(), Create a new role with paths and message attributes. Args: token: Admin access…, Update an existing role's paths and message attributes. Args: token: Admin…, Sync a single role to Keycloak. Args: token: Admin access token realm: Realm…, sync_role_to_keycloak(), update_role_attributes() (+16 more)

### Community 6 - "authenticate"
Cohesion: 0.07
Nodes (26): authenticate(), Authenticate as admin to the master realm and return access token., main(), Path, Sync all roles from a routes file (JSON) to Keycloak. Parses the routes file,…, sync_all_roles(), live_token(), fixture (+18 more)

### Community 7 - "helpers.py"
Cohesion: 0.11
Nodes (16): generate_deny_rules(), get_menus_for_roles(), Generate Caddy deny rules from role attributes fetched from Keycloak. Each…, Aggregate menu items for a set of role names. Args: role_names: Set of role…, make_roles_with_attrs(), Resolve ${VAR:-default} and ${VAR} patterns to their default values., Return a list of mock Keycloak admin events., Build a roles_with_attrs dict for testing. Usage: roles =… (+8 more)

### Community 8 - "kc_request"
Cohesion: 0.12
Nodes (22): kc_request(), Response, Make an authenticated request to the Keycloak Admin API. Args: method: HTTP…, fetch_events_with_params(), get_realm_events(), Fetch realm events with custom query parameters. Returns the raw Response…, Fetch realm admin events for a date range. Args: token: Keycloak admin token…, create_realms() (+14 more)

### Community 9 - "Settings"
Cohesion: 0.10
Nodes (6): Main entry point for the sync service., run_sync_service(), main(), Main entry point for the role sync service., Environment-based configuration with sensible defaults. All attributes are read…, Settings

### Community 10 - "TestYAMLPersistence"
Cohesion: 0.09
Nodes (12): Should create a JSON file if it doesn't exist., Should write roles in sorted order., Should handle roles without message., Test the full sync function with live Keycloak., Tests for load_existing_rbac_routes and related functions., Should return empty dict when file doesn't exist., Should parse a valid JSON file., Should return empty dict for empty JSON file. (+4 more)

### Community 11 - "roles.py"
Cohesion: 0.15
Nodes (14): fetch_all_roles(), Fetch all role names in the given realm (defaults to settings.KEYCLOAK_REALM)., delete_role(), list_roles(), print_summary(), Response, Delete a role by name. Returns the raw Response. Args: token: Keycloak admin…, Fetch all role names in the given realm. Args: token: Keycloak admin token… (+6 more)

### Community 12 - "has_role_events"
Cohesion: 0.22
Nodes (5): has_role_events(), Check if any event is a role-related admin event. Args: events: List of admin…, VIEW on ROLE should NOT trigger re-sync., TestHasRoleEvents, TestHasRoleEvents

### Community 13 - "Any"
Cohesion: 0.14
Nodes (10): parametrize, Any, Both endpoints return the same set of keys., All discovery endpoints must start with https://out-customer.com., No endpoint in the discovery response contains internal Docker hostnames., Discovery endpoint reachable through Caddy → Keycloak proxy., Discovery endpoint reachable directly on localhost:8080., TestAuthorizationEndpoint (+2 more)

### Community 14 - "fixtures.py"
Cohesion: 0.18
Nodes (15): compose_content(), json_file(), fixture, Read docker-compose.yaml once per session., Generate a unique test role name., Return a list of mock Keycloak admin events., Sample RBAC routes JSON content for testing., Sample Caddy config that simulates a real config with multiple servers. (+7 more)

### Community 15 - "keycloak_diagnose.py"
Cohesion: 0.22
Nodes (13): authenticate(), get_base_url(), get_user_groups(), list_clients(), list_groups(), list_realms(), list_users(), main() (+5 more)

### Community 16 - "clients.py"
Cohesion: 0.25
Nodes (10): create_all_client_apis(), create_all_clients(), create_client(), create_client_api(), _create_client_in_realm(), Create the conciergeos client in a realm. Returns the client UUID. Keycloak 26…, Create the client-api service client (Client Credentials Grant). Returns…, Create clients in all realms. Returns {realm: client_uuid}. (+2 more)

### Community 17 - "test_oidc_config.py"
Cohesion: 0.22
Nodes (10): compose_issuer_url(), compose_redis_connection_url(), compose_session_store_type(), compose_ssl_insecure_skip_verify(), Extract OAUTH2_PROXY_OIDC_ISSUER_URL from the docker-compose.yaml environment., Extract OAUTH2_PROXY_SSL_INSECURE_SKIP_VERIFY from docker-compose.yaml., Extract OAUTH2_PROXY_SESSION_STORE_TYPE from docker-compose.yaml., Extract OAUTH2_PROXY_REDIS_CONNECTION_URL from docker-compose.yaml. (+2 more)

### Community 18 - "TestSignInRedirect"
Cohesion: 0.25
Nodes (6): Hit /oauth2/start and return the redirect Location header., Hitting /oauth2/start must redirect (302) to Keycloak's authorization endpoint., The redirect Location must NOT contain internal Docker hostnames., The redirect Location must point to Keycloak's authorization endpoint., The redirect Location must start with https://out-customer.com., TestSignInRedirect

### Community 19 - "TestPersistenceFlow"
Cohesion: 0.20
Nodes (5): Cycle 1: all events new. Cycle 2: all events seen., Some events already seen, some new., After save_sync_timestamp, sync_is_current is True., When no checkpoint, sync_is_current is False., TestPersistenceFlow

### Community 20 - "TestParseRbacRoutes"
Cohesion: 0.20
Nodes (6): Test that parsing a nonexistent file raises an error., Tests for parse_rbac_routes function., Test parsing a basic JSON file., Test parsing JSON where message is optional., Test parsing JSON where paths is optional., TestParseRbacRoutes

### Community 21 - "update_oidc_configs"
Cohesion: 0.31
Nodes (8): _find_env_file(), Find the docker .env file. Searches: 1. Same directory as this script 2. Parent…, Update OIDC_CLIENT_SECRET in the .env file in place., Update CLIENT_API_CLIENT_SECRET in the .env file in place., Print and automatically update the Keycloak client secrets in .env files.…, _update_env_file(), _update_env_file_client_api(), update_oidc_configs()

### Community 22 - "TestPushRoutesToCaddyConfigPreservation"
Cohesion: 0.22
Nodes (4): Verify the config manipulation preserves structure., Verify push_routes_to_caddy uses requests.patch, not requests.put., Verify push_routes_to_caddy fetches current config before pushing., TestPushRoutesToCaddyConfigPreservation

### Community 23 - "authenticate"
Cohesion: 0.29
Nodes (5): authenticate(), Authenticate as admin to the master realm and return access token., Authenticate against live Keycloak and verify we get a token., Verify the token can access the admin API., TestLiveKeycloakAuth

### Community 24 - "sample_caddy_config"
Cohesion: 0.29
Nodes (7): find_deny_rule_for_role(), Any, Sample RBAC routes JSON content for testing., Sample Caddy config that simulates a real config with multiple servers., Search Caddy routes for a deny rule referencing the given role., sample_caddy_config(), sample_rbac_json()

### Community 28 - "discovery_config_direct"
Cohesion: 0.40
Nodes (5): discovery_config_direct(), discovery_config_public(), Any, Fetch the OIDC discovery config via the public HTTPS domain (Caddy proxy)., Fetch the OIDC discovery config directly on localhost:8080.

### Community 29 - "TestLiveKeycloakRoles"
Cohesion: 0.40
Nodes (3): Fetch roles from live Keycloak — should return at least our defined roles., Keycloak always creates uma_authorization., TestLiveKeycloakRoles

### Community 31 - "create_composite_role"
Cohesion: 0.50
Nodes (4): create_composite_role(), create_role(), Create a realm role. Returns the role name (Keycloak roles are identified by…, Create a composite role that inherits from the given composite roles.

## Knowledge Gaps
- **38 isolated node(s):** `install-cert-linux.sh script`, `install-cert-macos.sh script`, `Services`, `Access Control Flow`, `Roles` (+33 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `kc_request()` connect `kc_request` to `rbac_sync/__init__.py`, `keycloak_setup/__init__.py`, `test_rbac_routes_to_keycloak.py`, `roles.py`, `clients.py`, `create_composite_role`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Why does `authenticate()` connect `authenticate` to `rbac_sync/__init__.py`, `roles.py`, `keycloak_setup/__init__.py`, `test_rbac_routes_to_keycloak.py`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Why does `TestYAMLPersistence` connect `TestYAMLPersistence` to `authenticate`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **What connects `install-cert-linux.sh script`, `install-cert-macos.sh script`, `Services` to the rest of the system?**
  _38 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `.KEYCLOAK_REALM` be split into smaller, more focused modules?**
  _Cohesion score 0.050078247261345854 - nodes in this community are weakly interconnected._
- **Should `rbac_sync/__init__.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06346153846153846 - nodes in this community are weakly interconnected._
- **Should `routes_persistence.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06845513413506013 - nodes in this community are weakly interconnected._