# Graph Report - .  (2026-08-06)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 681 nodes · 1257 edges · 38 communities (30 shown, 8 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 35 edges (avg confidence: 0.78)
- Token cost: 5,899 input · 4,384 output

## Graph Freshness
- Built from commit: `de58e35c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- rbac_sync/__init__.py
- ConciergeOS Docker Setup
- test_valkey_session.py
- helpers.py
- test_rbac_routes_to_keycloak.py
- RBACRoutes
- has_role_events
- kc_request
- TestYAMLPersistence
- .KEYCLOAK_REALM
- Any
- settings.py
- fixtures.py
- roles.py
- Settings
- test_event_persistence.py
- keycloak_diagnose.py
- summary.py
- keycloak_setup/__init__.py
- fixture
- TestSignInRedirect
- conftest.py
- TestPersistenceFlow
- TestParseRbacRoutes
- update_oidc_configs
- TestPushRoutesToCaddyConfigPreservation
- TestSeenIds
- TestFilterNewEvents
- TestRoleEventTypes
- TestRBACRoutesFileConstant
- assignments.py
- claims.py
- TestComposeIssuerURL
- TestComposeSessionConfig
- install-cert-linux.sh
- install-cert-macos.sh

## God Nodes (most connected - your core abstractions)
1. `kc_request()` - 36 edges
2. `has_role_events()` - 21 edges
3. `poll_and_sync()` - 21 edges
4. `Settings` - 20 edges
5. `authenticate()` - 17 edges
6. `get_role_by_name()` - 16 edges
7. `main()` - 15 edges
8. `RBACRoutes` - 15 edges
9. `generate_deny_rules()` - 15 edges
10. `make_roles_with_attrs()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `sync_all_roles()` --calls--> `authenticate()`  [EXTRACTED]
  rbac_sync/role_operations.py → keycloak_common.py
- `initial_sync()` --calls--> `authenticate()`  [EXTRACTED]
  rbac_sync/sync_orchestrator.py → keycloak_common.py
- `poll_and_sync()` --calls--> `authenticate()`  [EXTRACTED]
  rbac_sync/sync_orchestrator.py → keycloak_common.py
- `live_token()` --calls--> `authenticate()`  [EXTRACTED]
  tests/conftest.py → keycloak_common.py
- `live_token()` --calls--> `authenticate()`  [EXTRACTED]
  tests/test_rbac_routes_to_keycloak.py → keycloak_common.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Authentication & Routing Flow** — docker_compose_caddy, docker_compose_oidc, docker_compose_keycloak, docker_compose_valkey [EXTRACTED 0.90]

## Communities (38 total, 8 thin omitted)

### Community 0 - "rbac_sync/__init__.py"
Cohesion: 0.06
Nodes (63): datetime, fetch_all_roles_with_attrs(), has_events(), Check if any event matches the given resource and operation types., Fetch all roles with their attributes from the given realm (defaults to…, _is_api_path(), push_routes_to_caddy(), Caddy Route Generation module. Handles generating Caddy deny rules from… (+55 more)

### Community 1 - "ConciergeOS Docker Setup"
Cohesion: 0.06
Nodes (57): Docker Compose, Backend Service, Caddy Service, Client Backend Service, Frontend Service, Keycloak Service, OAuth2 Proxy (Frontend), OAuth2 Proxy (Backend API) (+49 more)

### Community 2 - "test_valkey_session.py"
Cohesion: 0.07
Nodes (40): Session, _clear_sync_checkpoint(), Clear the Valkey sync timestamp and disable sync_is_current() so initial_sync()…, cleanup_user(), count_oauth2_proxy_sessions(), DockerExecValkeyClient, ensure_test_user(), get_valkey_client() (+32 more)

### Community 3 - "helpers.py"
Cohesion: 0.07
Nodes (30): build_caddy_routes(), generate_deny_rules(), get_menus_for_roles(), _load_fallback_roles(), Aggregate menu items for a set of role names. Args: role_names: Set of role…, Build the full internal-server routes array. Combines static assets route, full…, Load role path/menus from rbac_routes.json as fallback. Returns: Dictionary…, Generate Caddy deny rules from role attributes fetched from Keycloak. Each… (+22 more)

### Community 4 - "test_rbac_routes_to_keycloak.py"
Cohesion: 0.07
Nodes (35): get_role_by_name(), Return role data dict if found, else None., create_role_with_attributes(), delete_role(), Response, Delete a role by name. Returns the raw Response. Args: token: Keycloak admin…, Create a new role with paths, menus, and message attributes. Args: token: Admin…, Update an existing role's paths, menus, and message attributes. Args: token:… (+27 more)

### Community 5 - "RBACRoutes"
Cohesion: 0.07
Nodes (28): BaseModel, load_rbac_routes(), load_role_definitions(), load_role_descriptions(), Path, Shared RBAC utilities for ConciergeOS. This module provides common functions…, Load role definitions from RBAC routes file. Args: routes_path: Path to the…, Load role names with human-readable descriptions from RBAC routes file. This is… (+20 more)

### Community 6 - "has_role_events"
Cohesion: 0.14
Nodes (10): has_role_events(), Check if any event is a role-related admin event. Args: events: List of admin…, VIEW on ROLE should NOT trigger re-sync., TestHasRoleEvents, live_token(), fixture, poll_and_sync() runs without exceptions (hits live Keycloak + Caddy)., Get a live authentication token. (+2 more)

### Community 7 - "kc_request"
Cohesion: 0.13
Nodes (22): fetch_all_roles(), kc_request(), Response, Make an authenticated request to the Keycloak Admin API. Args: method: HTTP…, Fetch all role names in the given realm (defaults to settings.KEYCLOAK_REALM)., create_realms(), _ensure_events_enabled(), get_realm_config() (+14 more)

### Community 8 - "TestYAMLPersistence"
Cohesion: 0.09
Nodes (12): Should create a JSON file if it doesn't exist., Should write roles in sorted order., Should handle roles without message., Test the full sync function with live Keycloak., Tests for load_existing_rbac_routes and related functions., Should return empty dict when file doesn't exist., Should parse a valid JSON file., Should return empty dict for empty JSON file. (+4 more)

### Community 9 - ".KEYCLOAK_REALM"
Cohesion: 0.14
Nodes (12): fetch_events_with_params(), get_realm_events(), Fetch realm events with custom query parameters. Returns the raw Response…, Fetch realm admin events for a date range. Args: token: Keycloak admin token…, poll_admin_events should return a list (possibly empty)., Keycloak 26 requires yyyy-MM-dd date format. This test verifies the fix by: 1.…, Verify yyyy-MM-dd format works (the fix)., Verify type=ADMIN is NOT sent (Keycloak 26 rejects it). (+4 more)

### Community 10 - "Any"
Cohesion: 0.14
Nodes (10): parametrize, Any, Both endpoints return the same set of keys., All discovery endpoints must start with https://out-customer.com., No endpoint in the discovery response contains internal Docker hostnames., Discovery endpoint reachable through Caddy → Keycloak proxy., Discovery endpoint reachable directly on localhost:8080., TestAuthorizationEndpoint (+2 more)

### Community 11 - "settings.py"
Cohesion: 0.15
Nodes (10): authenticate(), Authenticate as admin to the master realm and return access token., list_roles(), Fetch all role names in the given realm. Args: token: Keycloak admin token…, Authenticate against live Keycloak and verify we get a token., Verify the token can access the admin API., Fetch roles from live Keycloak — should return at least our defined roles., Keycloak always creates uma_authorization. (+2 more)

### Community 12 - "fixtures.py"
Cohesion: 0.19
Nodes (15): compose_issuer_url(), compose_redis_connection_url(), compose_session_store_type(), compose_ssl_insecure_skip_verify(), discovery_config_direct(), discovery_config_public(), Any, Extract OAUTH2_PROXY_OIDC_ISSUER_URL from the docker-compose.yaml environment. (+7 more)

### Community 13 - "roles.py"
Cohesion: 0.20
Nodes (14): get_composite_roles(), get_roles(), _load_roles_from_mapping(), Load role definitions from the RBAC mapping file. Reads the RBAC routes file…, Get role definitions, loading from YAML if available., Get composite role definitions., create_all_roles(), create_composite_role() (+6 more)

### Community 15 - "test_event_persistence.py"
Cohesion: 0.12
Nodes (6): Return a list of mock Keycloak admin events., Flush all role_sync:* keys from Valkey before and after each test. Gracefully…, sample_events(), _valkey_flush(), TestCollectEventIds, TestSyncTimestamp

### Community 16 - "keycloak_diagnose.py"
Cohesion: 0.22
Nodes (13): authenticate(), get_base_url(), get_user_groups(), list_clients(), list_groups(), list_realms(), list_users(), main() (+5 more)

### Community 17 - "summary.py"
Cohesion: 0.22
Nodes (12): authenticate(), Authenticate as admin to the master realm and return access token., get_actual_client_secret(), get_client_api_secret(), Get the concierge client secret., Get the client-api service secret., main(), print_summary() (+4 more)

### Community 18 - "keycloak_setup/__init__.py"
Cohesion: 0.23
Nodes (12): create_all_client_apis(), create_all_clients(), create_client(), create_client_api(), _create_client_in_realm(), Create the conciergeos client in a realm. Returns the client UUID. Keycloak 26…, Create the client-api service client (Client Credentials Grant). Returns…, Create clients in all realms. Returns {realm: client_uuid}. (+4 more)

### Community 19 - "fixture"
Cohesion: 0.18
Nodes (11): compose_content(), json_file(), fixture, Read docker-compose.yaml once per session., Generate a unique test role name., Sample RBAC routes JSON content for testing., Sample Caddy config that simulates a real config with multiple servers., Create a temporary JSON file with sample RBAC content. (+3 more)

### Community 20 - "TestSignInRedirect"
Cohesion: 0.25
Nodes (6): Hit /oauth2/start and return the redirect Location header., Hitting /oauth2/start must redirect (302) to Keycloak's authorization endpoint., The redirect Location must NOT contain internal Docker hostnames., The redirect Location must point to Keycloak's authorization endpoint., The redirect Location must start with https://out-customer.com., TestSignInRedirect

### Community 21 - "conftest.py"
Cohesion: 0.27
Nodes (9): Create or update a role with paths and menus attributes. If the role exists,…, upsert_role_with_attributes(), live_test_role(), live_token(), fixture, Create a real role in Keycloak with paths/menus attributes for integration…, Authenticate against the live Keycloak instance once per session. Uses the…, Sample Caddy config that simulates a real config with multiple servers. (+1 more)

### Community 22 - "TestPersistenceFlow"
Cohesion: 0.20
Nodes (5): Cycle 1: all events new. Cycle 2: all events seen., Some events already seen, some new., After save_sync_timestamp, sync_is_current is True., When no checkpoint, sync_is_current is False., TestPersistenceFlow

### Community 23 - "TestParseRbacRoutes"
Cohesion: 0.20
Nodes (6): Test that parsing a nonexistent file raises an error., Tests for parse_rbac_routes function., Test parsing a basic JSON file., Test parsing JSON where message is optional., Test parsing JSON where paths is optional., TestParseRbacRoutes

### Community 24 - "update_oidc_configs"
Cohesion: 0.31
Nodes (8): _find_env_file(), Find the docker .env file. Searches: 1. Same directory as this script 2. Parent…, Update OIDC_CLIENT_SECRET in the .env file in place., Update CLIENT_API_CLIENT_SECRET in the .env file in place., Print and automatically update the Keycloak client secrets in .env files.…, _update_env_file(), _update_env_file_client_api(), update_oidc_configs()

### Community 25 - "TestPushRoutesToCaddyConfigPreservation"
Cohesion: 0.22
Nodes (4): Verify the config manipulation preserves structure., Verify _push_routes_to_caddy uses requests.patch, not requests.put., Verify _push_routes_to_caddy fetches current config before pushing., TestPushRoutesToCaddyConfigPreservation

### Community 29 - "TestRBACRoutesFileConstant"
Cohesion: 0.33
Nodes (4): Tests for RBAC_ROUTES_FILE constant., RBAC_ROUTES_FILE should point to an existing file., RBAC_ROUTES_FILE should be in the docker directory., TestRBACRoutesFileConstant

### Community 30 - "assignments.py"
Cohesion: 0.50
Nodes (4): assign_all_users_to_roles(), assign_user_to_roles(), Assign a user to realm roles., Assign all users to their respective roles in all realms.

### Community 31 - "claims.py"
Cohesion: 0.50
Nodes (4): configure_all_role_claims(), configure_role_claim(), Ensure realm roles are included in the access token. Roles are included in the…, Configure role claim for all realms.

## Knowledge Gaps
- **35 isolated node(s):** `Services`, `Access Control Flow`, `Roles`, `Environment Configuration`, `Build images` (+30 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `kc_request()` connect `kc_request` to `rbac_sync/__init__.py`, `test_rbac_routes_to_keycloak.py`, `.KEYCLOAK_REALM`, `settings.py`, `roles.py`, `keycloak_setup/__init__.py`, `conftest.py`, `assignments.py`, `claims.py`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Why does `authenticate()` connect `summary.py` to `rbac_sync/__init__.py`, `test_rbac_routes_to_keycloak.py`, `has_role_events`, `kc_request`, `conftest.py`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Why does `TestYAMLPersistence` connect `TestYAMLPersistence` to `rbac_sync/__init__.py`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **What connects `Services`, `Access Control Flow`, `Roles` to the rest of the system?**
  _35 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `rbac_sync/__init__.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05516475379489078 - nodes in this community are weakly interconnected._
- **Should `ConciergeOS Docker Setup` be split into smaller, more focused modules?**
  _Cohesion score 0.05513784461152882 - nodes in this community are weakly interconnected._
- **Should `test_valkey_session.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06516290726817042 - nodes in this community are weakly interconnected._