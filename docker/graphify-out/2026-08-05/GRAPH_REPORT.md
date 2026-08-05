# Graph Report - .  (2026-08-05)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 681 nodes · 1237 edges · 44 communities (36 shown, 8 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 38 edges (avg confidence: 0.78)
- Token cost: 6,816 input · 4,960 output

## Graph Freshness
- Built from commit: `97dc2dab`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- .KEYCLOAK_REALM
- session_management.py
- routes_persistence.py
- ConciergeOS Docker Setup
- keycloak_setup/__init__.py
- roles.py
- authenticate
- helpers.py
- kc_request
- Settings
- TestYAMLPersistence
- .VALKEY_URL
- has_role_events
- Any
- fixture
- keycloak_diagnose.py
- clients.py
- fixtures.py
- TestSignInRedirect
- TestPersistenceFlow
- TestParseRbacRoutes
- update_oidc_configs
- build_caddy_routes
- test_keycloak_events.py
- poll_and_sync
- TestSeenIds
- TestFilterNewEvents
- test_event_persistence.py
- rbac_sync/__init__.py
- sync_orchestrator.py
- TestComposeIssuerURL
- create_composite_role
- sync_all_roles
- TestComposeSessionConfig
- install-cert-linux.sh
- install-cert-macos.sh
- initial_sync
- TestRBACRoutesFileConstant
- assignments.py
- live_token
- print_summary
- invalidate_all_sessions

## God Nodes (most connected - your core abstractions)
1. `kc_request()` - 36 edges
2. `poll_and_sync()` - 22 edges
3. `has_role_events()` - 21 edges
4. `Settings` - 21 edges
5. `authenticate()` - 17 edges
6. `generate_deny_rules()` - 17 edges
7. `get_role_by_name()` - 16 edges
8. `main()` - 15 edges
9. `RBACRoutes` - 15 edges
10. `make_roles_with_attrs()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `authenticate()`  [EXTRACTED]
  keycloak_setup/summary.py → keycloak_common.py
- `sync_all_roles()` --calls--> `authenticate()`  [EXTRACTED]
  rbac_sync/role_operations.py → keycloak_common.py
- `initial_sync()` --calls--> `authenticate()`  [EXTRACTED]
  rbac_sync/sync_orchestrator.py → keycloak_common.py
- `poll_and_sync()` --calls--> `authenticate()`  [EXTRACTED]
  rbac_sync/sync_orchestrator.py → keycloak_common.py
- `live_token()` --calls--> `authenticate()`  [EXTRACTED]
  tests/conftest.py → keycloak_common.py

## Import Cycles
- None detected.

## Communities (44 total, 8 thin omitted)

### Community 0 - ".KEYCLOAK_REALM"
Cohesion: 0.07
Nodes (39): Session, cleanup_user(), count_oauth2_proxy_sessions(), DockerExecValkeyClient, ensure_test_user(), get_valkey_client(), list_oauth2_proxy_sessions(), oauth2_login_flow() (+31 more)

### Community 1 - "session_management.py"
Cohesion: 0.20
Nodes (13): _get_valkey_client(), load_seen_ids(), load_sync_timestamp(), Session Management module for Valkey session invalidation. Handles session…, True if a successful sync happened within the last 2xSYNC_INTERVAL. Returns:…, Load today's set of already-processed event IDs. Returns: Set of event IDs that…, Replace today's seen set. Args: ids: Set of event IDs to mark as seen, Return a Valkey client or None if unreachable. Returns: Valkey client instance… (+5 more)

### Community 2 - "routes_persistence.py"
Cohesion: 0.07
Nodes (34): BaseModel, load_rbac_routes(), load_role_definitions(), load_role_descriptions(), Path, Shared RBAC utilities for ConciergeOS. This module provides common functions…, Load role definitions from RBAC routes file. Args: routes_path: Path to the…, Load role names with human-readable descriptions from RBAC routes file. This is… (+26 more)

### Community 3 - "ConciergeOS Docker Setup"
Cohesion: 0.04
Nodes (45): Accepted tradeoff, Access Control Flow, Accessing the Application, Architecture, Build images, Build & Start, Certificate not trusted, Certificate persistence (+37 more)

### Community 4 - "keycloak_setup/__init__.py"
Cohesion: 0.14
Nodes (24): configure_all_role_claims(), configure_role_claim(), Ensure realm roles are included in the access token. Roles are included in the…, Configure role claim for all realms., create_all_client_apis(), get_actual_client_secret(), get_client_api_secret(), Create the client-api service client in all realms. Returns {realm:… (+16 more)

### Community 5 - "roles.py"
Cohesion: 0.11
Nodes (22): get_role_by_name(), Return role data dict if found, else None., create_role_with_attributes(), Create a new role with paths and message attributes. Args: token: Admin access…, Update an existing role's paths and message attributes. Args: token: Admin…, Sync a single role to Keycloak. Args: token: Admin access token realm: Realm…, sync_role_to_keycloak(), update_role_attributes() (+14 more)

### Community 6 - "authenticate"
Cohesion: 0.40
Nodes (5): authenticate(), Authenticate as admin to the master realm and return access token., live_token(), fixture, Get a live authentication token.

### Community 7 - "helpers.py"
Cohesion: 0.07
Nodes (29): generate_deny_rules(), get_menus_for_roles(), _is_api_path(), _load_fallback_roles(), Aggregate menu items for a set of role names. Args: role_names: Set of role…, Return True if *path* is a backend API path. API paths are enforced by the…, Load role path/menus from rbac_routes.json as fallback. Returns: Dictionary…, Generate Caddy deny rules from role attributes fetched from Keycloak. Each… (+21 more)

### Community 8 - "kc_request"
Cohesion: 0.13
Nodes (20): fetch_all_roles(), kc_request(), Response, Make an authenticated request to the Keycloak Admin API. Args: method: HTTP…, Fetch all role names in the given realm (defaults to settings.KEYCLOAK_REALM)., list_roles_with_attrs(), Fetch all roles with their attributes from the given realm. Returns {role_name:…, _clear_required_actions() (+12 more)

### Community 9 - "Settings"
Cohesion: 0.07
Nodes (9): _push_routes_to_caddy(), Push routes to a specific Caddy instance. Args: admin_url: Caddy Admin API URL…, Push the updated routes to both Caddy instances. Args: frontend_routes: Routes…, Environment-based configuration with sensible defaults. All attributes are read…, Settings, Verify the config manipulation preserves structure., Verify _push_routes_to_caddy uses requests.patch, not requests.put., Verify _push_routes_to_caddy fetches current config before pushing. (+1 more)

### Community 10 - "TestYAMLPersistence"
Cohesion: 0.09
Nodes (12): Should create a JSON file if it doesn't exist., Should write roles in sorted order., Should handle roles without message., Test the full sync function with live Keycloak., Tests for load_existing_rbac_routes and related functions., Should return empty dict when file doesn't exist., Should parse a valid JSON file., Should return empty dict for empty JSON file. (+4 more)

### Community 11 - ".VALKEY_URL"
Cohesion: 0.17
Nodes (14): delete_role(), Response, Delete a role by name. Returns the raw Response. Args: token: Keycloak admin…, Create or update a role with paths and menus attributes. If the role exists,…, upsert_role_with_attributes(), _clear_sync_checkpoint(), live_test_role(), live_token() (+6 more)

### Community 12 - "has_role_events"
Cohesion: 0.14
Nodes (10): has_role_events(), Check if any event is a role-related admin event. Args: events: List of admin…, VIEW on ROLE should NOT trigger re-sync., TestHasRoleEvents, live_token(), fixture, poll_and_sync() runs without exceptions (hits live Keycloak + Caddy)., Get a live authentication token. (+2 more)

### Community 13 - "Any"
Cohesion: 0.14
Nodes (10): parametrize, Any, Both endpoints return the same set of keys., All discovery endpoints must start with https://out-customer.com., No endpoint in the discovery response contains internal Docker hostnames., Discovery endpoint reachable through Caddy → Keycloak proxy., Discovery endpoint reachable directly on localhost:8080., TestAuthorizationEndpoint (+2 more)

### Community 14 - "fixture"
Cohesion: 0.18
Nodes (11): compose_content(), json_file(), fixture, Read docker-compose.yaml once per session., Generate a unique test role name., Sample RBAC routes JSON content for testing., Sample Caddy config that simulates a real config with multiple servers., Create a temporary JSON file with sample RBAC content. (+3 more)

### Community 15 - "keycloak_diagnose.py"
Cohesion: 0.22
Nodes (13): authenticate(), get_base_url(), get_user_groups(), list_clients(), list_groups(), list_realms(), list_users(), main() (+5 more)

### Community 16 - "clients.py"
Cohesion: 0.31
Nodes (8): create_all_clients(), create_client(), create_client_api(), _create_client_in_realm(), Create the conciergeos client in a realm. Returns the client UUID. Keycloak 26…, Create the client-api service client (Client Credentials Grant). Returns…, Create clients in all realms. Returns {realm: client_uuid}., Create (or update) a Keycloak client. Returns (client_uuid, secret).

### Community 17 - "fixtures.py"
Cohesion: 0.19
Nodes (15): compose_issuer_url(), compose_redis_connection_url(), compose_session_store_type(), compose_ssl_insecure_skip_verify(), discovery_config_direct(), discovery_config_public(), Any, Extract OAUTH2_PROXY_OIDC_ISSUER_URL from the docker-compose.yaml environment. (+7 more)

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

### Community 22 - "build_caddy_routes"
Cohesion: 0.17
Nodes (8): build_caddy_routes(), Build the full internal-server routes array. Combines static assets route, full…, Empty deny rules produces 2 routes for RBAC gateway: full_access_bypass, catch-…, Verify full-access bypass is the first route in RBAC gateway., Empty deny rules produces 3 routes: static_assets, full_access_bypass, catch-…, Deny rules inserted between full_access_bypass and catch-all., Verify the route order: static assets, full_access_bypass, deny rules, catch-…, TestBuildCaddyRoutes

### Community 23 - "test_keycloak_events.py"
Cohesion: 0.07
Nodes (25): authenticate(), Authenticate as admin to the master realm and return access token., fetch_events_with_params(), get_realm_events(), Fetch realm events with custom query parameters. Returns the raw Response…, Fetch realm admin events for a date range. Args: token: Keycloak admin token…, _ensure_events_enabled(), get_realm_config() (+17 more)

### Community 24 - "poll_and_sync"
Cohesion: 0.16
Nodes (12): collect_event_ids(), filter_new_events(), Return only events whose IDs are not in *seen*. Args: events: List of events to…, Extract every event ID from a list of events. Args: events: List of event…, poll_and_sync(), Poll Keycloak for role changes and sync if needed. Returns: True if successful,…, Wait for Keycloak and Caddy to be ready. Args: max_retries: Maximum number of…, Main entry point for the sync service. (+4 more)

### Community 27 - "test_event_persistence.py"
Cohesion: 0.12
Nodes (6): Return a list of mock Keycloak admin events., Flush all role_sync:* keys from Valkey before and after each test. Gracefully…, sample_events(), _valkey_flush(), TestCollectEventIds, TestSyncTimestamp

### Community 28 - "rbac_sync/__init__.py"
Cohesion: 0.23
Nodes (9): build_rbac_routes(), Caddy Route Generation module. Handles generating Caddy deny rules from…, Build the full caddy-rbac gateway routes array. Order: full-access bypass →…, Read current routes from the main Caddy for verification/debugging. Returns:…, Read current routes from the RBAC gateway for verification/debugging. Returns:…, verify_caddy_routes(), verify_rbac_routes(), Configuration constants for RBAC sync operations. Centralizes all configuration… (+1 more)

### Community 29 - "sync_orchestrator.py"
Cohesion: 0.27
Nodes (9): datetime, has_events(), Check if any event matches the given resource and operation types., has_user_delete_events(), poll_admin_events(), Event Polling module for Keycloak admin events. Handles polling Keycloak's…, Poll Keycloak admin events since the given timestamp. Keycloak 26 has two…, Check if any event is a user DELETE or USER_SESSION DELETE event. Args: events:… (+1 more)

### Community 31 - "create_composite_role"
Cohesion: 0.50
Nodes (4): create_composite_role(), create_role(), Create a realm role. Returns the role name (Keycloak roles are identified by…, Create a composite role that inherits from the given composite roles.

### Community 32 - "sync_all_roles"
Cohesion: 0.25
Nodes (7): main(), Path, Sync all roles from a routes file (JSON) to Keycloak. Parses the routes file,…, sync_all_roles(), Tests for the full sync flow., Test syncing all roles from a JSON file., TestSyncAllRoles

### Community 38 - "initial_sync"
Cohesion: 0.29
Nodes (8): fetch_all_roles_with_attrs(), Fetch all roles with their attributes from the given realm (defaults to…, convert_keycloak_attrs_to_route_format(), Convert Keycloak role attributes to route-compatible format. Args:…, Fetch roles from Keycloak and write to an RBAC routes file. Args: token:…, sync_rbac_routes(), initial_sync(), Perform initial full sync on startup. Returns: True if successful, False…

### Community 39 - "TestRBACRoutesFileConstant"
Cohesion: 0.33
Nodes (4): Tests for RBAC_ROUTES_FILE constant., RBAC_ROUTES_FILE should point to an existing file., RBAC_ROUTES_FILE should be in the docker directory., TestRBACRoutesFileConstant

### Community 40 - "assignments.py"
Cohesion: 0.50
Nodes (4): assign_all_users_to_roles(), assign_user_to_roles(), Assign a user to realm roles., Assign all users to their respective roles in all realms.

### Community 41 - "live_token"
Cohesion: 0.67
Nodes (3): live_token(), fixture, Get a live authentication token.

## Knowledge Gaps
- **38 isolated node(s):** `install-cert-linux.sh script`, `install-cert-macos.sh script`, `Services`, `Access Control Flow`, `Roles` (+33 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `kc_request()` connect `kc_request` to `keycloak_setup/__init__.py`, `roles.py`, `initial_sync`, `assignments.py`, `.VALKEY_URL`, `clients.py`, `test_keycloak_events.py`, `sync_orchestrator.py`, `create_composite_role`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Why does `authenticate()` connect `authenticate` to `sync_all_roles`, `keycloak_setup/__init__.py`, `roles.py`, `initial_sync`, `live_token`, `.VALKEY_URL`, `has_role_events`, `poll_and_sync`, `sync_orchestrator.py`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Why does `TestYAMLPersistence` connect `TestYAMLPersistence` to `authenticate`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **What connects `install-cert-linux.sh script`, `install-cert-macos.sh script`, `Services` to the rest of the system?**
  _38 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `.KEYCLOAK_REALM` be split into smaller, more focused modules?**
  _Cohesion score 0.06516290726817042 - nodes in this community are weakly interconnected._
- **Should `routes_persistence.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06845513413506013 - nodes in this community are weakly interconnected._
- **Should `ConciergeOS Docker Setup` be split into smaller, more focused modules?**
  _Cohesion score 0.043478260869565216 - nodes in this community are weakly interconnected._