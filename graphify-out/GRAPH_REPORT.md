# Graph Report - .  (2026-08-05)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 2793 nodes · 4768 edges · 229 communities (203 shown, 26 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 415 edges (avg confidence: 0.62)
- Token cost: 26,305 input · 23,568 output

## Graph Freshness
- Built from commit: `80fcab40`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- types/index.ts
- BookingSource
- PerformanceTesting/__init__.py
- PromptGroups.tsx
- ui/index.ts
- helpers.py
- ReservationStatus
- rbac_sync/__init__.py
- performance_testing.py
- roles.py
- keycloak_setup/__init__.py
- ConciergeOS Docker Setup
- routes_persistence.py
- PromptStore
- routes/prompts.py
- Phase 4: Frontend Components
- App.tsx
- routes/models.py
- Database Population Guide
- fixtures.py
- ModelManager.tsx
- execute_chain
- KeycloakClient
- kc_request
- authenticate
- has_role_events
- Settings
- PerformanceTesting.tsx
- placeholders.py
- client_backend/main.py
- compilerOptions
- TestYAMLPersistence
- ConciergeOS
- test_pure_functions.py
- Tasks
- setup_performance_test_guests
- _fetch_and_save
- ValidationModal.tsx
- compilerOptions
- shift_reservations_service
- create_collision_reservations
- PromptScheduler
- LLM Model Management — Multi-Model Support with Prompt-Level Assignment
- prompt_groups.py
- debug.py
- response_cache.py
- Any
- Any
- react
- .__call__
- app/config.py
- setup_errors.py
- Settings
- test_oidc_config.py
- Graphify — Codebase Graph Extraction & Navigation
- devDependencies
- Session
- generator_utils.py
- llm.py
- HttpCacheEntry
- ConciergeOS Backend
- TestLiveKeycloakEvents
- test_keycloak_auth.py
- JSONResponse
- Frontend Development Guide
- prompt_builders.py
- execute_chain_step_route
- guest_extraction.py
- utils.py
- keycloak_diagnose.py
- CompareModal.tsx
- BaseCacheEntry
- ReservationResponse
- Implementation Spec: Prompt Chain Pages
- api_extract_name
- BaseCacheStore
- README.md
- Client Backend — Dummy Service-to-Service Client
- build_caddy_routes
- 23. Implementation Extensions & Deviations
- 2. Implementation Checklist
- populate_rooms.py
- PerformanceTestLogger
- Backend Development Guide
- TestSignInRedirect
- 7. Background Scheduler
- detect_errors
- Database Impact Analysis & Permission Requirements
- TestPersistenceFlow
- TestParseRbacRoutes
- Versioned Prompt System — Implementation Plan
- Role-Based Access Control (RBAC) — Architecture & Implementation
- plugins
- package.json
- FastAPI
- _get_http_cache
- update_oidc_configs
- TestPushRoutesToCaddyConfigPreservation
- Differences from Plan
- 6.1 Database Models
- 5. Component Reference
- 7. Trade-offs & Limitations
- 1.5 Multimodal Name Extraction
- server.js
- Quick Start Guide
- dae900574783_add_prompt_versions_table.py
- Caddy Reverse Proxy Service
- 3. Authorization Flow
- 4. Phase 2: Chain Execution Engine
- 8. Design Decisions
- Prompt Versioning System
- sample_caddy_config
- TestSeenIds
- TestFilterNewEvents
- TestSyncTimestamp
- 4. LLM Integration & Prompt Resolution
- 8. API Reference
- Architecture
- dependencies
- GroupedDataTable.tsx
- MultiSortTable.tsx
- _run_tool_calling_loop
- 🔌 API Endpoints
- batch_runners.py
- TestRBACRoutesFileConstant
- For the Keycloak Administrator
- 8. Testing Plan
- 1. Overview & Architecture
- 6. Phase 4: Frontend Components
- sync_all_roles
- PromptImprovementChat.tsx
- env.py
- 5970a2463784_add_is_active_column_to_promptgroup.py
- 64e9fa0ce73b_add_schedule_type_to_promptgroupschedule.py
- a782e25476e4_add_prompt_group_tables.py
- DockerExecValkeyClient
- get_tool_calling_info
- role-sync service
- backend_post
- generate_rooms.py
- 23.3 Extended API Endpoints
- 23.7 Response Cache — Model-Aware Caching & Diagnostics
- 5. Phase 1: Backend Database Changes
- 8. Phase 4: Backend LLM Routing
- Phase 10: Frontend — Integration Pages
- Backend — PromptStore Service
- 11. File Map
- ConciergeOS — Prompting System Implementation Reference
- 3. Placeholder System
- 5. Response Caching
- 4. Role Naming Convention
- 3.1 Files Modified
- 5. Phase 3: Frontend Types & API Client
- d3f04a295bc8_add_hotel_tables_rooms_guests_.py
- _prompt_to_schema
- query_guest_with_llm
- shift_reservations.py
- run_script
- run_script
- run_script
- Debugging & Extraction via Temporary Files
- TestCollectEventIds
- 10. Phase 6: Backend Response Cache
- 16. Phase 12: Frontend Settings Page
- 21. Testing
- 3. Architecture & Data Model
- Backend — Schemas
- Backend — LLM Integration
- Frontend — API Client
- 10. Initialization & Seeding
- 9. Frontend API Clients
- Appendix C: File Change Summary
- Reusable Prompt: Generate Slidev Presentation from Git Branch Analysis
- React + TypeScript + Vite
- ✨ Key Features
- PromptGroupItem
- 14. Phase 10: Frontend Types
- 18. Phase 14: Frontend Prompt UI
- 19. Phase 15: Frontend Guest Search Integration
- 22. Migration Notes
- 2. Problem Statement & Design Rationale
- 6. Phase 2: Backend Schemas
- 7. Phase 3: Backend Model CRUD Routes
- 9. Phase 5: Backend Guest Extraction
- Phase 11: Migration & Polish
- tsconfig.json
- backend/__init__.py
- client_backend/__init__.py
- 04-questions-about-codebase.md
- install-cert-linux.sh
- install-cert-macos.sh
- Backend API
- ConciergeOS Backend Overview
- Graphify
- Performance Dashboard
- Prompt Chain Pages
- Keycloak Token Endpoint
- Pytest
- UV
- Uvicorn
- conciergeos
- _group_with_relations
- live_token
- _classify_response
- 9. Migration Guide
- create_openai_client
- _generate_guest_information
- _generate_schema_from_database
- .resolve_vllm_url

## God Nodes (most connected - your core abstractions)
1. `ReservationStatus` - 72 edges
2. `BookingSource` - 66 edges
3. `Reservation` - 62 edges
4. `react` - 53 edges
5. `kc_request()` - 36 edges
6. `PromptStore` - 33 edges
7. `request()` - 29 edges
8. `LLM Model Management — Multi-Model Support with Prompt-Level Assignment` - 26 edges
9. `ConciergeOS` - 23 edges
10. `poll_and_sync()` - 22 edges

## Surprising Connections (you probably didn't know these)
- `ConciergeOS` --references--> `Alembic`  [EXTRACTED]
  README.md → backend/README.md
- `ConciergeOS` --references--> `APScheduler`  [EXTRACTED]
  README.md → backend/README.md
- `ConciergeOS` --references--> `FastAPI`  [EXTRACTED]
  README.md → backend/README.md
- `ConciergeOS` --references--> `OpenAI SDK`  [EXTRACTED]
  README.md → backend/README.md
- `ConciergeOS` --references--> `SQLAlchemy`  [EXTRACTED]
  README.md → backend/README.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Docker Deployment Infrastructure** — docker_docker_compose_caddy, docker_docker_compose_keycloak, docker_docker_compose_oauth2_proxy, docker_docker_compose_role_sync, docker_docker_compose_valkey, docker_docker_compose_backend, docker_docker_compose_frontend, docker_docker_compose_client_backend [EXTRACTED 0.95]

## Communities (229 total, 26 thin omitted)

### Community 0 - "types/index.ts"
Cohesion: 0.05
Nodes (54): BatchLegend(), getBatchColor(), hashString(), PerformanceChart(), PerformanceChartProps, PerformanceChartWithTogglesProps, TooltipEntry, SettingsContext (+46 more)

### Community 1 - "BookingSource"
Cohesion: 0.05
Nodes (90): BookingSource, Where a reservation was created / booked from., Maps to the Reservations table. Set __expose_in_prompt__ = True to include this…, Reservation, ChainExecutionRequest, ChainExecutionResultSchema, ChainStepRequest, ChainStepResponse (+82 more)

### Community 2 - "PerformanceTesting/__init__.py"
Cohesion: 0.17
Nodes (18): ensure_database(), get_next_run_id(), init_database(), Connection, Path, Create the performance_tests database schema and return a connection. The table…, Create the database schema if it does not exist. A convenience helper for…, Return the next auto-incremented run_id. (+10 more)

### Community 3 - "PromptGroups.tsx"
Cohesion: 0.06
Nodes (59): CloneSectionModal(), CloneSectionModalProps, CreatePromptModal(), CreatePromptModalProps, PageHeader(), PageHeaderProps, PromptSettingsPanelProps, Select() (+51 more)

### Community 4 - "ui/index.ts"
Cohesion: 0.06
Nodes (38): Badge(), BadgeProps, BadgeVariant, variantClasses, Button(), ButtonProps, ButtonSize, ButtonVariant (+30 more)

### Community 5 - "helpers.py"
Cohesion: 0.09
Nodes (33): cleanup_user(), count_oauth2_proxy_sessions(), ensure_test_user(), get_valkey_client(), list_oauth2_proxy_sessions(), oauth2_login_flow(), Session, Connect to the live Valkey instance. Tries direct connection first, falls back… (+25 more)

### Community 6 - "ReservationStatus"
Cohesion: 0.10
Nodes (38): Base, Base class for all ORM models., BookingChannel, Allowed booking channel types for rooms., Lifecycle statuses for reservations., ReservationStatus, Guest, LLMModel (+30 more)

### Community 7 - "rbac_sync/__init__.py"
Cohesion: 0.08
Nodes (48): fetch_all_roles_with_attrs(), has_events(), Check if any event matches the given resource and operation types., Fetch all roles with their attributes from the given realm (defaults to…, push_routes_to_caddy(), Caddy Route Generation module. Handles generating Caddy deny rules from…, Push the updated routes to Caddy via the Admin API. Args: routes: List of route…, Read current routes from Caddy for verification/debugging. Returns: List of… (+40 more)

### Community 8 - "performance_testing.py"
Cohesion: 0.06
Nodes (55): api_check_duplicate_test_guests(), api_delete_batch(), api_generate_xml(), api_get_all_performance_results(), api_get_guest_detail(), api_get_performance_batches(), api_get_performance_results(), api_get_performance_stats() (+47 more)

### Community 9 - "roles.py"
Cohesion: 0.09
Nodes (28): get_role_by_name(), Return role data dict if found, else None., create_composite_role(), create_role(), create_role_with_attributes(), print_summary(), Create a realm role. Returns the role name (Keycloak roles are identified by…, Create a composite role that inherits from the given composite roles. (+20 more)

### Community 10 - "keycloak_setup/__init__.py"
Cohesion: 0.10
Nodes (36): assign_all_users_to_roles(), assign_user_to_roles(), Assign a user to realm roles., Assign all users to their respective roles in all realms., configure_all_role_claims(), configure_role_claim(), Ensure realm roles are included in the access token. Roles are included in the…, Configure role claim for all realms. (+28 more)

### Community 11 - "ConciergeOS Docker Setup"
Cohesion: 0.05
Nodes (41): Accepted tradeoff, Access Control Flow, Accessing the Application, Architecture, Build images, Build & Start, Certificate not trusted, Certificate persistence (+33 more)

### Community 12 - "routes_persistence.py"
Cohesion: 0.07
Nodes (33): load_rbac_routes(), load_role_definitions(), load_role_descriptions(), Path, Shared RBAC utilities for ConciergeOS. This module provides common functions…, Load role definitions from RBAC routes file. Args: routes_path: Path to the…, Load role names with human-readable descriptions from RBAC routes file. This is…, Write role configurations to an RBAC routes JSON file. Args: routes_path: Path… (+25 more)

### Community 13 - "PromptStore"
Cohesion: 0.07
Nodes (26): delete_version(), delete, patch, Set a specific version as the default., set_default_version(), build_system_prompt(), PromptStore, Any (+18 more)

### Community 14 - "routes/prompts.py"
Cohesion: 0.16
Nodes (22): PromptVersion, Maps to the prompt_versions table. Each prompt is identified by a unique…, ai_improve_prompt(), AiImproveRequest, AiImproveResponse, ChatMessage, create_version(), CreatePromptRequest (+14 more)

### Community 15 - "Phase 4: Frontend Components"
Cohesion: 0.06
Nodes (33): 1.1 — Backend: Add aggregated stats endpoint, 1.1 — Backend: Datetime parsing improvement, 2.1 — Frontend: Add PerformanceStats type, 3.1 — Frontend: Add getPerformanceStats to api.ts, 4.10 — Frontend: Create useSelectionState hook, 4.1 — Frontend: Create PerformanceChart component, 4.1 — PerformanceChart: Enhanced beyond original spec, 4.2 — Frontend: Export PerformanceChart from ui index (+25 more)

### Community 16 - "App.tsx"
Cohesion: 0.12
Nodes (25): App(), fetchMe(), Header(), MENU_TO_PATH, MeResponse, ChainOutputSection(), ChainStepStatus(), ChainPagesContext (+17 more)

### Community 17 - "routes/models.py"
Cohesion: 0.10
Nodes (28): create_model(), delete_model(), fetch_info_by_url(), fetch_model_info(), _fetch_remote_model_info(), get_model(), list_models(), Any (+20 more)

### Community 18 - "Database Population Guide"
Cohesion: 0.07
Nodes (29): 1.1 Name Generation, 1.2 Room Generation, 2.1 Populate Rooms, 2.2 Populate Guests and Reservations, 2.3 (Optional) Setup Performance Test Guests, 2.4 Seed Prompt Versions, 3.1 Inject Controlled Errors, Booking Source Rules (+21 more)

### Community 19 - "fixtures.py"
Cohesion: 0.10
Nodes (27): compose_content(), compose_redis_connection_url(), compose_session_store_type(), compose_ssl_insecure_skip_verify(), json_file(), fixture, Read docker-compose.yaml once per session., Extract OAUTH2_PROXY_SSL_INSECURE_SKIP_VERIFY from docker-compose.yaml. (+19 more)

### Community 20 - "ModelManager.tsx"
Cohesion: 0.17
Nodes (11): MODEL_TYPE_OPTIONS, ModelManager(), ModelManagerProps, PerformancePromptSelector(), PerformancePromptSelectorProps, PromptSelector(), PromptSelectorProps, PromptSettingsPanel() (+3 more)

### Community 21 - "execute_chain"
Cohesion: 0.15
Nodes (25): _build_aliases_map(), _build_step_result(), _call_llm(), _ensure_results_dir(), execute_chain(), execute_chain_step(), _execute_single_step(), _load_group_and_items() (+17 more)

### Community 22 - "KeycloakClient"
Cohesion: 0.10
Nodes (15): KeycloakClient, Response, Keycloak OAuth2 Client — Client Credentials Grant Flow. This module handles…, Return a valid access token, refreshing if necessary., Force-fetch a new token (ignores the cached one)., Minimally decode the JWT payload (middle segment) without crypto. This is for…, Return human-readable information about the current token., Make an authenticated request to the main backend service. The access token is… (+7 more)

### Community 23 - "kc_request"
Cohesion: 0.08
Nodes (33): fetch_all_roles(), kc_request(), Response, Make an authenticated request to the Keycloak Admin API. Args: method: HTTP…, Fetch all role names in the given realm (defaults to settings.KEYCLOAK_REALM)., fetch_events_with_params(), get_realm_events(), Fetch realm events with custom query parameters. Returns the raw Response… (+25 more)

### Community 24 - "authenticate"
Cohesion: 0.10
Nodes (22): authenticate(), Authenticate as admin to the master realm and return access token., delete_role(), Response, Delete a role by name. Returns the raw Response. Args: token: Keycloak admin…, _clear_sync_checkpoint(), live_test_role(), live_token() (+14 more)

### Community 25 - "has_role_events"
Cohesion: 0.15
Nodes (7): has_role_events(), Check if any event is a role-related admin event. Args: events: List of admin…, VIEW and LOGIN should not trigger a re-sync., VIEW on ROLE should NOT trigger re-sync., TestHasRoleEvents, TestRoleEventTypes, TestHasRoleEvents

### Community 26 - "Settings"
Cohesion: 0.09
Nodes (6): Main entry point for the sync service., run_sync_service(), main(), Main entry point for the role sync service., Environment-based configuration with sensible defaults. All attributes are read…, Settings

### Community 27 - "PerformanceTesting.tsx"
Cohesion: 0.08
Nodes (30): StatusBanner(), StatusBannerProps, styleMap, useSettings(), BatchListProps, DataFormatCard(), DataFormatCardProps, formatDuration() (+22 more)

### Community 28 - "placeholders.py"
Cohesion: 0.10
Nodes (21): _get_db_schema(), _get_exposed_tables(), Generate a schema description by introspecting exposed database tables. Only…, Generate a list of all guests in the database for context., Generate a list of all hotel rooms., Generate high-level hotel statistics., Return today's date in ISO format., Generate human-readable description of available database query tools. (+13 more)

### Community 29 - "client_backend/main.py"
Cohesion: 0.13
Nodes (22): _authenticate_admin(), backend_health(), backend_models(), backend_settings(), _extract_roles(), _fetch_roles_with_attrs(), _get_menus_for_roles(), health() (+14 more)

### Community 30 - "compilerOptions"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+14 more)

### Community 31 - "TestYAMLPersistence"
Cohesion: 0.09
Nodes (12): Should create a JSON file if it doesn't exist., Should write roles in sorted order., Should handle roles without message., Test the full sync function with live Keycloak., Tests for load_existing_rbac_routes and related functions., Should return empty dict when file doesn't exist., Should parse a valid JSON file., Should return empty dict for empty JSON file. (+4 more)

### Community 32 - "ConciergeOS"
Cohesion: 0.09
Nodes (22): Alembic, APScheduler, Caddy, FastAPI, Keycloak, Node.js, oauth2-proxy, OpenAI SDK (+14 more)

### Community 33 - "test_pure_functions.py"
Cohesion: 0.19
Nodes (10): generate_deny_rules(), get_menus_for_roles(), Generate Caddy deny rules from role attributes fetched from Keycloak. Each…, Aggregate menu items for a set of role names. Args: role_names: Set of role…, make_roles_with_attrs(), Build a roles_with_attrs dict for testing. Usage: roles =…, Verify message from role name is used in the deny rule., Verify the deny rule structure uses header_regexp with X-Forwarded-Groups. (+2 more)

### Community 34 - "Tasks"
Cohesion: 0.10
Nodes (21): 1.1 — Add `PromptVersion` model to `app/models.py`, 2.1 — Add prompt schemas to `app/schemas.py`, 3.1 — Create `app/services/prompts.py`, 4.1 — Create `app/routes/prompts.py`, 5.1 — Wire up routes in `app/main.py` and `app/routes/__init__.py`, 5.2 — Modify `app/services/llm.py`, 6.1 — Create `frontend/src/types/prompt.ts`, 7.1 — Create `frontend/src/services/promptsApi.ts` (+13 more)

### Community 35 - "setup_performance_test_guests"
Cohesion: 0.12
Nodes (21): generate_random_dob(), get_bucket_dates(), Generate a random date of birth string (ISO format) for a person aged 18-80., Return (check_in_date, check_out_date, status) for a given bucket. Uses the…, delete_duplicate_test_guests(), delete_performance_test_guests(), find_duplicate_test_guests(), insert_reservation() (+13 more)

### Community 36 - "_fetch_and_save"
Cohesion: 0.18
Nodes (15): dataset_refresh(), _fetch_and_save(), _fetch_raw_data(), _get_cached_dataset(), Any, Path, Fetch all guests, rooms, and reservations from the database. Returns structured…, Helper to ensure directory exists and write content to file. (+7 more)

### Community 37 - "ValidationModal.tsx"
Cohesion: 0.13
Nodes (8): GuestComparisonView(), GuestComparisonViewProps, formatJson(), JsonPanel(), JsonPanelProps, ValidationModal(), ValidationModalProps, SingleGuestValidation

### Community 38 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, noEmit, noFallthroughCasesInSwitch (+11 more)

### Community 39 - "shift_reservations_service"
Cohesion: 0.22
Nodes (9): api_shift_reservations(), post, Session, ShiftRequest, Shift all reservation dates forward/backward by the specified number of days., Session, ShiftResponse, Shift all reservation check_in and check_out dates by a given number of days… (+1 more)

### Community 40 - "create_collision_reservations"
Cohesion: 0.19
Nodes (16): booking_channel_to_source(), Determine booking_source based on room's allowed_booking_channel., Split a full name string into (first_name, last_name)., split_name(), create_collision_reservations(), insert_guest(), insert_reservation(), load_names() (+8 more)

### Community 41 - "PromptScheduler"
Cohesion: 0.13
Nodes (10): PromptScheduler, datetime, Cancel a scheduled job by its database schedule_id., Callback invoked by APScheduler to run a prompt chain. Checks if the group is…, Save active job info to JSON for recovery after restart., On startup: reload pending schedules from the database. Re-schedules any active…, Background scheduler for prompt group chain executions., Start the scheduler and recover persisted schedules. (+2 more)

### Community 42 - "LLM Model Management — Multi-Model Support with Prompt-Level Assignment"
Cohesion: 0.11
Nodes (19): 11.1 Model Resolution per Step, 11. Phase 7: Backend Prompt Chain, 12.1 Model Resolution in Performance Testing, 12. Phase 8: Backend Performance Testing, 13.1 Current State of `backend/app/config.py`, 13. Phase 9: Backend Config Deprecation, 15.1 Add Model CRUD Methods, 15.2 Update `promptsApi.ts` (+11 more)

### Community 43 - "prompt_groups.py"
Cohesion: 0.22
Nodes (14): create_group(), get_group(), _group_to_schema(), patch, PromptGroup, Convert a PromptGroup ORM object to the response schema., Create a new prompt group with optional items., Get a single prompt group with all details. (+6 more)

### Community 44 - "debug.py"
Cohesion: 0.15
Nodes (17): cleanup_expired_http_cache(), clear_all_caches(), clear_http_cache(), clear_llm_cache(), post, ShiftRequest, ShiftResponse, Clear the LLM response cache. (+9 more)

### Community 45 - "response_cache.py"
Cohesion: 0.15
Nodes (17): cache_clear(), cache_stats(), CacheStore, call_llm_with_db_tools(), call_llm_with_db_tools_with_cache_flag(), generate_cache_key(), _get_cache(), In-memory LLM response cache with TTL-based expiration. Single-process use.… (+9 more)

### Community 46 - "Any"
Cohesion: 0.16
Nodes (17): execute_get_hotel_summary(), execute_query_guest_with_reservations(), execute_query_guests(), execute_query_reservations(), execute_query_rooms(), _format_guest(), _format_reservation(), Any (+9 more)

### Community 47 - "Any"
Cohesion: 0.14
Nodes (10): Any, Both endpoints return the same set of keys., All discovery endpoints must start with https://out-customer.com., No endpoint in the discovery response contains internal Docker hostnames., Discovery endpoint reachable through Caddy → Keycloak proxy., Discovery endpoint reachable directly on localhost:8080., TestAuthorizationEndpoint, TestDiscoveryEndpointReachable (+2 more)

### Community 48 - "react"
Cohesion: 0.07
Nodes (29): ChainInputSection(), ChainInputSectionProps, ChartWithLegendProps, FormField(), FormFieldProps, Input, InputProps, PromptTextareaProps (+21 more)

### Community 49 - ".__call__"
Cohesion: 0.16
Nodes (9): HttpCacheMiddleware, Captures response body from a streaming response., ASGI middleware that caches GET responses by URI + query parameters. - Only…, _StreamingResponseCapture, generate_http_cache_key(), Generate a SHA256 cache key from an HTTP URL. Parses the URL and normalizes…, Receive, Scope (+1 more)

### Community 50 - "app/config.py"
Cohesion: 0.15
Nodes (11): AppConfig, ConfigManager, setter, Configuration settings for LLM model configuration., Global application configuration., Manages persistent application configuration via a JSON file., Loads configuration from the JSON file or returns defaults., Persists the current configuration to the JSON file. (+3 more)

### Community 51 - "setup_errors.py"
Cohesion: 0.21
Nodes (14): apply_errors(), ErrorRecord, fetch_collision_reservation_ids(), fetch_reservation_details(), main(), print_results(), Any, date (+6 more)

### Community 52 - "Settings"
Cohesion: 0.12
Nodes (9): Configuration for the client backend service. Reads environment variables with…, Environment-based configuration for the client backend., Keycloak base URL (e.g. http://keycloak:8080/auth)., Keycloak admin username for Admin API access., Keycloak admin password for Admin API access., The OAuth2 client_id registered in Keycloak for this service., The OAuth2 client_secret for this service. Must be set., URL of the main backend service to call. (+1 more)

### Community 53 - "test_oidc_config.py"
Cohesion: 0.12
Nodes (9): compose_issuer_url(), discovery_config_direct(), discovery_config_public(), Any, Extract OAUTH2_PROXY_OIDC_ISSUER_URL from the docker-compose.yaml environment., Fetch the OIDC discovery config via the public HTTPS domain (Caddy proxy)., Fetch the OIDC discovery config directly on localhost:8080., TestComposeIssuerURL (+1 more)

### Community 54 - "Graphify — Codebase Graph Extraction & Navigation"
Cohesion: 0.12
Nodes (17): 1. Overview, 2. Output Structure, 3.1 Extraction, 3.2 Querying, 3.3 Navigation, 3. Commands, 4. Graph Freshness, 5. Integration with AI Assistants (+9 more)

### Community 55 - "devDependencies"
Cohesion: 0.11
Nodes (19): devDependencies, oxlint, tailwindcss, @tailwindcss/vite, @types/node, @types/react, @types/react-dom, typescript (+11 more)

### Community 56 - "Session"
Cohesion: 0.20
Nodes (17): _cancel_active_schedules(), cancel_schedule(), clear_schedules(), delete_group(), get_results(), delete, put, Session (+9 more)

### Community 57 - "generator_utils.py"
Cohesion: 0.25
Nodes (13): classify_reservation_type(), _coerce_date(), is_checked_in_type(), is_checked_out_type(), is_confirmed_type(), date, Pick a bucket key (1-4) using defined weights., Convert a date string or date object to a date object. (+5 more)

### Community 58 - "llm.py"
Cohesion: 0.22
Nodes (16): _build_client_from_model(), _get_base_client(), get_llm_config(), get_llm_config_by_model_id(), get_llm_config_by_name(), _get_shared_http_client(), OpenAI, Return a module-level singleton httpx.Client with connection pooling. Created… (+8 more)

### Community 59 - "HttpCacheEntry"
Cohesion: 0.15
Nodes (9): HttpCacheEntry, HttpCacheStore, Initialize the cache store. Args: ttl: Time-to-live in seconds (default 3600 =…, Get a cached entry by key. Returns None if expired., A single cached HTTP response with expiration tracking., In-memory HTTP response cache with TTL-based expiration. Stores full HTTP…, Initialize the HTTP cache store. Args: ttl: Time-to-live in seconds (default…, Get a cached HTTP response entry by key. Returns None if expired. (+1 more)

### Community 60 - "ConciergeOS Backend"
Cohesion: 0.12
Nodes (16): 📖 API Documentation, ConciergeOS Backend, ⚙️ Configuration, 🧬 Data Generation, 🗄️ Database, Database Setup, Generate Initial Data, Installation (+8 more)

### Community 61 - "TestLiveKeycloakEvents"
Cohesion: 0.22
Nodes (5): poll_admin_events should return a list (possibly empty)., Keycloak 26 requires yyyy-MM-dd date format. This test verifies the fix by: 1.…, Verify yyyy-MM-dd format works (the fix)., Verify type=ADMIN is NOT sent (Keycloak 26 rejects it)., TestLiveKeycloakEvents

### Community 62 - "test_keycloak_auth.py"
Cohesion: 0.16
Nodes (10): authenticate(), Authenticate as admin to the master realm and return access token., list_roles(), Fetch all role names in the given realm. Args: token: Keycloak admin token…, Authenticate against live Keycloak and verify we get a token., Verify the token can access the admin API., Fetch roles from live Keycloak — should return at least our defined roles., Keycloak always creates uma_authorization. (+2 more)

### Community 63 - "JSONResponse"
Cohesion: 0.15
Nodes (15): Request, Custom handler that safely encodes binary data in validation errors. The…, validation_exception_handler(), api_get_models_info(), api_get_settings(), api_update_settings(), Any, get (+7 more)

### Community 64 - "Frontend Development Guide"
Cohesion: 0.13
Nodes (14): Adding a New API Endpoint, Adding a New Page, Available Scripts, Build & Deployment, Development Workflow, Frontend Development Guide, Linting, Prerequisites (+6 more)

### Community 65 - "prompt_builders.py"
Cohesion: 0.15
Nodes (18): api_generate_all(), Regenerate all 3 data file formats (CSV, JSON, XML) and return their paths., build_user_prompt(), fetch_all_as_json(), fetch_all_as_xml(), fetch_all_guests_and_reservations(), Build the user prompt for querying a guest by name., Returns CSV string and saves to disk. (+10 more)

### Community 66 - "execute_chain_step_route"
Cohesion: 0.16
Nodes (14): execute_chain_page(), execute_chain_step_route(), execute_group(), post, Request, Execute the prompt chain now (Recalculate Now)., Execute chain with user inputs (page mode). The first step receives user_inputs…, Execute a single step in a prompt chain (page mode, step-by-step). Accepts both… (+6 more)

### Community 67 - "guest_extraction.py"
Cohesion: 0.21
Nodes (13): convert_to_wav(), _detect_image_ext(), extract_name_from_audio(), extract_name_from_image(), _get_client_and_model(), OpenAI, Multimodal name extraction service for Guest Search. Supports extracting guest…, Detect image file extension from magic bytes. (+5 more)

### Community 68 - "utils.py"
Cohesion: 0.20
Nodes (8): Save names to individual files and a master JSON file., save_names(), get_session(), init_connection(), Connection, Session, Open a SQLite connection with foreign keys enforced and WAL journal mode. By…, Create and return a new SQLAlchemy Session bound to the project database.…

### Community 69 - "keycloak_diagnose.py"
Cohesion: 0.22
Nodes (13): authenticate(), get_base_url(), get_user_groups(), list_clients(), list_groups(), list_realms(), list_users(), main() (+5 more)

### Community 70 - "CompareModal.tsx"
Cohesion: 0.23
Nodes (12): CompareModal(), CompareModalProps, getElapsed(), MetaInfo(), DiffOp, DiffResult, computeJsonDiff(), computeLineDiff() (+4 more)

### Community 71 - "BaseCacheEntry"
Cohesion: 0.18
Nodes (7): BaseCacheEntry, CacheEntry, A generic cached entry with expiration tracking. Type parameter T represents…, Cache a value with the default TTL., Base cached entry with expiration tracking., Return True if this entry has exceeded its TTL., T

### Community 72 - "ReservationResponse"
Cohesion: 0.18
Nodes (11): api_reservations(), get, JSON endpoint returning reservations grouped by room and errors., Single reservation output (includes joined room/guest data)., Create a ReservationResponse directly from an ORM Reservation object…, ReservationResponse, get_all_reservations_grouped_by_room(), get_reservations_summary() (+3 more)

### Community 73 - "Implementation Spec: Prompt Chain Pages"
Cohesion: 0.13
Nodes (15): 7.1 Wildcard Route, 7.2 Seed Data, 7.3 Execution Model, 7. Phase 5: Routing & GuestSearch Replacement, Appendix A: API Request/Response Examples, Appendix B: Example Prompt Templates, `backend/Generator/seed_chain_pages.py` (163 lines), Dependency Graph (Summary) (+7 more)

### Community 74 - "api_extract_name"
Cohesion: 0.18
Nodes (11): api_extract_name(), api_guest_search(), post, Query the LLM for all information about a given guest., Extract a guest name from a multimedia file (image or audio). For images: - If…, crop_image(), Crop an image using normalized coordinates (0.0-1.0). Args: image_bytes: Raw…, GuestSearchRequest (+3 more)

### Community 75 - "BaseCacheStore"
Cohesion: 0.14
Nodes (10): BaseCacheStore, http_cache_clear(), setter, Return cache hit/miss stats., Clear the HTTP response cache and return the number of cleared entries., Base in-memory cache store with TTL-based expiration. Single-process use.…, Initialize the cache store. Args: ttl: Time-to-live in seconds (default 3600 =…, Current TTL in seconds. (+2 more)

### Community 77 - "Client Backend — Dummy Service-to-Service Client"
Cohesion: 0.17
Nodes (11): Architecture, Client Backend — Dummy Service-to-Service Client, Endpoints, Environment Variables, Example: Call backend with authenticated token, Example: Inspect the token payload, How it works, Key Concepts Demonstrated (+3 more)

### Community 78 - "build_caddy_routes"
Cohesion: 0.24
Nodes (6): build_caddy_routes(), Build the full internal-server routes array. Combines static assets route, full…, Empty deny rules produces 3 routes: static_assets, full_access_bypass, catch-…, Deny rules inserted between full_access_bypass and catch-all., Verify the route order: static assets, full_access_bypass, deny rules, catch-…, TestBuildCaddyRoutes

### Community 79 - "23. Implementation Extensions & Deviations"
Cohesion: 0.17
Nodes (12): 23.10 Prompt Version `model_id` — `ondelete="SET NULL"` Behavior, 23.1 `LLMModel` Table — Schema Deviations, 23.2.1 `DeleteModelResponse` — Added `message` Field, 23.2.2 `ModelInfoResponse` — New Schema, 23.2 Schema Extensions, 23.4 Shared HTTP Transport for Connection Pooling, 23.5 Model Resolution Return Type Deviation, 23.6 `get_available_models()` — Additional Function (+4 more)

### Community 80 - "2. Implementation Checklist"
Cohesion: 0.17
Nodes (12): 2. Implementation Checklist, 5A: ChainInputSection ✅, 5B: ChainStepStatus ✅, 5C: ChainOutputSection ✅, Files, Files Created/Modified, Phase 1: Database Schema (No Dependencies), Phase 2: Pydantic Schemas + Placeholder Engine (+4 more)

### Community 81 - "populate_rooms.py"
Cohesion: 0.21
Nodes (12): get_booking_channel(), get_checkin_checkout_times(), Return the allowed_booking_channel value for a given wing code., Return (checkin_time, checkout_time) for a given booking channel value., load_rooms(), main(), populate_rooms(), print_summary() (+4 more)

### Community 82 - "PerformanceTestLogger"
Cohesion: 0.15
Nodes (18): PerformanceTestLogger, Thread-safe logger that writes performance test results to SQLite. Can be…, _execute_and_log(), Any, TestSettings, Single-request execution for performance testing. Handles the core execute-and-…, Execute a single LLM query and log the result (thread-safe). Each call resolves…, Execute a single LLM query and log the result (single-guest mode). Thin wrapper… (+10 more)

### Community 83 - "Backend Development Guide"
Cohesion: 0.18
Nodes (10): API Development, Backend Development Guide, Data Generation Scripts, Database Migrations, Migration Workflow, Project Structure, Running the Server, Standalone Scripts (+2 more)

### Community 84 - "TestSignInRedirect"
Cohesion: 0.25
Nodes (6): Hit /oauth2/start and return the redirect Location header., Hitting /oauth2/start must redirect (302) to Keycloak's authorization endpoint., The redirect Location must NOT contain internal Docker hostnames., The redirect Location must point to Keycloak's authorization endpoint., The redirect Location must start with https://out-customer.com., TestSignInRedirect

### Community 85 - "7. Background Scheduler"
Cohesion: 0.18
Nodes (11): 2.1 Database Model, 2.2 Prompt Structure, 2.3 PromptStore Service, 2. Prompt Versioning System, 7. Background Scheduler, Architecture, Execution Callback, Key Methods (+3 more)

### Community 86 - "detect_errors"
Cohesion: 0.20
Nodes (10): _base_reservation_query(), detect_errors(), get_error_ids(), Reservation, Session, Return a list of error details for reservations flagged in…, Build the base query for reservations joined with Room and Guest. Reused by…, Load the erroneous_reservations.json created by setup_errors.py and return the… (+2 more)

### Community 87 - "Database Impact Analysis & Permission Requirements"
Cohesion: 0.20
Nodes (9): Bad — Running destructive queries without checking, Database Impact Analysis & Permission Requirements, Examples, Good — Analyzing impact first, How to Present Impact to the User, Rationale, What Does NOT Require Permission, What Requires Permission (+1 more)

### Community 88 - "TestPersistenceFlow"
Cohesion: 0.20
Nodes (5): Cycle 1: all events new. Cycle 2: all events seen., Some events already seen, some new., After save_sync_timestamp, sync_is_current is True., When no checkpoint, sync_is_current is False., TestPersistenceFlow

### Community 89 - "TestParseRbacRoutes"
Cohesion: 0.20
Nodes (6): Test that parsing a nonexistent file raises an error., Tests for parse_rbac_routes function., Test parsing a basic JSON file., Test parsing JSON where message is optional., Test parsing JSON where paths is optional., TestParseRbacRoutes

### Community 90 - "Versioned Prompt System — Implementation Plan"
Cohesion: 0.20
Nodes (10): API Reference, Backend Tests (`tests/test_prompts.py`), Dependency Order, Execution Order Summary, Frontend Test Requirements, Overview, Prompt REST Endpoints, Reused Components (+2 more)

### Community 91 - "Role-Based Access Control (RBAC) — Architecture & Implementation"
Cohesion: 0.20
Nodes (10): 1. Architecture Overview, 2. Authentication Flow, Appendix A: Frontend Pages to Backend API Mapping, Appendix B: Backend API Inventory, Appendix C: Key Files Reference, Key Design Decisions, Role-Based Access Control (RBAC) — Architecture & Implementation, Service-to-Service Authentication (client-backend) (+2 more)

### Community 92 - "plugins"
Cohesion: 0.22
Nodes (8): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema, oxc, typescript, warn

### Community 93 - "package.json"
Cohesion: 0.20
Nodes (9): name, private, scripts, build, dev, lint, preview, type (+1 more)

### Community 94 - "FastAPI"
Cohesion: 0.28
Nodes (7): lifespan(), Start up and shut down the prompt group scheduler., _count_endpoints(), export_openapi(), Export the FastAPI OpenAPI spec to a JSON file., Count endpoints by method from the OpenAPI spec., FastAPI

### Community 95 - "_get_http_cache"
Cohesion: 0.13
Nodes (13): ASGIApp, delete_http_cache_entry(), get_cache_stats(), delete, Delete a specific HTTP cache entry by cache key. Query param: key=sha256hex..., Return statistics for both LLM and HTTP response caches., _get_http_cache(), http_cache_cleanup_expired() (+5 more)

### Community 96 - "update_oidc_configs"
Cohesion: 0.31
Nodes (8): _find_env_file(), Find the docker .env file. Searches: 1. Same directory as this script 2. Parent…, Update OIDC_CLIENT_SECRET in the .env file in place., Update CLIENT_API_CLIENT_SECRET in the .env file in place., Print and automatically update the Keycloak client secrets in .env files.…, _update_env_file(), _update_env_file_client_api(), update_oidc_configs()

### Community 97 - "TestPushRoutesToCaddyConfigPreservation"
Cohesion: 0.22
Nodes (4): Verify the config manipulation preserves structure., Verify push_routes_to_caddy uses requests.patch, not requests.put., Verify push_routes_to_caddy fetches current config before pushing., TestPushRoutesToCaddyConfigPreservation

### Community 98 - "Differences from Plan"
Cohesion: 0.22
Nodes (9): 10.2 — `guestSearchApi` modification, 1.1 — `PromptVersion` model: column name `metadata` → `meta_json`, 1.1 — Table name case, 6.1 — Additional types added, Additional Features Beyond Plan, Backend — Database Model, Differences from Plan, Frontend — Integration (+1 more)

### Community 99 - "6.1 Database Models"
Cohesion: 0.22
Nodes (9): 6.1 Database Models, 6.2 Chain Execution Logic, 6.3 is_active Behavior, 6. Prompt Groups — Chain Execution, Execution Steps, `PromptGroupItem`, `PromptGroupResult`, `PromptGroupSchedule` (+1 more)

### Community 100 - "5. Component Reference"
Cohesion: 0.22
Nodes (9): 5.1 Keycloak Setup (`docker/keycloak_setup/`), 5.2 oauth2-proxy Configuration, 5.3 Caddy Configuration (`docker/Caddyfile`), 5.4 Docker Compose (`docker/docker-compose.yaml`), 5.5 Role Sync Service (`docker/rbac_sync/` package), 5.6 Role-to-Path Mapping (`docker/rbac_routes.json`), 5.7 Shared Settings (`docker/settings.py`), 5.8 RBAC File Utilities (`docker/rbac_file.py`) (+1 more)

### Community 101 - "7. Trade-offs & Limitations"
Cohesion: 0.22
Nodes (9): 7. Trade-offs & Limitations, Caddy Cannot Distinguish HTTP Methods, Header Regexp Performance, oauth2-proxy `allowed_groups = ["*"]`, Realm Duplication, Sync Service: Caddy Admin API Security, Sync Service: JWT Token Lag, Sync Service: Mapping File Maintenance (+1 more)

### Community 102 - "1.5 Multimodal Name Extraction"
Cohesion: 0.22
Nodes (9): 1.5.1 Overview, 1.5.2 Backend Schema: `NameExtractionResponse`, 1.5.3 Backend Service: `guest_extraction.py`, 1.5.4 Backend Route: `POST /api/guest-search/extract-name`, 1.5.5 Frontend API Client, 1.5.6 Frontend Component: `RegionSelector`, 1.5.7 Frontend Integration in ChainInputSection, 1.5.8 Dependencies (+1 more)

### Community 103 - "server.js"
Cohesion: 0.22
Nodes (6): CONTENT_TYPES, DIST_DIR, fs, http, path, url

### Community 104 - "Quick Start Guide"
Cohesion: 0.22
Nodes (8): 1. Install Backend Dependencies, 2. Initialize the Database, 3. Populate the Database, 4. Start the Application, Optional: Inject Test Errors, Optional: Performance Test Guests, Prerequisites, Quick Start Guide

### Community 105 - "dae900574783_add_prompt_versions_table.py"
Cohesion: 0.29
Nodes (7): downgrade(), _get_default_prompts(), add prompt_versions table Revision ID: dae900574783 Revises: Create Date:…, Return seed data for default prompts as list of dicts. Each dict has the column…, Add PromptVersions table and seed default prompts., Remove PromptVersions table and all data., upgrade()

### Community 106 - "Caddy Reverse Proxy Service"
Cohesion: 0.43
Nodes (8): ConciergeOS Backend Service, Caddy Reverse Proxy Service, Client Backend Service, ConciergeOS Frontend Service, Keycloak OIDC Provider Service, oauth2-proxy OIDC Proxy Service, role-sync Background Service, Valkey Session Store Service

### Community 107 - "3. Authorization Flow"
Cohesion: 0.25
Nodes (8): 3.1 Session Invalidation (Force Logout), 3. Authorization Flow, Architecture: Valkey Server-Side Sessions (Deployed), Decision: Realm Roles vs Client Roles, Fallback: Token Validation via `/userinfo`, How It Works, Role Sync (Admin Operations), Runtime Request — Roles from Keycloak to Caddy

### Community 108 - "4. Phase 2: Chain Execution Engine"
Cohesion: 0.25
Nodes (8): 4.1 Placeholder Resolution, 4.2 Chain Execution, 4.3 New API Endpoints, 4.4 New Schemas, 4. Phase 2: Chain Execution Engine, `backend/app/routes/prompt_groups.py`, `backend/app/services/placeholders.py`, `backend/app/services/prompt_chain.py`

### Community 109 - "8. Design Decisions"
Cohesion: 0.25
Nodes (8): 8.1 Media Input Lives in ChainInputSection (Option A), 8.2 Dynamic Wildcard Routing, 8.3 Template Placeholders vs Special Inputs, 8.4 Chain Results Passed as Accumulated Context, 8.5 Alias Resolution, 8.6 Step-by-Step Execution (Beyond Original Spec), 8.7 Per-Item `is_active` Toggle (Beyond Original Spec), 8. Design Decisions

### Community 111 - "sample_caddy_config"
Cohesion: 0.29
Nodes (7): find_deny_rule_for_role(), Any, Sample RBAC routes JSON content for testing., Sample Caddy config that simulates a real config with multiple servers., Search Caddy routes for a deny rule referencing the given role., sample_caddy_config(), sample_rbac_json()

### Community 115 - "4. LLM Integration & Prompt Resolution"
Cohesion: 0.29
Nodes (7): 4.1 Main Entry Point: `query_guest_with_llm()`, 4.2 Hardcoded Fallback (`SHARED_SYSTEM_PROMPT`), 4.3 Tool Definitions, 4.4 LLM Client Configuration, 4.5 Tool Calling Loop, 4. LLM Integration & Prompt Resolution, Resolution Flow

### Community 116 - "8. API Reference"
Cohesion: 0.29
Nodes (7): 8.1 Prompt Versioning Endpoints, 8.2 Guest Search Endpoints, 8.3 Prompt Groups Endpoints, 8.4 Pydantic Schemas, 8. API Reference, Prompt Versioning, `PromptGroup`

### Community 117 - "Architecture"
Cohesion: 0.29
Nodes (7): API Integration, Architecture, Custom Hooks, Key Components, State Management, Tech Stack, UI Components (`components/ui/`)

### Community 118 - "dependencies"
Cohesion: 0.29
Nodes (7): dependencies, react-dom, react-router-dom, recharts, react-dom, react-router-dom, recharts

### Community 119 - "GroupedDataTable.tsx"
Cohesion: 0.20
Nodes (8): react, BatchToggleList(), BatchToggleListProps, GroupedColumn, GroupedDataTable(), GroupedDataTableProps, GroupedRow, react

### Community 120 - "MultiSortTable.tsx"
Cohesion: 0.33
Nodes (5): getSortDirectionIndicator(), MultiSortTable(), MultiSortTableProps, SortConfig, TableColumn

### Community 121 - "_run_tool_calling_loop"
Cohesion: 0.40
Nodes (5): call_llm_with_db_tools(), Any, Call the LLM with database tools and handle the tool calling loop. This…, Run the LLM tool-calling loop until the assistant stops calling tools. Accepts…, _run_tool_calling_loop()

### Community 122 - "🔌 API Endpoints"
Cohesion: 0.33
Nodes (6): 🔌 API Endpoints, Guest Search, Performance Testing, Prompts, Reservations, Settings

### Community 123 - "batch_runners.py"
Cohesion: 0.20
Nodes (15): _build_guest_runtime_variables(), _call_guest_llm(), _log_to_perf_db(), Any, TestSettings, Batch runners for performance testing. This module ONLY supports multi-guest…, Log a single result to the performance test database. Always logs the result…, Run sequential requests, each querying a different guest. Always calls… (+7 more)

### Community 124 - "TestRBACRoutesFileConstant"
Cohesion: 0.33
Nodes (4): Tests for RBAC_ROUTES_FILE constant., RBAC_ROUTES_FILE should point to an existing file., RBAC_ROUTES_FILE should be in the docker directory., TestRBACRoutesFileConstant

### Community 125 - "For the Keycloak Administrator"
Cohesion: 0.33
Nodes (6): 6. Scaling Guidelines, Adding a New Protected Resource, Adding a New User, Creating a Permission Tier, Decision Matrix: When to Create a New Role vs Reuse Existing, For the Keycloak Administrator

### Community 126 - "8. Testing Plan"
Cohesion: 0.33
Nodes (6): 8.1 Unit Tests (Setup Script), 8.2 Integration Tests (Full Flow), 8.3 Sync Service Tests, 8.4 Session Invalidation Tests, 8.5 Manual Verification Steps, 8. Testing Plan

### Community 127 - "1. Overview & Architecture"
Cohesion: 0.33
Nodes (6): 1. Overview & Architecture, Execution Order Diagram, Step Reference Syntax, The Problem, The Solution: Prompt Chain Pages, Visual Architecture

### Community 128 - "6. Phase 4: Frontend Components"
Cohesion: 0.33
Nodes (6): 6.1 Component Architecture, 6.2 `ChainInputSection.tsx` (401 lines), 6.3 `ChainStepStatus.tsx` (106 lines), 6.4 `ChainOutputSection.tsx` (109 lines), 6.5 `PromptChainPage.tsx` (323 lines), 6. Phase 4: Frontend Components

### Community 129 - "sync_all_roles"
Cohesion: 0.22
Nodes (7): main(), Path, Sync all roles from a routes file (JSON) to Keycloak. Parses the routes file,…, sync_all_roles(), Tests for the full sync flow., Test syncing all roles from a JSON file., TestSyncAllRoles

### Community 130 - "PromptImprovementChat.tsx"
Cohesion: 0.40
Nodes (5): ChatMessage, PromptImprovementChat(), PromptImprovementChatProps, SECTION_LABELS, aiImprove()

### Community 131 - "env.py"
Cohesion: 0.40
Nodes (4): Run migrations in 'offline' mode. This configures the context with just a URL…, Run migrations in 'online' mode. In this scenario we need to create an Engine…, run_migrations_offline(), run_migrations_online()

### Community 132 - "5970a2463784_add_is_active_column_to_promptgroup.py"
Cohesion: 0.40
Nodes (4): downgrade(), Add is_active column to PromptGroup table (idempotent for SQLite)., Remove is_active column from PromptGroup table., upgrade()

### Community 133 - "64e9fa0ce73b_add_schedule_type_to_promptgroupschedule.py"
Cohesion: 0.40
Nodes (4): downgrade(), Add schedule_type column to PromptGroupSchedule., Remove schedule_type column from PromptGroupSchedule., upgrade()

### Community 134 - "a782e25476e4_add_prompt_group_tables.py"
Cohesion: 0.40
Nodes (4): downgrade(), Create PromptGroup, PromptGroupItem, PromptGroupSchedule, PromptGroupResult…, Drop PromptGroup tables., upgrade()

### Community 135 - "DockerExecValkeyClient"
Cohesion: 0.27
Nodes (5): DockerExecValkeyClient, Delete one or more keys., Get the value of a key., Proxy Valkey client that executes commands inside the valkey container via…, Execute a valkey-cli command inside the container.

### Community 136 - "get_tool_calling_info"
Cohesion: 0.40
Nodes (5): get_tool_calling_info(), get, Return information about available tools and LLM configuration for debugging., get_available_models(), Fetch all available models from the configured LLM endpoint. Returns: List of…

### Community 137 - "role-sync service"
Cohesion: 0.40
Nodes (5): Caddy Admin API, role-sync service, RBAC Architecture, Keycloak Admin Events API, Valkey Session Store

### Community 138 - "backend_post"
Cohesion: 0.40
Nodes (5): backend_post(), post, Force a token refresh., Generic POST proxy to any backend endpoint., refresh_token()

### Community 139 - "generate_rooms.py"
Cohesion: 0.33
Nodes (6): generate_rooms(), Save rooms to a txt file and a JSON file., Deterministically compute the number of rooms on one side of a given floor.…, Generate all room numbers for the hotel., rooms_per_side(), save_rooms()

### Community 140 - "23.3 Extended API Endpoints"
Cohesion: 0.40
Nodes (5): 23.3.1 `/api/models/{model_id}/info` — Live Info for Saved Model, 23.3.2 `/api/models/fetch-info` — JSON Body with Normalization, 23.3.3 Duplicate Name Checking, 23.3.4 Detailed Delete Error Messages, 23.3 Extended API Endpoints

### Community 141 - "23.7 Response Cache — Model-Aware Caching & Diagnostics"
Cohesion: 0.40
Nodes (5): 23.7.1 Cache Key (No Model Awareness), 23.7.2 Extended CacheStore with Statistics, 23.7.3 HTTP Response Cache (Enhancement), 23.7.4 ResponseLogger — Diagnostic Logging, 23.7 Response Cache — Model-Aware Caching & Diagnostics

### Community 142 - "5. Phase 1: Backend Database Changes"
Cohesion: 0.40
Nodes (5): 5.1 Add `LLMModel` to `backend/app/models.py`, 5.2 Add `model_id` to `PromptVersion` in `backend/app/models.py`, 5.3 Create Alembic Migration, 5.4 Run Migration, 5. Phase 1: Backend Database Changes

### Community 143 - "8. Phase 4: Backend LLM Routing"
Cohesion: 0.40
Nodes (5): 8.1.1 `get_llm_config_by_model_id()`, 8.1.2 `get_llm_config_by_name()`, 8.1 Replace Config-Based Lookup with DB-Based Lookup, 8.2 Update `query_guest_with_llm()`, 8. Phase 4: Backend LLM Routing

### Community 144 - "Phase 10: Frontend — Integration Pages"
Cohesion: 0.40
Nodes (5): 10.1 — Modify `frontend/src/pages/GuestSearch.tsx`, 10.2 — Modify `frontend/src/services/api.ts`, 10.3 — Modify `frontend/src/pages/PerformanceTesting.tsx`, 10.4 — Modify `frontend/src/App.tsx`, Phase 10: Frontend — Integration Pages

### Community 145 - "Backend — PromptStore Service"
Cohesion: 0.40
Nodes (5): 3.1 — `create_prompt` parameter: `metadata` → `metadata_dict`, 3.1 — `resolve_prompt()` method added, 3.1 — Seed content structure, 3.1 — Timestamp timezone, Backend — PromptStore Service

### Community 146 - "11. File Map"
Cohesion: 0.40
Nodes (5): 11. File Map, Backend Files, Data Files, Database Tables (SQLite, hotel.db), Frontend Files

### Community 147 - "ConciergeOS — Prompting System Implementation Reference"
Cohesion: 0.40
Nodes (5): 1. Architecture Overview, ConciergeOS — Prompting System Implementation Reference, Data Flow: Guest Search, Data Flow: Prompt Group Chain, Table of Contents

### Community 148 - "3. Placeholder System"
Cohesion: 0.40
Nodes (5): 3. Placeholder System, Field Schema Discovery, Phase 1: Static Placeholders, Phase 2: Runtime Variables, Runtime Variable Auto-Mapping (in `query_guest_with_llm`)

### Community 149 - "5. Response Caching"
Cohesion: 0.40
Nodes (5): 5. Response Caching, Cache Architecture, Cache Flow in LLM Call, Key Classes & Functions, Public API

### Community 150 - "4. Role Naming Convention"
Cohesion: 0.40
Nodes (5): 4. Role Naming Convention, Convention, Defined Roles, Example User Assignments, Role Composition

### Community 151 - "3.1 Files Modified"
Cohesion: 0.40
Nodes (5): 3.1 Files Modified, 3. Phase 1: Backend Infrastructure, `backend/alembic/versions/aaa_add_chain_page_fields.py`, `backend/app/models.py`, `backend/app/schemas.py`

### Community 152 - "5. Phase 3: Frontend Types & API Client"
Cohesion: 0.40
Nodes (5): 5.1 TypeScript Types, 5.2 API Client, 5. Phase 3: Frontend Types & API Client, `frontend/src/services/promptGroupsApi.ts`, `frontend/src/types/prompt.ts`

### Community 154 - "_prompt_to_schema"
Cohesion: 0.12
Nodes (18): get_default(), get_field_schema(), get_version(), list_all_prompts(), list_available_placeholders(), list_versions(), _prompt_to_schema(), Any (+10 more)

### Community 155 - "query_guest_with_llm"
Cohesion: 0.50
Nodes (4): query_guest_with_llm(), Resolve (model_name, model_id) for a prompt version. Returns (None, None) if no…, Query the LLM for all information about a given guest using tool calling. This…, resolve_prompt_model()

### Community 156 - "shift_reservations.py"
Cohesion: 0.38
Nodes (5): main(), parse_args(), ShiftResponse, Wrapper for the service-level shift_reservations_service to maintain…, shift_reservations()

### Community 157 - "run_script"
Cohesion: 0.67
Nodes (3): main(), Run a single error setup script and return success status., run_script()

### Community 158 - "run_script"
Cohesion: 0.67
Nodes (3): main(), Run a single generator script and return success status., run_script()

### Community 159 - "run_script"
Cohesion: 0.67
Nodes (3): main(), Run a single population script and return success status., run_script()

### Community 160 - "Debugging & Extraction via Temporary Files"
Cohesion: 0.50
Nodes (3): Debugging & Extraction via Temporary Files, Example Workflow, Rationale

### Community 162 - "10. Phase 6: Backend Response Cache"
Cohesion: 0.50
Nodes (4): 10.1 Current Cache Implementation, 10.2 CacheStore with Statistics, 10.3 HTTP Response Cache (Enhancement), 10. Phase 6: Backend Response Cache

### Community 163 - "16. Phase 12: Frontend Settings Page"
Cohesion: 0.50
Nodes (4): 16.1 Redesign Settings as Model Management Hub, 16.2 Implementation Approach, 16.3 Model Card Component (inline or extract), 16. Phase 12: Frontend Settings Page

### Community 164 - "21. Testing"
Cohesion: 0.50
Nodes (4): 21.1 Backend Tests, 21.2 Frontend Tests, 21.3 End-to-End Flow, 21. Testing

### Community 165 - "3. Architecture & Data Model"
Cohesion: 0.50
Nodes (4): 3. Architecture & Data Model, Diagram, Modified Table: `PromptVersions`, New Table: `LLMModels`

### Community 166 - "Backend — Schemas"
Cohesion: 0.50
Nodes (4): 2.1 — `GuestSearchRequest` additional field, 2.1 — `PerformanceTestRequest` field naming, 2.1 — `PromptVersionSchema` datetime format, Backend — Schemas

### Community 167 - "Backend — LLM Integration"
Cohesion: 0.50
Nodes (4): 5.2 — Fallback behavior, 5.2 — Placeholder resolution, 5.2 — `query_guest_with_llm` function signature, Backend — LLM Integration

### Community 168 - "Frontend — API Client"
Cohesion: 0.50
Nodes (4): 7.1 — Additional methods added, 7.1 — Custom `request` helper, 7.1 — Function-style exports vs object pattern, Frontend — API Client

### Community 169 - "10. Initialization & Seeding"
Cohesion: 0.50
Nodes (4): 10.1 Prompt Seeding, 10.2 Scheduler Initialization, 10.3 Router Registration, 10. Initialization & Seeding

### Community 170 - "9. Frontend API Clients"
Cohesion: 0.50
Nodes (4): 9.1 Prompts API Client, 9.2 Prompt Groups API Client, 9.3 Guest Search API Integration, 9. Frontend API Clients

### Community 171 - "Appendix C: File Change Summary"
Cohesion: 0.50
Nodes (4): Appendix C: File Change Summary, Files Created, Files Modified, Grand Total

### Community 172 - "Reusable Prompt: Generate Slidev Presentation from Git Branch Analysis"
Cohesion: 0.50
Nodes (3): Prompt Template, Quick Start: How to Use, Reusable Prompt: Generate Slidev Presentation from Git Branch Analysis

### Community 173 - "React + TypeScript + Vite"
Cohesion: 0.50
Nodes (3): Expanding the Oxlint configuration, React Compiler, React + TypeScript + Vite

### Community 174 - "✨ Key Features"
Cohesion: 0.50
Nodes (4): Guest Search, ✨ Key Features, Performance Testing, Reservation Management

### Community 179 - "PromptGroupItem"
Cohesion: 0.19
Nodes (12): get_db(), Session, FastAPI dependency that yields a database session., PromptGroup, PromptGroupItem, A named, ordered collection of prompt+version pairs forming a chain., Single prompt+version entry within a PromptGroup, with ordering., main() (+4 more)

### Community 180 - "14. Phase 10: Frontend Types"
Cohesion: 0.67
Nodes (3): 14.1 Add `LLMModel` Type, 14.2 Update Prompt Types, 14. Phase 10: Frontend Types

### Community 181 - "18. Phase 14: Frontend Prompt UI"
Cohesion: 0.67
Nodes (3): 18.1 Update `frontend/src/components/ui/PromptSelector.tsx`, 18.2 Update `frontend/src/components/ui/CreatePromptModal.tsx`, 18. Phase 14: Frontend Prompt UI

### Community 182 - "19. Phase 15: Frontend Guest Search Integration"
Cohesion: 0.67
Nodes (3): 19.1 Update `frontend/src/pages/GuestSearch.tsx`, 19.2 Update `NameExtractionResponse` in API, 19. Phase 15: Frontend Guest Search Integration

### Community 183 - "22. Migration Notes"
Cohesion: 0.67
Nodes (3): 22. Migration Notes, Backward Compatibility, Existing Data

### Community 184 - "2. Problem Statement & Design Rationale"
Cohesion: 0.67
Nodes (3): 2. Problem Statement & Design Rationale, Current Limitations, Design Decisions

### Community 185 - "6. Phase 2: Backend Schemas"
Cohesion: 0.67
Nodes (3): 6.1 Add LLMModel Schemas, 6.2 Update Prompt Schemas, 6. Phase 2: Backend Schemas

### Community 186 - "7. Phase 3: Backend Model CRUD Routes"
Cohesion: 0.67
Nodes (3): 7.1 Create `backend/app/routes/models.py`, 7.2 Register the Router, 7. Phase 3: Backend Model CRUD Routes

### Community 187 - "9. Phase 5: Backend Guest Extraction"
Cohesion: 0.67
Nodes (3): 9.1 Update `backend/app/services/guest_extraction.py`, 9.2 Update `backend/app/routes/guest_search.py`, 9. Phase 5: Backend Guest Extraction

### Community 188 - "Phase 11: Migration & Polish"
Cohesion: 0.67
Nodes (3): 11.1 — Implement `seed_default_prompts()`, 11.2 — Update app navigation, Phase 11: Migration & Polish

### Community 221 - "_group_with_relations"
Cohesion: 0.25
Nodes (8): download_result(), _group_with_relations(), list_groups(), Any, get, List all prompt groups., Return a PromptGroup query with items, schedules, and results joined., Download a result file for a specific execution result.

### Community 222 - "live_token"
Cohesion: 0.67
Nodes (3): live_token(), fixture, Get a live authentication token.

### Community 223 - "_classify_response"
Cohesion: 0.50
Nodes (3): _classify_response(), Insert a single performance test result (thread-safe)., Determine the response format and whether JSON is malformed. Returns: A tuple…

### Community 224 - "9. Migration Guide"
Cohesion: 0.50
Nodes (4): 9. Migration Guide, Running the Migration, Seed Data, Verifying

### Community 226 - "create_openai_client"
Cohesion: 0.67
Nodes (3): create_openai_client(), Any, Lazy-import and create an OpenAI client.

## Knowledge Gaps
- **596 isolated node(s):** `install-cert-linux.sh script`, `install-cert-macos.sh script`, `$schema`, `typescript`, `oxc` (+591 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **26 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `api_run_performance_testing()` connect `performance_testing.py` to `app/config.py`, `PerformanceTesting/__init__.py`, `llm.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `run_tests()` connect `PerformanceTesting/__init__.py` to `performance_testing.py`, `PerformanceTestLogger`, `batch_runners.py`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Why does `LLM Model Management — Multi-Model Support with Prompt-Level Assignment` connect `LLM Model Management — Multi-Model Support with Prompt-Level Assignment` to `10. Phase 6: Backend Response Cache`, `16. Phase 12: Frontend Settings Page`, `21. Testing`, `3. Architecture & Data Model`, `README.md`, `5. Phase 1: Backend Database Changes`, `23. Implementation Extensions & Deviations`, `8. Phase 4: Backend LLM Routing`, `14. Phase 10: Frontend Types`, `18. Phase 14: Frontend Prompt UI`, `19. Phase 15: Frontend Guest Search Integration`, `22. Migration Notes`, `2. Problem Statement & Design Rationale`, `6. Phase 2: Backend Schemas`, `7. Phase 3: Backend Model CRUD Routes`, `9. Phase 5: Backend Guest Extraction`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._
- **Are the 65 inferred relationships involving `ReservationStatus` (e.g. with `Guest` and `LLMModel`) actually correct?**
  _`ReservationStatus` has 65 INFERRED edges - model-reasoned connections that need verification._
- **Are the 59 inferred relationships involving `BookingSource` (e.g. with `Guest` and `LLMModel`) actually correct?**
  _`BookingSource` has 59 INFERRED edges - model-reasoned connections that need verification._
- **Are the 59 inferred relationships involving `Reservation` (e.g. with `BookingChannel` and `BookingSource`) actually correct?**
  _`Reservation` has 59 INFERRED edges - model-reasoned connections that need verification._
- **What connects `install-cert-linux.sh script`, `install-cert-macos.sh script`, `$schema` to the rest of the system?**
  _596 weakly-connected nodes found - possible documentation gaps or missing edges._