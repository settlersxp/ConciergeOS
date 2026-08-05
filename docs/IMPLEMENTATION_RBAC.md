# Role-Based Access Control (RBAC) — Architecture & Implementation

> **Status:** Implementation complete
> **Objective:** Fine-grained role-based access control using Keycloak roles, oauth2-proxy role extraction, and Caddy path-based enforcement — without modifying frontend or backend application code. Role changes in Keycloak are automatically synced to Caddy via a polling-based sync service. User/session changes are detected and sessions are force-logged-out via Valkey server-side session storage.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Authentication Flow](#2-authentication-flow)
3. [Authorization Flow](#3-authorization-flow)
   - [3.1 Frontend Request Flow](#31-frontend-request-flow)
   - [3.2 Backend API Request Flow](#32-backend-api-request-flow)
   - [3.3 Session Invalidation (Force Logout)](#33-session-invalidation-force-logout)
4. [Role Naming Convention](#4-role-naming-convention)
5. [Component Reference](#5-component-reference)
   - [5.1 Keycloak Setup](#51-keycloak-setup-dockerkeycloak_setup)
   - [5.2 oauth2-proxy Configuration](#52-oauth2-proxy-configuration)
   - [5.3 Caddy Configuration](#53-caddy-configuration-dockercaddyfile)
    - [5.4 Docker Compose](#54-docker-compose-dockerdocker-composeyaml)
   - [5.6 Role Sync Service](#56-role-sync-service-docker-rbac-sync-package)
   - [5.7 Role-to-Path Mapping](#57-role-to-path-mapping-dockerrbac_routesjson)
   - [5.8 Shared Settings](#58-shared-settings-dockersettingspy)
   - [5.9 RBAC File Utilities](#59-rbac-file-utilities-dockerrbac_filepy)
6. [Scaling Guidelines](#6-scaling-guidelines)
7. [Trade-offs & Limitations](#7-trade-offs--limitations)
8. [Testing Plan](#8-testing-plan)

---

## 1. Architecture Overview

ConciergeOS uses a **multi-layer authentication and authorization chain** with a single Caddy instance and three oauth2-proxy instances:

```
Browser → Caddy (443)
           ├─ /auth/*        → Keycloak (8080)
           ├─ /app1/*        → oidc (4180) → frontend (80)
           ├─ /app2/*        → oidc (4180) → frontend-two (80)
           ├─ /oauth2/*      → oidc (4180)
           ├─ /client-api/*  → oidc-client-api (4186) → client-backend (8000)
           ├─ /api/*         → oidc-api (4184) → backend (8000)
           └─ /* (default)   → oidc (4180)
```

| Layer | Component | Role |
|-------|-----------|------|
| **Identity Provider** | Keycloak (v26) | User authentication, role management, OIDC token issuance |
| **Authentication Gateway** | oauth2-proxy (v7.15.3, three instances) | OIDC flow, session management, role extraction from tokens |
| **Authorization** | Caddy (v2, single instance) | Path-based access control for all routes (frontend + API) using `header_regexp` on `X-Forwarded-Groups` |
| **Session Store** | Valkey (v8) | Server-side session storage for all oauth2-proxy instances, enables force logout |
| **Role Sync** | `rbac_sync` Python package | Polls Keycloak admin events, updates Caddy automatically |

### Key Design Decisions

1. **No frontend/backend code changes** — all authN/authZ handled by infrastructure components
2. **Single source of truth** — roles defined in `rbac_routes.json`, created in Keycloak, enforced in Caddy
3. **Deny-by-default** — Caddy blocks protected paths unless the user has the required role
4. **Two realms** — `testing` and `production` for environment isolation, switched via `OIDC_REALM` env var
5. **Three oauth2-proxy instances** — `oidc` (frontend apps), `oidc-api` (backend API), `oidc-client-api` (client-backend)
6. **Single Caddy instance** — external gateway (443) + internal server (`:8000`) for all RBAC enforcement
7. **Valkey session storage** — enables immediate server-side session invalidation
8. **Role attributes** — roles in Keycloak store `paths`, `menus`, and `message` attributes for use by the sync service

---

## 2. Authentication Flow

### User Login (Browser)

```
1. User visits https://out-customer.com
2. Caddy proxies request to oauth2-proxy (oidc:4180)
3. oauth2-proxy detects no valid session → redirects to Keycloak login
4. User enters credentials on Keycloak login page
5. Keycloak issues OIDC tokens (access token with realm_access.roles)
6. oauth2-proxy extracts roles from access token
7. oauth2-proxy creates session in Valkey (server-side store)
8. oauth2-proxy sets session cookie in browser
9. Request forwarded to frontend:80
```

### Backend API Authentication

```
1. User request to /api/* arrives at Caddy (:443)
2. Caddy proxies to oidc-api (oauth2-proxy on :4184)
3. oauth2-proxy validates session (Valkey) → extracts roles → sets X-Forwarded-Groups
4. oauth2-proxy forwards to backend:8000
5. Caddy internal-server checks X-Forwarded-Groups against deny rules (pushed by role sync)
6. If role present → forward to backend:8000; else → 403
```

### Service-to-Service Authentication (client-backend)

```
1. client-backend uses Client Credentials Grant
2. POST /realms/master/protocol/openid-connect/token
   - client_id: "client-api"
   - client_secret: "<configured>"
3. Keycloak issues access token for service account
4. client-backend uses token to authenticate to backend API
```

---

## 3. Authorization Flow

### 3.1 Frontend Request Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. User logs in via Keycloak                                        │
│ 2. Keycloak issues access token with:                               │
│    - realm_access.roles: ["reservations:view", "guest-search:view"] │
│ 3. oauth2-proxy (oidc) extracts roles via:                          │
│    - oidc_groups_claim = "realm_access.roles"                       │
│    - Roles are prefixed with "role:" → "role:reservations:view"     │
│ 4. oauth2-proxy sets header:                                        │
│    X-Forwarded-Groups: ["role:reservations:view", "role:guest-search:view"] │
│ 5. Caddy internal-server reads X-Forwarded-Groups,                 │
│    matches against header_regexp deny rules                         │
│ 6. If required role NOT found → 403; otherwise → forward request   │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Backend API Request Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ 1. User request → Caddy (:443) → oidc-api (oauth2-proxy :4184)              │
│ 2. oauth2-proxy validates session, extracts roles, sets X-Forwarded-Groups  │
│ 3. oauth2-proxy → backend:8000 (upstream) but Caddy internal-server         │
│    intercepts and checks X-Forwarded-Groups against deny rules               │
│    pushed by the role sync service                                          │
│ 4. If required role NOT found → 403; otherwise → backend:8000               │
│                                                                             │
│ Route generation:                                                            │
│ - All routes pushed to single Caddy instance (internal-server)               │
│ - All receive a full-access bypass route (role:full-access → skip deny)     │
│ - All receive a catch-all reverse_proxy route                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

From `oauth2-proxy/providers/keycloak_oidc.go`:

```go
// extractRoles pulls roles from the access token
func (p *KeycloakOIDCProvider) extractRoles(s *sessions.SessionState) error {
    claims, _ := p.getAccessClaims(s)
    var roles []string
    roles = append(roles, claims.RealmAccess.Roles...)              // realm roles
    roles = append(roles, getClientRoles(claims)...)                // client roles as "client:role"
    for _, role := range roles {
        s.Groups = append(s.Groups, formatRole(role))              // prefixed with "role:"
    }
}

// formatRole adds the "role:" prefix
func formatRole(role string) string {
    return fmt.Sprintf("role:%s", role)
}
```

This means `X-Forwarded-Groups` contains values like:
- `role:reservations:view` (realm role)
- `role:concierge:admin` (client role)

### Role Sync (Admin Operations)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                     │
│  Keycloak          Role Sync Service              Valkey       Caddy                │
│  ┌──────────┐     (rbac_sync package)       ┌──────────┐   ┌──────────┐            │
│  │          │ 1. Admin creates/             │  Event   │   │  Admin   │            │
│  │  Events  │ ── updates/deletes            │  Dedup   │   │  API     │            │
│  │  API     │     a role in Keycloak        │  Seen    │   │  :2019   │            │
│  │          │                               │  IDs     │   │          │            │
│  │          │ 2. Sync polls events          │          │   │          │            │
│  │          │ ──────────────────────────→   │  Sync    │   │          │            │
│  │          │     (ROLE CRUD events)        │  Timestamp│   │          │            │
│  │          │                               │          │   │          │            │
│  │          │ 3. Regenerate routes          │          │   │          │            │
│  │          │ ──────────────────────────→   │          │←──│  PATCH   │            │
│  │          │     (all paths to Caddy)      │          │   │  /config  │            │
│  │          │                               │          │   │          │            │
│  └──────────┘                               └──────────┘   └──────────┘            │
│                                                                                     │
│  On startup: full sync from Keycloak roles + rbac_routes.json → Caddy               │
│  Polling: every SYNC_INTERVAL seconds (default: 10s from settings,                  │
│           overridden in docker-compose). Valkey tracks seen event                    │
│  IDs and last sync timestamp for deduplication and stale detection.                 │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Decision: Realm Roles vs Client Roles

| Factor | Realm Roles | Client Roles |
|--------|-------------|--------------|
| Header format | `role:role_name` | `role:client_id:role_name` |
| Scope | Cross-client | Scoped to one client |
| Caddy matching | Simpler regex | Longer regex with `:` |
| Recommendation | ✅ **Preferred** | Use if multi-client isolation needed |

**Decision:** Use **realm roles** for simplicity. Shorter header values, simpler Caddy regex patterns.

### 3.3 Session Invalidation (Force Logout)

#### Architecture: Valkey Server-Side Sessions (Deployed)

ConciergeOS **uses Valkey for server-side session storage**. All three oauth2-proxy instances (`oidc-main`, `oidc-two`, and `oidc-api`) are configured with:

```env
OAUTH2_PROXY_SESSION_STORE_TYPE=redis
OAUTH2_PROXY_REDIS_CONNECTION_URL=redis://valkey:6379/0
```

This enables **immediate server-side session invalidation** when a user is deleted or their session terminated.

#### How It Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  Keycloak          Role Sync Service              Valkey        oauth2-proxy │
│  ┌──────────┐     (rbac_sync package)        ┌──────────┐   ┌──────────┐   │
│  │          │ 1. Admin deletes user         │          │   │          │   │
│  │  Events  │ ──────────────────────────→   │  Session │   │  Session │   │
│  │  API     │     (USER_DELETE,             │  Store   │   │  Validation│   │
│  │          │      USER_SESSION DELETE)     │          │   │          │   │
│  │          │ 2. Sync service detects       │          │   │          │   │
│  │          │ ──────────────────────────→   │  DELETE  │←──│  CHECK   │   │
│  │          │     session invalidation       │  session │   │  on req  │   │
│  │          │                               │          │   │          │   │
│  └──────────┘                               └──────────┘   └──────────┘    │
│                                                                             │
│  Result: User is immediately logged out on next request (session gone).     │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Flow:**
1. Admin deletes a user or terminates their session in Keycloak
2. Role sync service polls Keycloak Admin Events API (every `SYNC_INTERVAL` seconds)
3. On detecting `USER_DELETE` or `USER_SESSION DELETE` events, the sync service invalidates all matching sessions in Valkey
4. On the user's next request, oauth2-proxy finds no session in Valkey → returns 401 → redirects to login

#### Fallback: Token Validation via `/userinfo`

In addition to Valkey session deletion, oauth2-proxy also validates tokens by calling Keycloak's `/userinfo` endpoint every `cookie_refresh` interval (configured as `5m`). If the user was deleted from Keycloak, the `/userinfo` call returns `HTTP 401`, and oauth2-proxy invalidates the session as a fallback.

```
GET /auth/realms/{realm}/protocol/openid-connect/userinfo
Authorization: Bearer <valid_jwt_token>
Response: HTTP 401 (user no longer exists or session expired)
```

---

## 4. Role Naming Convention

### Convention

```
<module>:<resource>[:<action>]
```

| Segment | Description | Examples |
|---------|-------------|----------|
| `<module>` | Functional area | `reservations`, `guest-search`, `performance`, `settings`, `models`, `prompts` |
| `<resource>` | Specific resource within module | `view`, `write`, `extract`, `run`, `admin` |
| `<action>` | (Optional) Fine-grained action | For future use: `export`, `delete`, `schedule` |

### Defined Roles

| Role | Frontend Pages | Backend APIs | Description |
|------|----------------|--------------|-------------|
| `reservations:view` | `/reservations` | `GET /api/reservations` | Read-only reservation access |
| `reservations:write` | — | `POST /api/reservations/shift` | Modify reservation data |
| `guest-search:view` | — | `POST /api/guest-search` | Search for guests |
| `guest-search:extract` | — | `POST /api/guest-search/extract-name` | Extract names from media |
| `performance:view` | `/performance-testing`, `/performance-dashboard` | `GET /api/performance-testing/*`, `GET /api/performance-testing/stats`, `GET /api/performance-testing/prompt-*` | View performance results |
| `performance:run` | — | `POST /api/performance-testing`, `DELETE /api/performance-testing/batch/*`, `PATCH /api/performance-testing/result/*`, `POST /api/performance-testing/setup-guests`, `POST /api/performance-testing/generate-*` | Execute/manage performance tests |
| `settings:view` | `/settings` | `GET /api/settings`, `POST /api/settings` | View and edit application settings |
| `models:admin` | (within `/settings`) | `CRUD /api/models/*` | Full LLM model management |
| `prompts:admin` | `/prompt-management`, `/prompt-groups`, `/prompt-chain-page*` | `CRUD /api/prompts/*`, `CRUD /api/prompt-groups/*` | Full prompt management |

### Example User Assignments

| User | Use Case | Roles Assigned |
|------|----------|----------------|
| `receptionist` | Front desk — view reservations, search guests | `reservations:view`, `guest-search:view` |
| `analyst` | QA — view performance results | `reservations:view`, `performance:view` |
| `operator` | Power user — everything except system config | `reservations:view`, `reservations:write`, `guest-search:view`, `guest-search:extract`, `performance:view`, `performance:run` |
| `admin` | Full access | `full-access` (composes all roles above) |

### Role Composition

For users who need broad access, create a composite role in Keycloak:

```
full-access → inherits:
  - reservations:view
  - reservations:write
  - guest-search:view
  - guest-search:extract
  - performance:view
  - performance:run
  - settings:view
  - models:admin
  - prompts:admin
```

Assign `full-access` to a user, and Keycloak automatically includes all child roles in the access token.

---

## 5. Component Reference

### 5.1 Keycloak Setup (`docker/keycloak_setup/`)

The Keycloak setup is a modular Python package that configures realms, roles, users, and OIDC clients.

**Package structure:**

| File | Purpose |
|------|---------|
| `docker/keycloak_setup.py` | Entry point — delegates to `keycloak_setup.summary.main()` |
| `keycloak_setup/config.py` | Central config: realms, clients, roles (loaded from `rbac_routes.json`), users |
| `keycloak_setup/roles.py` | Role and composite role creation in Keycloak |
| `keycloak_setup/users.py` | User creation, password setting, required actions clearing |
| `keycloak_setup/assignments.py` | Role-to-user assignment |
| `keycloak_setup/claims.py` | OIDC protocol mapper configuration (`realm_access.roles`) |
| `keycloak_setup/clients.py` | OIDC client creation and configuration |
| `keycloak_setup/auth.py` | Admin authentication |
| `keycloak_setup/summary.py` | Orchestration — runs all setup steps in order |
| `keycloak_setup/events.py` | Admin events configuration |
| `keycloak_setup/realms.py` | Realm creation |

**Key details:**
- Roles are loaded from `rbac_routes.json` at runtime via `get_roles()` which calls `load_rbac_routes()` from `rbac_file.py`
- Roles are created with custom Keycloak attributes: `paths`, `menus`, and `message`
- Two OIDC clients are configured: `concierge` (user-facing, OIDC) and `client-api` (service-to-service, Client Credentials)
- Two realms: `testing` and `production`, both configured identically
- `full-access` is a composite role inheriting all granular roles

**Shared Keycloak helpers (`docker/keycloak_common.py`):**

| Function | API Endpoint |
|----------|-------------|
| `authenticate()` | `POST /realms/master/protocol/openid-connect/token` |
| `kc_request()` | Generic — prepends `KEYCLOAK_URL` to path |
| `fetch_all_roles()` | `GET /admin/realms/{realm}/roles` |
| `fetch_all_roles_with_attrs()` | `GET /admin/realms/{realm}/roles` (includes attributes) |
| `get_role_by_name()` | `GET /admin/realms/{realm}/roles/{role_name}` |
| `has_events()` | In-memory event filtering |

**Users:**

| User | Password | Roles |
|------|----------|-------|
| `user1` | `password1` | `reservations:view`, `guest-search:view` |
| `user2` | `password2` | `full-access` |

### 5.2 oauth2-proxy Configuration

oauth2-proxy is configured **entirely via environment variables** in `docker/docker-compose.yaml` — no TOML config file is used.

Three instances are deployed:

| Instance | Service Name | Port | Upstream | Cookie Path | Purpose |
|----------|-------------|------|----------|-------------|---------|
| `oidc` | Frontend apps | 4180 | `http://caddy:8000/` | `/` | Frontend authentication (app1 + app2) |
| `oidc-api` | Backend API | 4184 | `http://backend:8000/` | `/` | API authentication |
| `oidc-client-api` | Client API | 4186 | `http://client-backend:8000/` | `/` | Client-backend authentication |

**Key configuration (all instances share these settings):**

| Environment Variable | Value |
|---------------------|-------|
| `OAUTH2_PROXY_PROVIDER` | `keycloak-oidc` |
| `OAUTH2_PROXY_OIDC_ISSUER_URL` | `{APP_DOMAIN}/auth/realms/{OIDC_REALM}` |
| `OAUTH2_PROXY_CLIENT_ID` | `concierge` |
| `OAUTH2_PROXY_SCOPE` | `openid profile email roles` |
| `OAUTH2_PROXY_OIDC_GROUPS_CLAIM` | `realm_access.roles` |
| `OAUTH2_PROXY_EMAIL_DOMAINS` | `*` |
| `OAUTH2_PROXY_COOKIE_REFRESH` | `5m` |
| `OAUTH2_PROXY_COOKIE_EXPIRE` | `1h` |
| `OAUTH2_PROXY_REVERSE_PROXY` | `true` |
| `OAUTH2_PROXY_SSL_INSECURE_SKIP_VERIFY` | `true` |
| `OAUTH2_PROXY_CODE_CHALLENGE_METHOD` | `S256` |
| `OAUTH2_PROXY_SESSION_STORE_TYPE` | `redis` |
| `OAUTH2_PROXY_REDIS_CONNECTION_URL` | `redis://valkey:6379/0` |
| `OAUTH2_PROXY_BACKEND_LOGOUT_URL` | Keycloak logout endpoint (server-side SSO termination) |
| `OAUTH2_PROXY_OIDC_EXTRA_AUDIENCES` | `account` |

**Instance-specific differences:**

| Setting | oidc | oidc-api | oidc-client-api |
|---------|------|----------|-----------------|
| `OAUTH2_PROXY_HTTP_ADDRESS` | `0.0.0.0:4180` | `0.0.0.0:4184` | `0.0.0.0:4186` |
| `OAUTH2_PROXY_REDIRECT_URL` | `.../oauth2/callback` | `.../api/oauth2/callback` | `.../client-api/oauth2/callback` |
| `OAUTH2_PROXY_UPSTREAMS` | `http://caddy:8000/` | `http://backend:8000/` | `http://client-backend:8000/` |

### 5.3 Caddy Configuration (`docker/Caddyfile`)

The single Caddy instance serves as the **external reverse proxy** (ports 80/443) and manages the **internal server** (`:8000`) for all RBAC enforcement.

**External server** (`out-customer.com`):

| Path | Backend | Notes |
|------|---------|-------|
| `/auth/*` | `keycloak:8080` | Keycloak OIDC endpoints |
| `/app2/*` | `oidc:4180` | Second frontend (path rewrite via `path_regexp`) |
| `/app1/*` | `oidc:4180` | Primary app (path rewrite via `path_regexp`) |
| `/oauth2/*` | `oidc:4180` | oauth2-proxy callbacks/sign-out |
| `/client-api/*` | `oidc-client-api:4186` | Client API (through oauth2-proxy) |
| `/api/*` | `oidc-api:4184` | Backend API (through oauth2-proxy) |
| `/*` (default) | `oidc:4180` | Fallback to oauth2-proxy |

**Internal server** (`:8000`):
- Proxies all traffic to `frontend:80`
- Deny rules for all role-protected paths (frontend + API) are injected by the role sync service at runtime
- Static assets are served directly from frontend without role checks
- Users with `full-access` role bypass all deny rules

**Admin API:** Enabled on `0.0.0.0:2019` for the role sync service (internal Docker network only).

**Route structure** (managed by role sync service):
```
[static_assets_route, full_access_bypass_route, ...deny_rules..., catch_all_route]
```

### 5.4 Docker Compose (`docker/docker-compose.yaml`)

**Services:**

| Service | Image | Host Port | Internal Port | Network |
|---------|-------|-----------|---------------|---------|
| `caddy` | `caddy:2-alpine` | 80, 443 | 80, 443 | app-network |
| `keycloak` | `quay.io/keycloak/keycloak:26.0` | 8080 | 8080 | app-network |
| `oidc` | `quay.io/oauth2-proxy/oauth2-proxy:v7.15.3` | — | 4180 | app-network |
| `oidc-api` | `quay.io/oauth2-proxy/oauth2-proxy:v7.15.3` | — | 4184 | app-network |
| `oidc-client-api` | `quay.io/oauth2-proxy/oauth2-proxy:v7.15.3` | — | 4186 | app-network |
| `role-sync` | `concos-role-sync:latest` (custom Dockerfile) | — | — | app-network |
| `valkey` | `valkey/valkey:8-alpine` | — | 6379 | app-network |
| `frontend` | `concos-frontend:latest` | — | 80 | app-network |
| `frontend-two` | `concos-frontend-two:latest` | — | 80 | app-network |
| `backend` | `concos-backend:latest` | — | 8000 | app-network |
| `client-backend` | `concos-client-backend:latest` | — | 8000 | app-network |

**Realm switching:** `OIDC_REALM` environment variable (default: `production`).

```bash
# Use production realm (default)
docker compose up -d

# Use testing realm
OIDC_REALM=testing docker compose up -d
```

### 5.5 Role Sync Service (`docker/rbac_sync/` package)

The role sync service is a modular Python package (not a single file). It polls Keycloak's Admin Events API and updates Caddy.

**Package structure:**

| File | Purpose |
|------|---------|
| `sync_orchestrator.py` | Main orchestrator — polling loop, initial sync, event dispatch |
| `config.py` | Configuration loading (delegates to shared `settings` module) |
| `event_polling.py` | Keycloak Admin Events API polling |
| `role_operations.py` | Role CRUD detection from events |
| `caddy_routes.py` | Caddy route generation and pushing to Caddy |
| `session_management.py` | Valkey session invalidation + event persistence |
| `routes_persistence.py` | Local route state persistence (`rbac_routes.json` sync from Keycloak) |
| `docker/role_sync.py` | Entry point — starts the orchestrator |

**Behavior:**

| Phase | Description |
|-------|-------------|
| **Startup** | Waits for Keycloak + Caddy to be ready. Checks Valkey for last sync timestamp. If stale (> 2x `SYNC_INTERVAL`), performs full sync from Keycloak roles + `rbac_routes.json` |
| **Polling loop** | Every `SYNC_INTERVAL` seconds (10s default from settings, 30s from docker-compose override), polls Keycloak admin events |
| **Event deduplication** | Seen event IDs stored in Valkey (`role_sync:seen` set) to avoid duplicate processing |
| **ROLE events** | On CREATE/UPDATE/DELETE, regenerates deny rules and pushes to Caddy's `internal-server` |
| **USER events** | On USER_DELETE/USER_SESSION DELETE, invalidates all matching sessions in Valkey via `invalidate_all_sessions()` |
| **Routes persistence** | After pushing routes to Caddy, syncs role attributes back to `rbac_routes.json` file |
| **Error handling** | Fail-open — if polling or pushing fails, logs error and retries next cycle |

**Configuration (from `rbac_sync/config.py`):**

| Variable | Source | Default | Description |
|----------|--------|---------|-------------|
| `KEYCLOAK_URL` | `settings.KEYCLOAK_URL` | `http://keycloak:8080/auth` | Keycloak server URL |
| `KEYCLOAK_REALM` | `settings.KEYCLOAK_REALM` | `production` | Realm to monitor |
| `CADDY_ADMIN_URL` | `settings.CADDY_ADMIN_URL` | `http://caddy:2019` | Main Caddy Admin API |
| `CADDY_RBAC_ADMIN_URL` | `settings.CADDY_RBAC_ADMIN_URL` | `http://caddy-rbac:2020` | RBAC gateway Admin API |
| `SYNC_INTERVAL` | `settings.SYNC_INTERVAL` | `30` (docker-compose override) | Polling interval in seconds |
| `VALKEY_URL` | `settings.VALKEY_URL` | `redis://valkey:6379/0` | Valkey connection URL |
| `SESSION_COOKIE_NAME` | `settings.SESSION_COOKIE_NAME` | `_oauth2_proxy` | oauth2-proxy session cookie name |
| `RBAC_ROUTES_FILE` | Computed | `docker/rbac_routes.json` | Role-to-path mapping file |

**Keycloak API endpoints used:**

```
POST   {KEYCLOAK_URL}/realms/master/protocol/openid-connect/token  → Admin auth
GET    {KEYCLOAK_URL}/admin/realms/{realm}/roles                   → Fetch roles
GET    {KEYCLOAK_URL}/admin/realms/{realm}/admin-events            → Poll admin events
```

**Caddy API endpoints used:**

```
GET    {CADDY_ADMIN_URL}/config/                                   → Fetch Caddy config
PATCH  {CADDY_ADMIN_URL}/config                                    → Push routes (internal-server)
```

### 5.7 Role-to-Path Mapping (`docker/rbac_routes.json`)

The role-to-path mapping is a **JSON file**. It is the single source of truth for which roles protect which paths, which frontend menus are visible, and also serves as a fallback when Keycloak role attributes are not yet populated.

**Schema:**

```json
[
  {
    "role": "<role_name>",
    "paths": [
      "<path_pattern>",
      "<path_pattern>"
    ],
    "menus": [
      "<menu_identifier>"
    ],
    "message": "Custom 403 message"
  }
]
```

**Field descriptions:**

| Field | Description | Example |
|-------|-------------|---------|
| `role` | Keycloak role name | `settings:view` |
| `paths` | Path patterns enforced by Caddy (frontend + API) | `/settings`, `/api/settings` |
| `menus` | Frontend menu identifiers this role unlocks | `settings`, `prompts` |
| `message` | Custom 403 denial message | `Access denied: ...` |

**How `menus` controls frontend navigation visibility:**

The `menus` field is the bridge between Keycloak role attributes and frontend navigation. The flow:

1. **Role creation:** `keycloak_setup` writes `menus` as a Keycloak role attribute
2. **Role sync:** `rbac_sync` preserves `menus` when syncing roles between Keycloak and `rbac_routes.json`
3. **Frontend request:** On page load, `Header.tsx` calls `/client-api/me`
4. **Menu resolution:** The client-backend reads user roles from `X-Forwarded-Groups`, queries Keycloak Admin API for role attributes (including `menus`), and aggregates menu identifiers across all user roles
5. **Menu filtering:** The frontend filters its navigation links against the returned `menus` array

Roles that only protect API endpoints (e.g., `reservations:write`, `guest-search:view`, `performance:run`) have an empty `menus: []` array since they do not correspond to a visible page.

**Current mappings:**

| Role | Protected Paths |
|------|----------------|
| `settings:view` | `/settings`, `/settings/*`, `/api/settings`, `/api/settings/*` |
| `models:admin` | `/api/models`, `/api/models/*` |
| `prompts:admin` | `/prompt-management`, `/prompt-groups`, `/prompt-chain-page*`, `/api/prompts/*`, `/api/prompt-groups/*` |
| `performance:view` | `/performance-testing`, `/performance-dashboard`, `/api/performance-testing/*` |
| `performance:run` | `/api/performance-testing/batch/*`, `/api/performance-testing/result/*`, `/api/performance-testing/setup-guests`, `/api/performance-testing/generate-*`, `/api/performance-testing/validate-guests` |
| `reservations:view` | `/reservations`, `/api/reservations/*` |
| `reservations:write` | `/api/reservations/shift` |
| `guest-search:view` | `/api/guest-search` |
| `guest-search:extract` | `/api/guest-search/extract-name` |

The Keycloak setup script (`keycloak_setup/config.py`) loads this file at runtime via `get_roles()` which calls `load_rbac_routes()` from `rbac_file.py`. This ensures roles in Keycloak always match the mapping file.

### 5.8 Shared Settings (`docker/settings.py`)

A shared Python settings module used by `role_sync`, `keycloak_setup`, and test fixtures. Provides a `settings` singleton with properties backed by environment variables.

**Key settings:**

| Property | Default | Used By |
|----------|---------|---------|
| `KEYCLOAK_URL` | `http://keycloak:8080/auth` | All scripts |
| `KEYCLOAK_REALM` | `production` | All scripts |
| `KEYCLOAK_ADMIN_USER` | `admin` | All scripts |
| `KEYCLOAK_ADMIN_PASSWORD` | `admin` | All scripts |
| `CADDY_ADMIN_URL` | `http://caddy:2019` | Role sync (main Caddy) |
| `CADDY_RBAC_ADMIN_URL` | `http://caddy-rbac:2020` | Role sync (RBAC gateway) |
| `VALKEY_URL` | `redis://valkey:6379/0` | Role sync, tests |
| `SESSION_COOKIE_NAME` | `_oauth2_proxy` | Role sync |
| `SYNC_INTERVAL` | `10` | Role sync |
| `MAPPING_FILE` | `/app/rbac_routes.json` | Role sync, Keycloak setup |
| `APP_DOMAIN` | `https://out-customer.com` | Keycloak setup |
| `OIDC_REALM` | `production` | Keycloak setup |
| `OIDC_CLIENT_ID` | `concierge` | Keycloak setup |
| `MODELS_ENDPOINT` | `http://localhost:8000/v1` | Backend LLM |
| `DATABASE_URL` | `sqlite:////app/database.db` | Backend |

### 5.9 RBAC File Utilities (`docker/rbac_file.py`)

Shared Python utilities for loading and writing the `rbac_routes.json` file. Uses Pydantic models (`rbac_models.py`) for validation.

| Function | Purpose |
|----------|---------|
| `load_rbac_routes(path)` | Load JSON → `RBACRoutes` Pydantic model |
| `load_role_definitions(path)` | Extract `{role: {"paths": [...], "message": ""}}` dict |
| `load_role_descriptions(path)` | Extract `{role: description}` dict (for Keycloak role creation) |
| `write_rbac_routes(path, roles_config)` | Write role config back to JSON |

---

## 6. Scaling Guidelines

### For the Keycloak Administrator

#### Adding a New Protected Resource

**Step 1 — Create the role in Keycloak:**

```bash
# Via Admin API:
curl -X POST "http://keycloak:8080/auth/admin/realms/production/roles" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "reports:view"}'
```

Or via the Keycloak admin console: Realm → Roles → Create Role.

**Step 2 — Add the role-to-path mapping:**

Add an entry to `docker/rbac_routes.json`:

```json
{
  "role": "reports:view",
  "paths": ["/reports", "/reports/*", "/api/reports", "/api/reports/*"],
  "message": "Access denied: /reports requires the reports:view role."
}
```

**Step 3 — The sync service picks it up automatically:**

On the next poll cycle (default: 30 seconds), the sync service will:
1. Detect the new role exists in Keycloak
2. Find the matching entry in the mapping file
3. Generate deny rules for all paths
4. Push all rules to Caddy's `internal-server`

**No manual Caddy restart required.**

**Step 4 — Assign the role to users** via the Keycloak admin console or API.

#### Adding a New User

1. Create user in Keycloak (realm → Users → Create user)
2. Assign roles (Role mapping tab → Assign roles)
3. No config file changes needed — roles are extracted from the JWT token at request time

#### Adding a New API Endpoint

1. Add the API path to the role's entry in `rbac_routes.json`
2. The sync service will push the deny rule to Caddy's `internal-server` on the next poll cycle

#### Adding a New Frontend Page

1. Add the frontend path to the role's entry in `rbac_routes.json`
2. The sync service will push the deny rule to Caddy's `internal-server` on the next poll cycle

#### Creating a Permission Tier

For organizations that prefer tier-based management (e.g., "receptionist", "manager", "admin"):

1. Create individual granular roles (e.g., `reservations:view`, `guest-search:view`)
2. Create composite roles that group them:
   ```
   receptionist → reservations:view, guest-search:view
   manager      → receptionist + reservations:write, performance:view
   admin        → all roles
   ```
3. Assign the composite role to users
4. Add corresponding entries to `rbac_routes.json` for each granular role

### Decision Matrix: When to Create a New Role vs Reuse Existing

| Scenario | Action |
|----------|--------|
| New frontend page | Create role `<module>:view`, add entry to `rbac_routes.json` |
| New API endpoint (read) | If module role exists (e.g., `reservations:view`), reuse; otherwise create role and add mapping |
| New API endpoint (write) | Create role `<module>:write` (or `<module>:<action>` for granularity), add entry to `rbac_routes.json` |
| New API endpoint (destructive) | Create role `<module>:admin`, add entry to `rbac_routes.json` |
| User needs subset of existing module | Create finer-grained role: `<module>:<resource>:<action>`, add entry to `rbac_routes.json` |

---

## 7. Trade-offs & Limitations

### Caddy Cannot Distinguish HTTP Methods

**Problem:** Caddy's `match` clause supports `path`, `host`, `header`, and `header_regexp` — but not HTTP method in the JSON configuration's standard matchers. (The `method` matcher exists but is limited.)

**Impact:** We cannot enforce `GET /api/settings` (allowed) vs `POST /api/settings` (denied) at the Caddy layer.

**Current approach:** Require the role for **any** access to a protected path, regardless of HTTP method. A user with `settings:view` can both GET and POST to `/api/settings`.

**Mitigation options (if method-level granularity becomes required):**

| Option | Complexity | Effort |
|--------|------------|--------|
| Use Caddy `expression` matcher with `http.request.method` | Medium | Requires Caddy template syntax |
| Run a second oauth2-proxy instance for write endpoints | High | Adds infrastructure complexity |
| Push method-level authZ to backend (FastAPI deps) | Low | **Violates** "no backend code" constraint |
| Split write endpoints under different paths (e.g., `/api/admin/settings`) | Low | Requires backend route changes |

**Recommendation:** Start with path-level control. If method-level granularity is needed, use path separation (e.g., `/api/admin/*` for write-only endpoints).

### Single Caddy Instance

The architecture uses a **single Caddy instance** with the external gateway (443) and an internal server (`:8000`) for RBAC enforcement. This simplifies operations:
- Only one Caddy process to monitor and manage
- All deny rules pushed to a single Admin API endpoint
- The `internal-server` handles both frontend and API routes

### oauth2-proxy `allowed_groups = []` (Accept All)

**Concern:** Accepting all groups at the oauth2-proxy level means an authenticated user passes through oauth2-proxy and only gets blocked at Caddy.

**Reality:** This is acceptable because:
1. The user **is** authenticated (oauth2-proxy enforces authentication)
2. Authorization (what they can access) is intentionally pushed to Caddy
3. The user sees 403 from Caddy, which is the correct behavior for "authenticated but not authorized"

### Header Regexp Performance

**Concern:** Multiple `header_regexp` patterns on every request.

**Reality:** The `X-Forwarded-Groups` header is small (comma-separated list of role strings). Regex matching is fast for this size. Even with 15+ rules across both Caddy instances, the overhead is negligible (<1ms per request).

### Realm Duplication

**Decision:** Keep 2 realms (`testing`, `production`) as requested.

**Cost:** Roles must be created in both realms. The setup script handles this automatically.

**Benefit:** Environment isolation — testing realm can have different users/roles without affecting production.

### Sync Service: Polling Latency

**Concern:** Role changes are not propagated to Caddy immediately — there's a delay of up to `SYNC_INTERVAL` seconds (default: 30s).

**Mitigation:** The interval is configurable via `SYNC_INTERVAL` environment variable. For most use cases, 30 seconds is acceptable. If near-real-time sync is required, reduce to 5-10 seconds (at the cost of slightly more API calls to Keycloak).

### Sync Service: JWT Token Lag

**Concern:** Even after Caddy routes are updated, existing users with old JWT tokens won't have the new roles in their `X-Forwarded-Groups` header until their token expires and they re-authenticate.

**Reality:** This is a Keycloak/JWT limitation, not a sync service issue. With `cookie_expire = "1h"` and `cookie_refresh = "5m"` in oauth2-proxy, tokens refresh every 5 minutes. Users will pick up new roles within ~5 minutes after oauth2-proxy performs a token refresh.

### Sync Service: Caddy Admin API Security

**Concern:** The Caddy Admin API (`:2019` for main, `:2020` for RBAC gateway) allows modifying the live Caddy configuration.

**Mitigation:** Both admin endpoints are only accessible from the internal Docker network. No port mapping exposes `2019` or `2020` to the host. The sync service is the only container with access. If additional hardening is needed, the Caddy admin API supports authentication (via `auth` module) in future implementations.

### Sync Service: Mapping File Maintenance

**Concern:** The `rbac_routes.json` file must be kept in sync with the roles created in Keycloak.

**Mitigation:** The sync service only generates routes for roles that exist in **both** Keycloak and the mapping file. If a role exists in Keycloak but not in the mapping file, no deny rule is generated (the resource remains accessible). If a role exists in the mapping file but not in Keycloak, the sync service logs a warning but skips it. The sync service also writes routes back to `rbac_routes.json` after syncing from Keycloak, helping keep the file in sync.

### Three oauth2-proxy Instances: Resource Usage

**Concern:** Running three oauth2-proxy instances consumes more memory and CPU than a single instance.

**Reality:** Each oauth2-proxy instance is lightweight (~10-20MB RAM idle). The separation is necessary because each instance has a different upstream and redirect URL. The additional resource usage is negligible in a Docker environment.

---

## 8. Testing Plan

### 8.1 Unit Tests (Setup Script)

| Test | Assertion |
|------|-----------|
| Create role | Role exists in Keycloak, returns 201 |
| Assign role to user | User has role in `GET /users/{id}/role-mappings/realm` |
| Composite role | `full-access` user has all child roles in access token |
| Idempotency | Running setup twice does not duplicate roles/users |

### 8.2 Integration Tests (Full Flow)

| Scenario | User | Expected Result |
|----------|------|-----------------|
| Access `/reservations` | `receptionist` (`reservations:view`) | 200 OK |
| Access `/settings` | `receptionist` (`reservations:view`) | 403 Forbidden |
| Access `/api/reservations/shift` (POST) | `receptionist` (`reservations:view`) | 403 Forbidden |
| Access `/api/reservations` (GET) | `receptionist` | 200 OK (proxied through oidc-api) |
| Access `/settings` | `admin` (`full-access`) | 200 OK |
| Access `/api/models` | `operator` (no `models:admin`) | 403 Forbidden |
| Access `/api/models` | `admin` (`models:admin` via `full-access`) | 200 OK |
| Access any page | Unauthenticated user | Redirect to Keycloak login |
| Static assets | Any authenticated user | 200 OK (no role check) |

### 8.3 Sync Service Tests

| Test | Assertion |
|------|-----------|
| Initial sync on startup | All routes generated from mapping file pushed to Caddy |
| Role CREATE detected | New deny rule appears in Caddy within `SYNC_INTERVAL` seconds |
| Role DELETE detected | Corresponding deny rule removed from Caddy within `SYNC_INTERVAL` seconds |
| Mapping file update detected | New paths appear in Caddy routes on next poll cycle |
| Idempotent restart | Restarting sync service produces identical Caddy routes |
| Keycloak unreachable | Sync service logs error, existing Caddy config unchanged (fail-open) |
| Caddy API unreachable | Sync service logs error, retries on next poll cycle |
| Role in Keycloak but not in mapping | Sync service logs warning, no route generated |
| Role in mapping but not in Keycloak | Sync service logs warning, route skipped |
| ETag handling | Caddy returns 304 when no config changes; sync service handles gracefully |

### 8.4 Session Invalidation Tests

| Test | Assertion |
|------|-----------|
| User deleted from Keycloak | User forced to login within `cookie_refresh` interval (~1 min) |
| User session terminated in Keycloak | User forced to login within `cookie_refresh` interval |
| `/userinfo` returns 401 | oauth2-proxy invalidates session, redirects to login |
| (Valkey) User deleted from Keycloak | Session deleted from Valkey immediately, user logged out on next request |
| (Valkey) SESSION_REMOVE event | Sync service detects event, deletes session from Valkey |

### 8.5 Manual Verification Steps

1. Start all services: `docker compose up -d`
2. Run setup script: `docker run --rm --network docker_app-network -v "$(pwd)/docker":/work python:3.12-slim bash -c "cd /work && pip install requests -q && python3 keycloak_setup.py keycloak 8080"`
3. Verify sync service logs: `docker compose logs role-sync` — should show initial sync completing
4. Verify main Caddy routes: `curl http://localhost:2019/config/apps/http/servers/internal-server/routes` — should show frontend deny rules
5. Verify Caddy internal-server routes: `curl http://localhost:2019/config/apps/http/servers/internal-server/routes` — should show deny rules for all protected paths
6. Login as `user1` → verify access to assigned pages only
7. Login as `user2` → verify access to all pages
8. Create a new role in Keycloak admin console
9. Add entry to `rbac_routes.json`
10. Wait up to `SYNC_INTERVAL` seconds; check Caddy logs for updated routes
11. Check Caddy logs for 403 responses on denied paths
12. Switch realm: `OIDC_REALM=testing docker compose up -d` → verify same behavior

---

## Appendix A: Frontend Pages to Backend API Mapping

| Frontend Route | Component | Backend APIs Called | Role Required |
|----------------|-----------|---------------------|---------------|
| `/reservations` | Reservations | `GET /api/reservations` | `reservations:view` |
| `/settings` | Settings | `GET/POST /api/settings`, `GET /api/models` | `settings:view` (+ `models:admin` for models) |
| `/performance-testing` | PerformanceTesting | `POST /api/performance-testing`, `GET .../results`, `GET .../batches`, etc. | `performance:view` (+ `performance:run` for writes) |
| `/performance-dashboard` | PerformanceDashboard | `GET .../stats`, `GET .../prompt-stats`, etc. | `performance:view` |
| `/prompt-management` | PromptManagement | `CRUD /api/prompts/*` | `prompts:admin` |
| `/prompt-groups` | PromptGroups | `CRUD /api/prompt-groups/*` | `prompts:admin` |
| `/prompt-chain-page*` | PromptChainPage | `POST /api/prompt-groups/*/execute*` | `prompts:admin` |
| (home, default) | — | — | Any authenticated user |

## Appendix B: Backend API Inventory

| API Path | Methods | Module | Suggested Role |
|----------|---------|--------|----------------|
| `/api/reservations` | GET | reservations | `reservations:view` |
| `/api/reservations/shift` | POST | reservations | `reservations:write` |
| `/api/guest-search` | POST | guest-search | `guest-search:view` |
| `/api/guest-search/extract-name` | POST | guest-search | `guest-search:extract` |
| `/api/settings` | GET, POST | settings | `settings:view` |
| `/api/models` | GET, POST | models | `models:admin` |
| `/api/models/{id}` | GET, PUT, DELETE | models | `models:admin` |
| `/api/models/fetch-info` | POST | models | `models:admin` |
| `/api/performance-testing` | POST | performance | `performance:run` |
| `/api/performance-testing/results` | GET | performance | `performance:view` |
| `/api/performance-testing/all-results` | GET | performance | `performance:view` |
| `/api/performance-testing/batches` | GET | performance | `performance:view` |
| `/api/performance-testing/results-by-batch` | GET | performance | `performance:view` |
| `/api/performance-testing/result/{id}` | PATCH | performance | `performance:run` |
| `/api/performance-testing/batch/{uuid}` | DELETE | performance | `performance:run` |
| `/api/performance-testing/setup-guests` | POST | performance | `performance:run` |
| `/api/performance-testing/generate-*` | POST | performance | `performance:run` |
| `/api/performance-testing/test-guests` | GET | performance | `performance:view` |
| `/api/performance-testing/guest/{id}` | GET | performance | `performance:view` |
| `/api/performance-testing/check-duplicates` | GET | performance | `performance:view` |
| `/api/performance-testing/validate-guests` | POST | performance | `performance:run` |
| `/api/performance-testing/stats` | GET | performance | `performance:view` |
| `/api/performance-testing/prompt-stats` | GET | performance | `performance:view` |
| `/api/performance-testing/prompt-batches` | GET | performance | `performance:view` |
| `/api/performance-testing/prompt-detail` | GET | performance | `performance:view` |
| `/api/prompts/*` | CRUD | prompts | `prompts:admin` |
| `/api/prompt-groups/*` | CRUD | prompts | `prompts:admin` |

---

## Appendix C: Key Files Reference

| File | Description |
|------|-------------|
| `docker/keycloak_setup/` | Modular Keycloak setup package (realms, roles, users, clients) |
| `docker/keycloak_common.py` | Shared Keycloak API helpers |
| `docker/rbac_routes.json` | Role-to-path mapping (single source of truth) |
| `docker/rbac_file.py` | Shared RBAC file utilities |
| `docker/rbac_models.py` | Pydantic models for RBAC routes |
| `docker/rbac_sync/` | Role sync service package |
| `docker/rbac_sync/sync_orchestrator.py` | Main orchestrator — polling loop, initial sync, event dispatch |
| `docker/rbac_sync/config.py` | Configuration (delegates to shared settings) |
| `docker/rbac_sync/caddy_routes.py` | Route generation + pushing to both Caddy instances |
| `docker/rbac_sync/event_polling.py` | Keycloak Admin Events API polling |
| `docker/rbac_sync/session_management.py` | Valkey session invalidation + event persistence |
| `docker/rbac_sync/routes_persistence.py` | Route file persistence (sync from Keycloak) |
| `docker/role_sync.py` | Role sync entry point |
| `docker/settings.py` | Shared settings module |
| `docker/Caddyfile` | Main Caddy configuration (external gateway + frontend RBAC) |
| `docker/Caddyfile.rbac` | Caddy RBAC gateway configuration (API authorization) |
| `docker/docker-compose.yaml` | Docker Compose service definitions |
| `docs/IMPLEMENTATION_RBAC.md` | This document |