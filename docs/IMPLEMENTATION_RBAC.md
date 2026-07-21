# Role-Based Access Control (RBAC) Implementation Plan

> **Status:** Draft — pending refinement
> **Objective:** Replace the current group-based access model with a fine-grained role-based architecture using Keycloak roles, oauth2-proxy role extraction, and Caddy path-based enforcement — without modifying frontend or backend code. Role changes in Keycloak are automatically synced to Caddy via a polling-based sync service. User/session changes are detected and sessions are force-logged-out via Valkey server-side session storage.

---

## Table of Contents

1. [Current State](#1-current-state)
2. [Target State](#2-target-state)
3. [Architecture](#3-architecture)
   - [3.1 Session Invalidation (Force Logout)](#31-session-invalidation-force-logout)
4. [Role Naming Convention](#4-role-naming-convention)
5. [Component Changes](#5-component-changes)
   - [5.1 Keycloak Setup Script](#51-keycloak-setup-script-dockerkeycloak_setuppy)
   - [5.2 oauth2-proxy Configuration](#52-oauth2-proxy-configuration-dockeroidc-maintoml)
   - [5.3 Caddy Configuration](#53-caddy-configuration-dockercaddyfilejson)
   - [5.4 Docker Compose](#54-docker-compose-dockerdocker-composeyaml)
   - [5.5 Role Sync Service](#55-role-sync-service-dockerrole_syncpy)
   - [5.6 Role-to-Path Mapping](#56-role-to-path-mapping-dockerrbac_routesyaml)
6. [Implementation Steps](#6-implementation-steps)
7. [Scaling Guidelines](#7-scaling-guidelines)
8. [Trade-offs & Limitations](#8-trade-offs--limitations)
9. [Testing Plan](#9-testing-plan)

---

## 1. Current State

### Authentication Flow

```
Browser → Caddy (443) → oauth2-proxy (4182) → Caddy internal (8000) → frontend/backend
```

### Current Access Model

| Component | Mechanism | Details |
|-----------|-----------|---------|
| Keycloak | 2 realms (`testing`, `production`), 2 groups per realm (`single`, `all`) | `oidc-group-membership-mapper` exposes groups in ID token |
| oauth2-proxy | `allowed_groups = ["single", "all"]` + `oidc_groups_claim = "groups"` | Passes groups via `X-Forwarded-Groups` header |
| Caddy | `header_regexp` regex matching on `X-Forwarded-Groups` | 2 rules: deny `/settings` for `all`, deny everything else for `single` |

### Current Limitations

1. **Only 2 access levels** — `single` (settings-only) and `all` (everything except settings)
2. **No API-level control** — all authenticated users can call all `/api/*` endpoints
3. **Configuration fragmentation** — access logic spread across 3 files
4. **Realm duplication** — `testing` + `production` doubles configuration maintenance
5. **Regex-based matching** — fragile, hard to read, error-prone

---

## 2. Target State

### Goals

1. **Fine-grained access control** — each user can access specific frontend pages AND specific backend API endpoints
2. **No frontend/backend code changes** — all authN/authZ handled by Keycloak + oauth2-proxy + Caddy
3. **Single source of truth** — roles defined in Keycloak, enforced in Caddy
4. **Scalable** — adding a new permission requires 1 role in Keycloak + 1 entry in mapping file (sync is automatic)
5. **Realm switching** — controlled via environment variable for testing/production parity
6. **Auto-sync** — role changes in Keycloak are automatically propagated to Caddy via a polling sync service
7. **Session invalidation** — deleted users are detected via `/userinfo` returning 401 (within `cookie_refresh` interval), with optional Valkey session store for immediate force logout

### Target Access Model

| Component | Mechanism | Details |
|-----------|-----------|---------|
| Keycloak | Realm roles with naming convention | Auto-extracted from access token by oauth2-proxy |
| oauth2-proxy | `allowed_groups = ["*"]` (deny-by-default pushed to Caddy) | Roles auto-extracted with `role:` prefix into `X-Forwarded-Groups` |
| Role Sync Service | Polls Keycloak Admin Events API | Detects role CRUD operations, generates Caddy routes, pushes via Caddy Admin API |
| Caddy | Explicit role-to-path deny rules (auto-generated) | `header_regexp` matches `role:<name>` patterns, deny-by-default |
| Valkey (optional) | Server-side session store | Enables immediate force logout by deleting sessions when user deleted/terminated |

---

## 3. Architecture

### Data Flow: Roles from Keycloak to Caddy (Runtime Request)

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. User logs in via Keycloak                                        │
│ 2. Keycloak issues access token with:                               │
│    - realm_access.roles: ["reservations:view", "guest-search:view"] │
│    - resource_access.client.roles: [...]                             │
│ 3. oauth2-proxy (KeycloakOIDCProvider) extracts roles from token    │
│    - Realm roles  → "role:reservations:view"                        │
│    - Client roles → "role:concierge:role_name"                      │
│ 4. oauth2-proxy sets header:                                        │
│    X-Forwarded-Groups: ["role:reservations:view", "role:guest-search:view"] │
│ 5. Caddy reads X-Forwarded-Groups, matches against path rules       │
│ 6. If no matching role → 403; otherwise → forward to frontend       │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow: Role Sync (Admin Operations)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                     │
│  Keycloak              Role Sync Service                 Caddy                      │
│  ┌─────────────┐      (polling)            ┌─────────────────┐    (admin API)      │
│  │             │  1. Admin creates/        │                 │                      │
│  │  Admin      │ ── updates/deletes        │  Polling Loop:  │                      │
│  │  API        │     a role in Keycloak    │  1. Query Admin │                      │
│  │             │                           │     Events API  │                      │
│  │  /admin/    │                           │  2. Detect ROLE │                      │
│  │  realms/    │                           │     CRUD events │                      │
│  │  roles      │                           │  3. Load role- │                      │
│  │             │                           │     to-path     │                      │
│  │             │                           │     mapping     │                      │
│  │             │                           │  4. Generate    │                      │
│  │             │                           │     Caddy       │ ─── PUT /config/     │
│  │             │                           │     routes      │      apps/http/...   │
│  │             │                           │  5. Push to     │                      │
│  │             │                           │     Caddy API   │                      │
│  └─────────────┘                           └─────────────────┘                      │
│                                                                                     │
│  On startup: Sync service queries GET /admin/realms/{realm}/roles to build          │
│  routes from scratch (idempotent initial sync).                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Technical Verification

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

This means `X-Forwarded-Groups` will contain values like:
- `role:reservations:view` (realm role)
- `role:concierge:admin` (client role)

### Decision: Realm Roles vs Client Roles

| Factor | Realm Roles | Client Roles |
|--------|-------------|--------------|
| Header format | `role:role_name` | `role:client_id:role_name` |
| Scope | Cross-client | Scoped to one client |
| Caddy matching | Simpler regex | Longer regex with `:` |
| Recommendation | ✅ **Preferred** | Use if multi-client isolation needed |

**Decision:** Use **realm roles** for simplicity. Shorter header values, simpler Caddy regex patterns.

### 3.1 Session Invalidation (Force Logout)

#### Problem Statement

When a user is deleted from Keycloak, or their session is manually terminated (e.g., via admin console or API), the user can **continue accessing the application** until their oauth2-proxy cookie expires. This is because:

1. oauth2-proxy stores session state in **browser cookies** by default (no server-side store)
2. Cookies cannot be revoked server-side — they persist until expiry (`cookie_expire = "1h"`)
3. Role route updates via the sync service only affect **new** requests with updated headers, not existing cookies

#### Detection Mechanism: Keycloak `/userinfo` Returns 401

**Discovery:** When a user is deleted from Keycloak (or their session terminated), the Keycloak `/userinfo` endpoint returns `HTTP 401 Unauthorized`.

```
GET /auth/realms/{realm}/protocol/openid-connect/userinfo
Authorization: Bearer <valid_jwt_token>

Response: HTTP 401 (user no longer exists or session expired)
```

**How oauth2-proxy uses this:** The `cookie_refresh` setting controls how often oauth2-proxy calls the `/userinfo` endpoint (via `ValidateURL`) to validate the session. On each validation:

1. oauth2-proxy calls `GET /userinfo` with the current access token
2. If the response is `HTTP 200`, the session is valid — tokens are refreshed
3. If the response is `HTTP 401` (user deleted/session terminated), oauth2-proxy **invalidates the session** and redirects to login

**Default behavior with `cookie_refresh = "1m"`:** A deleted user will be detected and forced to log out within **~1 minute** (bounded by the refresh interval).

#### Limitation: Cookie-Only Session Storage

With the default cookie-based session storage in oauth2-proxy:

| Aspect | Behavior |
|--------|----------|
| Detection mechanism | `ValidateURL` calls `/userinfo` every `cookie_refresh` interval |
| Max detection delay | `cookie_refresh` duration (1 minute with current config) |
| Server-side invalidation | **Not possible** — cookies are client-side |
| Immediate force logout | **Not possible** without Valkey session store |

**The `cookie_refresh = "1m"` setting already provides bounded detection.** Reducing it further (e.g., `30s`) increases detection speed but also increases load on Keycloak's `/userinfo` endpoint.

#### Optional: Real-Time Force Logout with Valkey Session Store

If **immediate** force logout is required (e.g., for security-sensitive environments), oauth2-proxy supports **server-side session storage** via Valkey. This enables the sync service to actively delete sessions from Valkey when a user is deleted or session terminated.

##### Architecture with Valkey

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  Keycloak          Role Sync Service              Valkey        oauth2-proxy │
│  ┌──────────┐     (extended polling)        ┌──────────┐   ┌──────────┐    │
│  │          │ 1. Admin deletes user         │          │   │          │    │
│  │  Events  │ ──────────────────────────→   │  Session │   │  Session │    │
│  │  API     │     (USER_DELETE,             │  Store   │   │  Validation│   │
│  │          │      SESSION_REMOVE)          │          │   │          │    │
│  │          │ 2. Sync service detects       │          │   │          │    │
│  │          │ ──────────────────────────→   │  DELETE  │←──│  CHECK   │    │
│  │          │     session invalidation       │  session │   │  on req  │    │
│  │          │                               │          │   │          │    │
│  └──────────┘                               └──────────┘   └──────────┘    │
│                                                                             │
│  Result: User is immediately logged out on next request (session gone).     │
└─────────────────────────────────────────────────────────────────────────────┘
```

##### Required Changes for Valkey Session Store

**oauth2-proxy configuration** (`docker/oidc-main.toml`):

```toml
# ADD these lines:
session_store_type = "redis"
session_store_clients = ["valkey:6379"]
session_store_redis_options = "{\"Password\":\"\",\"DB\":0}"
```

**Docker Compose** — add Valkey service:

```yaml
valkey:
  image: valkey/valkey:alpine
  container_name: valkey
  restart: unless-stopped
  networks:
    - app-network
```

**Role sync service** — extend event filtering:

```python
# ADD these event types to the filter:
USER_EVENTS = ["USER_DELETE", "SESSION_REMOVE", "LOGIN_FAILURE"]  # Extend as needed

# When detected, find all sessions in Valkey for the user and delete them:
def invalidate_user_sessions(user_id: str, valkey_client):
    """Delete all oauth2-proxy sessions for a given user."""
    # oauth2-proxy stores sessions as: _oauth2-proxy:<hash>
    # Scan for sessions containing the user_id and delete
    for key in valkey_client.scan_iter(match=f"*{user_id}*"):
        valkey_client.delete(key)
```

##### Trade-off: Valkey vs Cookie-Only

| Factor | Cookie-Only (current) | Valkey (optional) |
|--------|------------------------|-------------------|
| Detection delay | Up to `cookie_refresh` (~1 min) | Near-instant (next request) |
| Infrastructure | None | Additional Valkey container |
| Complexity | Low | Medium (sync service extension) |
| Scalability | Stateless oauth2-proxy | Shared state via Valkey |
| Recommendation | ✅ **Start here** | Add if immediate invalidation required |

**Recommendation:** Start with cookie-only (rely on `cookie_refresh = "1m"` for detection). Add Valkey session store in a follow-on phase if immediate force logout becomes a requirement.

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

## 5. Component Changes

### 5.1 Keycloak Setup Script (`docker/keycloak_setup.py`)

#### Changes

| Current | Target |
|---------|--------|
| Creates groups (`single`, `all`) | Creates realm roles (see [Defined Roles](#defined-roles)) |
| Assigns users to groups | Assigns users to roles via `POST /users/{id}/role-mappings/realm` |
| Configures `oidc-group-membership-mapper` | **No mapper needed** — roles are in access token by default |
| 2 realms duplicated | 2 realms (kept), roles created in both |

#### API Endpoints Used

```
POST   /admin/realms/{realm}/roles                    → Create role
GET    /admin/realms/{realm}/roles/{role}             → Check if role exists
POST   /admin/realms/{realm}/users/{id}/role-mappings/realm  → Assign roles to user
GET    /admin/realms/{realm}/users/{id}/role-mappings/realm  → Check existing assignments
```

#### New Data Structures

```python
ROLES = {
    "reservations:view":        "Read-only reservation access",
    "reservations:write":       "Modify reservation data",
    "guest-search:view":        "Search for guests",
    "guest-search:extract":     "Extract names from media",
    "performance:view":         "View performance results",
    "performance:run":          "Execute/manage performance tests",
    "settings:view":            "View and edit application settings",
    "models:admin":             "Full LLM model management",
    "prompts:admin":            "Full prompt management",
}

# Composite role
COMPOSITE_ROLES = {
    "full-access": list(ROLES.keys()),
}

USERS = {
    "user1": {
        "password": "password1",
        "roles": ["reservations:view", "guest-search:view"],
    },
    "user2": {
        "password": "password2",
        "roles": ["full-access"],  # or explicitly list all roles
    },
}
```

### 5.2 oauth2-proxy Configuration (`docker/oidc-main.toml`)

#### Changes

| Setting | Current | Target | Reason |
|---------|---------|--------|--------|
| `allowed_groups` | `["single", "all"]` | `["*"]` | Push authorization to Caddy (deny-by-default) |
| `oidc_groups_claim` | `"groups"` | **Removed** | No longer needed — roles auto-extracted by KeycloakOIDCProvider |
| `oidc_issuer_url` | Hardcoded realm | `${OIDC_REALM}` variable | Environment-based realm switching |

#### Target Configuration

```toml
provider = "keycloak-oidc"
oidc_issuer_url = "https://out-customer.com/auth/realms/production"
client_id = "concierge"
client_secret = "..."
redirect_url = "https://out-customer.com/oauth2/callback"
cookie_secret = "..."
cookie_secure = false
email_domains = ["*"]

# Allow all authenticated users — Caddy enforces fine-grained access
allowed_groups = ["*"]

upstreams = ["http://caddy:8000/"]
http_address = "0.0.0.0:4182"
proxy_prefix = "/oauth2"
reverse_proxy = true
scope = "openid profile email"
pass_access_token = false
pass_authorization_header = false
pass_user_headers = true
ssl_insecure_skip_verify = true
code_challenge_method = "S256"
cookie_refresh = "1m"
cookie_expire = "1h"
```

**Note:** The `scope` does not need `roles` because Keycloak includes `realm_access.roles` in the **access token** by default, and oauth2-proxy reads roles from the access token (not the ID token).

### 5.3 Caddy Configuration (`docker/Caddyfile.json`)

#### Changes

| Current | Target |
|---------|--------|
| `"admin": {"disabled": true}` | `"admin": {"listen": "0.0.0.0:2019"}` — **Required** for the sync service to push route updates |
| 2 regex rules (2 groups × 2 paths) | N explicit deny rules (1 per protected path), auto-generated by sync service |
| Group-based regex: `.*all.*`, `.*single.*` | Role-based regex: `.*role:settings:view.*` |
| Allow-by-default (last route is catch-all proxy) | Deny-by-default (last route is catch-all proxy, but all sensitive paths have explicit deny rules above) |

#### Route Structure (Order Matters)

```
1. Static assets        → always allow → frontend:80
2. /settings            → deny unless role:settings:view
3. /performance-testing → deny unless role:performance:view
4. /performance-dashboard → deny unless role:performance:view
5. /prompt-management   → deny unless role:prompts:admin
6. /prompt-groups       → deny unless role:prompts:admin
7. /prompt-chain-page*  → deny unless role:prompts:admin
8. /api/settings*       → deny unless role:settings:view
9. /api/models*         → deny unless role:models:admin
10. /api/prompts*        → deny unless role:prompts:admin
11. /api/prompt-groups*  → deny unless role:prompts:admin
12. /api/performance-testing* → deny unless role:performance:view
13. /api/reservations/shift*  → deny unless role:reservations:write
14. /api/guest-search/extract-name* → deny unless role:guest-search:extract
15. Default             → allow → frontend:80
```

**Note:** Routes 2-14 are auto-generated by the sync service from the role-to-path mapping file. They are pushed to Caddy via the Admin API at `http://caddy:2019/config/apps/http/servers/internal-server/routes`.

#### Route Template

Every deny rule follows this pattern:

```jsonc
{
  "handle": [
    {
      "handler": "static_response",
      "status_code": "403",
      "body": "Access denied: this resource requires the <role> role."
    }
  ],
  "match": [
    {
      "path": ["<protected-path>"],
      "not": [
        {
          "header_regexp": {
            "X-Forwarded-Groups": {
              "pattern": ".*role:<role_name>.*"
            }
          }
        }
      ]
    }
  ],
  "terminal": true
}
```

#### Admin API Security

The Caddy admin endpoint (`:2019`) is bound to `0.0.0.0` but is **only accessible from the internal Docker network**. It must never be exposed to the host or external networks. The `docker-compose.yaml` ensures this by placing the sync service and Caddy on the same `app-network` with no port mapping for `2019`.

### 5.4 Docker Compose (`docker/docker-compose.yaml`)

#### Changes

Add environment variable support for realm switching and the new `role-sync` service:

```yaml
oidc-main:
  image: quay.io/oauth2-proxy/oauth2-proxy:v7.15.3
  container_name: oidc-main
  restart: unless-stopped
  extra_hosts:
    - "out-customer.com:host-gateway"
  volumes:
    - ./oidc-main.toml:/cfg.toml
  environment:
    - OIDC_REALM=${OIDC_REALM:-production}  # ← NEW
  command: >
    oauth2-proxy --config /cfg.toml
    --oidc-issuer-url=https://out-customer.com/auth/realms/${OIDC_REALM:-production}
  depends_on:
    - keycloak
    - frontend
  networks:
    - app-network

# NEW: Role sync service
role-sync:
  image: python:3.12-slim
  container_name: role-sync
  restart: unless-stopped
  volumes:
    - ./role_sync.py:/app/role_sync.py
    - ./rbac_routes.yaml:/app/rbac_routes.yaml
  environment:
    - KEYCLOAK_URL=http://keycloak:8080
    - KEYCLOAK_REALM=${OIDC_REALM:-production}
    - KEYCLOAK_ADMIN_USER=admin
    - KEYCLOAK_ADMIN_PASSWORD=admin
    - CADDY_ADMIN_URL=http://caddy:2019
    - SYNC_INTERVAL=30
  command: >
    sh -c "pip install requests pyyaml -q && python3 /app/role_sync.py"
  depends_on:
    - keycloak
    - caddy
  networks:
    - app-network
```

**Usage:**
```bash
# Use production realm (default)
docker compose up -d

# Use testing realm
OIDC_REALM=testing docker compose up -d
```

### 5.5 Role Sync Service (`docker/role_sync.py`)

#### Purpose

A lightweight Python service that polls Keycloak's Admin Events API to detect role-related changes (CREATE, UPDATE, DELETE of roles; ADD/REMOVE role mappings), then regenerates Caddy route rules and pushes them via the Caddy Admin API.

#### Behavior

| Phase | Description |
|-------|-------------|
| **Startup (initial sync)** | On first run, queries `GET /auth/admin/realms/{realm}/roles` to fetch all roles, loads the role-to-path mapping file, generates all Caddy routes, and pushes them atomically via `PUT /config/apps/http/servers/internal-server/routes`. This ensures idempotent behavior on restart. |
| **Polling loop** | Every `SYNC_INTERVAL` seconds (default: 30s), polls `GET /auth/admin/realms/{realm}/events?type=ADMIN&dateFrom={last_poll_ts}&dateTo={now}` to fetch admin events since the last poll. |
| **Event filtering** | Filters events where `resourceType == "ROLE"` and `operationType` in `["CREATE", "UPDATE", "DELETE"]`. |
| **Route regeneration** | On detecting a role change, re-queries `GET /auth/admin/realms/{realm}/roles` for the current state, regenerates all Caddy deny rules from the mapping file, and pushes the updated routes via `PUT /config/apps/http/servers/internal-server/routes`. |
| **Error handling** | If polling or pushing fails, logs the error and retries on the next poll cycle. The existing Caddy config remains unchanged (fail-open). |

#### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `KEYCLOAK_URL` | Yes | — | Keycloak server URL (e.g., `http://keycloak:8080`) |
| `KEYCLOAK_REALM` | Yes | `production` | Realm to monitor |
| `KEYCLOAK_ADMIN_USER` | Yes | — | Admin username for Keycloak API |
| `KEYCLOAK_ADMIN_PASSWORD` | Yes | — | Admin password for Keycloak API |
| `CADDY_ADMIN_URL` | Yes | `http://caddy:2019` | Caddy Admin API URL |
| `SYNC_INTERVAL` | No | `30` | Polling interval in seconds |
| `MAPPING_FILE` | No | `/app/rbac_routes.yaml` | Path to role-to-path mapping file |

#### Keycloak API Endpoints Used

```
POST   /auth/realms/master/protocol/openid-connect/token          → Authenticate as admin
GET    /auth/admin/realms/{realm}/roles                           → Fetch all roles
GET    /auth/admin/realms/{realm}/events?type=ADMIN&dateFrom=&dateTo=  → Poll admin events
```

#### Caddy API Endpoints Used

```
PUT    /config/apps/http/servers/internal-server/routes           → Push updated routes atomically
GET    /config/apps/http/servers/internal-server/routes           → Read current routes (for debug/verify)
```

### 5.6 Role-to-Path Mapping (`docker/rbac_routes.yaml`)

#### Purpose

A human-readable YAML file that maps Keycloak role names to the Caddy paths they protect. The sync service reads this file to generate Caddy deny rules. When a new role is created in Keycloak, the admin adds an entry to this file, and the sync service picks it up on the next poll cycle.

#### Format

```yaml
# Role-to-Path Mapping for RBAC Sync Service
# Each role maps to one or more path patterns protected by that role.
#
# Format:
#   role: "<role_name>"
#   paths:
#     - "<path_pattern>"
#     - "<path_pattern>"
#   message: "Optional custom 403 message"

- role: "settings:view"
  paths:
    - "/settings"
    - "/settings/*"
    - "/api/settings"
    - "/api/settings/*"
  message: "Access denied: /settings requires the settings:view role."

- role: "models:admin"
  paths:
    - "/api/models"
    - "/api/models/*"
  message: "Access denied: /api/models requires the models:admin role."

- role: "prompts:admin"
  paths:
    - "/prompt-management"
    - "/prompt-groups"
    - "/prompt-chain-page*"
    - "/api/prompts"
    - "/api/prompts/*"
    - "/api/prompt-groups"
    - "/api/prompt-groups/*"
  message: "Access denied: prompt resources require the prompts:admin role."

- role: "performance:view"
  paths:
    - "/performance-testing"
    - "/performance-dashboard"
    - "/api/performance-testing"
    - "/api/performance-testing/*"
  message: "Access denied: performance resources require the performance:view role."

- role: "performance:run"
  paths:
    - "/api/performance-testing"              # POST only (Caddy cannot distinguish method)
    - "/api/performance-testing/batch/*"      # DELETE
    - "/api/performance-testing/result/*"     # PATCH
    - "/api/performance-testing/setup-guests"
    - "/api/performance-testing/generate-*"
    - "/api/performance-testing/validate-guests"
  message: "Access denied: performance test execution requires the performance:run role."

- role: "reservations:view"
  paths:
    - "/reservations"
    - "/api/reservations"
    - "/api/reservations/*"
  message: "Access denied: /reservations requires the reservations:view role."

- role: "reservations:write"
  paths:
    - "/api/reservations/shift"
  message: "Access denied: shifting reservations requires the reservations:write role."

- role: "guest-search:view"
  paths:
    - "/api/guest-search"
  message: "Access denied: guest search requires the guest-search:view role."

- role: "guest-search:extract"
  paths:
    - "/api/guest-search/extract-name"
  message: "Access denied: name extraction requires the guest-search:extract role."
```

#### How the Sync Service Uses It

1. Load the YAML file on startup and after each role change
2. For each role entry, check if the role exists in Keycloak (via `GET /admin/realms/{realm}/roles`)
3. If the role exists, generate a Caddy deny rule for each path using the [Route Template](#route-template)
4. Assemble all rules in order (static assets route first, deny rules, catch-all proxy last)
5. Push the complete routes array atomically to Caddy

---

## 6. Implementation Steps

### Phase 1: Keycloak Setup Script

1. Replace `GROUPS = ["single", "all"]` with `ROLES = {...}` (see [Defined Roles](#defined-roles))
2. Replace `create_group()` with `create_role()` using `POST /admin/realms/{realm}/roles`
3. Replace `assign_user_to_group()` with `assign_user_to_roles()` using `POST /admin/realms/{realm}/users/{id}/role-mappings/realm`
4. Remove `configure_groups_claim()` — no protocol mapper needed
5. Add composite role creation for `full-access`
6. Update summary output to list roles instead of groups

### Phase 2: oauth2-proxy Configuration

1. Remove `oidc_groups_claim = "groups"` from `oidc-main.toml`
2. Replace `allowed_groups = ["single", "all"]` with `allowed_groups = ["*"]`
3. Keep all other settings unchanged

### Phase 3: Caddy Configuration

1. Enable the Caddy Admin API: change `"admin": {"disabled": true}` to `"admin": {"listen": "0.0.0.0:2019"}` in `Caddyfile.json`
2. In `internal-server` routes, keep the static assets route and the default catch-all proxy route — deny rules will be injected by the sync service at runtime
3. Validate JSON syntax

### Phase 4: Docker Compose

1. Add `OIDC_REALM` environment variable to `oidc-main` service
2. Pass realm as CLI flag to override TOML config
3. Add `role-sync` service definition (see [Section 5.4](#54-docker-compose-dockerdocker-composeyaml))

### Phase 5: Role Sync Service

1. Create `docker/role_sync.py` implementing the polling loop (see [Section 5.5](#55-role-sync-service-dockerrole_syncpy))
2. Create `docker/rbac_routes.yaml` with role-to-path mappings (see [Section 5.6](#56-role-to-path-mapping-dockerrbac_routesyaml))
3. Verify the sync service starts, authenticates to Keycloak, and pushes initial routes to Caddy
4. Test that role changes in Keycloak are detected and routes are updated

### Phase 6: Documentation

1. Update `docker/README.md` with:
   - New architecture diagram (including sync service)
   - Role naming convention and guidelines
   - User access matrix
   - Setup instructions
2. Create this document (`docs/IMPLEMENTATION_RBAC.md`)

### Phase 7: Testing

(See [Testing Plan](#9-testing-plan))

---

## 7. Scaling Guidelines

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

Add an entry to `docker/rbac_routes.yaml`:

```yaml
- role: "reports:view"
  paths:
    - "/reports"
    - "/reports/*"
    - "/api/reports"
    - "/api/reports/*"
  message: "Access denied: /reports requires the reports:view role."
```

**Step 3 — The sync service picks it up automatically:**

On the next poll cycle (default: 30 seconds), the sync service will:
1. Detect the new role exists in Keycloak
2. Find the matching entry in the mapping file
3. Generate the Caddy deny rule
4. Push the updated routes to Caddy via the Admin API

**No manual Caddy restart required.**

**Step 4 — Assign the role to users** via the Keycloak admin console or API.

#### Adding a New User

1. Create user in Keycloak (realm → Users → Create user)
2. Assign roles (Role mapping tab → Assign roles)
3. No config file changes needed — roles are extracted from the JWT token at request time

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
4. Add corresponding entries to `rbac_routes.yaml` for each granular role

### Decision Matrix: When to Create a New Role vs Reuse Existing

| Scenario | Action |
|----------|--------|
| New frontend page | Create role `<module>:view`, add entry to `rbac_routes.yaml` |
| New API endpoint (read) | If module role exists (e.g., `reservations:view`), reuse; otherwise create role and add mapping |
| New API endpoint (write) | Create role `<module>:write` (or `<module>:<action>` for granularity), add entry to `rbac_routes.yaml` |
| New API endpoint (destructive) | Create role `<module>:admin`, add entry to `rbac_routes.yaml` |
| User needs subset of existing module | Create finer-grained role: `<module>:<resource>:<action>`, add entry to `rbac_routes.yaml` |

---

## 8. Trade-offs & Limitations

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

### oauth2-proxy `allowed_groups = ["*"]`

**Concern:** Accepting all groups at the oauth2-proxy level means an authenticated user passes through oauth2-proxy and only gets blocked at Caddy.

**Reality:** This is acceptable because:
1. The user **is** authenticated (oauth2-proxy enforces authentication)
2. Authorization (what they can access) is intentionally pushed to Caddy
3. The user sees 403 from Caddy, which is the correct behavior for "authenticated but not authorized"

### Header Regexp Performance

**Concern:** Multiple `header_regexp` patterns on every request.

**Reality:** The `X-Forwarded-Groups` header is small (comma-separated list of role strings). Regex matching is fast for this size. Even with 15+ rules, the overhead is negligible (<1ms per request).

### Realm Duplication

**Decision:** Keep 2 realms (`testing`, `production`) as requested.

**Cost:** Roles must be created in both realms. The setup script handles this automatically.

**Benefit:** Environment isolation — testing realm can have different users/roles without affecting production.

### Sync Service: Polling Latency

**Concern:** Role changes are not propagated to Caddy immediately — there's a delay of up to `SYNC_INTERVAL` seconds (default: 30s).

**Mitigation:** The interval is configurable via `SYNC_INTERVAL` environment variable. For most use cases, 30 seconds is acceptable. If near-real-time sync is required, reduce to 5-10 seconds (at the cost of slightly more API calls to Keycloak).

### Sync Service: JWT Token Lag

**Concern:** Even after Caddy routes are updated, existing users with old JWT tokens won't have the new roles in their `X-Forwarded-Groups` header until their token expires and they re-authenticate.

**Reality:** This is a Keycloak/JWT limitation, not a sync service issue. With `cookie_expire = "1h"` and `cookie_refresh = "1m"` in oauth2-proxy, tokens refresh frequently. Users will pick up new roles within ~1 minute after oauth2-proxy performs a token refresh.

### Sync Service: Caddy Admin API Security

**Concern:** The Caddy Admin API (`:2019`) allows modifying the live Caddy configuration.

**Mitigation:** The admin endpoint is only accessible from the internal Docker network. No port mapping exposes `2019` to the host. The sync service is the only container with access. If additional hardening is needed, the Caddy admin API supports authentication (via `auth` module) in future implementations.

### Sync Service: Mapping File Maintenance

**Concern:** The `rbac_routes.yaml` file must be kept in sync with the roles created in Keycloak.

**Mitigation:** The sync service only generates routes for roles that exist in **both** Keycloak and the mapping file. If a role exists in Keycloak but not in the mapping file, no deny rule is generated (the resource remains accessible). If a role exists in the mapping file but not in Keycloak, the sync service logs a warning but skips it.

---

## 9. Testing Plan

### 9.1 Unit Tests (Setup Script)

| Test | Assertion |
|------|-----------|
| Create role | Role exists in Keycloak, returns 201 |
| Assign role to user | User has role in `GET /users/{id}/role-mappings/realm` |
| Composite role | `full-access` user has all child roles in access token |
| Idempotency | Running setup twice does not duplicate roles/users |

### 9.2 Integration Tests (Full Flow)

| Scenario | User | Expected Result |
|----------|------|-----------------|
| Access `/reservations` | `receptionist` (`reservations:view`) | 200 OK |
| Access `/settings` | `receptionist` (`reservations:view`) | 403 Forbidden |
| Access `/api/reservations/shift` (POST) | `receptionist` (`reservations:view`) | 403 Forbidden |
| Access `/api/reservations` (GET) | `receptionist` | 200 OK (proxied through) |
| Access `/settings` | `admin` (`full-access`) | 200 OK |
| Access `/api/models` | `operator` (no `models:admin`) | 403 Forbidden |
| Access `/api/models` | `admin` (`models:admin` via `full-access`) | 200 OK |
| Access any page | Unauthenticated user | Redirect to Keycloak login |
| Static assets | Any authenticated user | 200 OK (no role check) |

### 9.3 Sync Service Tests

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

### 9.4 Session Invalidation Tests

| Test | Assertion |
|------|-----------|
| User deleted from Keycloak | User forced to login within `cookie_refresh` interval (~1 min) |
| User session terminated in Keycloak | User forced to login within `cookie_refresh` interval |
| `/userinfo` returns 401 | oauth2-proxy invalidates session, redirects to login |
| (Valkey) User deleted from Keycloak | Session deleted from Valkey immediately, user logged out on next request |
| (Valkey) SESSION_REMOVE event | Sync service detects event, deletes session from Valkey |

### 9.5 Manual Verification Steps

1. Start all services: `docker compose up -d`
2. Run setup script: `docker run --rm --network docker_app-network -v "$(pwd)/docker":/work python:3.12-slim bash -c "cd /work && pip install requests -q && python3 keycloak_setup.py keycloak 8080"`
3. Verify sync service logs: `docker compose logs role-sync` — should show initial sync completing
4. Verify Caddy routes: `curl http://localhost:2019/config/apps/http/servers/internal-server/routes` — should show deny rules
5. Login as `user1` → verify access to assigned pages only
6. Login as `user2` → verify access to all pages
7. Create a new role in Keycloak admin console
8. Add entry to `rbac_routes.yaml`
9. Wait up to `SYNC_INTERVAL` seconds; check Caddy logs for updated routes
10. Check Caddy logs for 403 responses on denied paths
11. Switch realm: `OIDC_REALM=testing docker compose up -d` → verify same behavior

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

## Appendix C: Files to Modify or Create

| File | Action | Description |
|------|--------|-------------|
| `docker/keycloak_setup.py` | Modify | Group → Role throughout |
| `docker/oidc-main.toml` | Modify | Remove `oidc_groups_claim`, set `allowed_groups = ["*"]` |
| `docker/Caddyfile.json` | Modify | Enable admin endpoint (`"listen": "0.0.0.0:2019"`), simplify routes (deny rules injected by sync service) |
| `docker/docker-compose.yaml` | Modify | Add `OIDC_REALM` env var to `oidc-main`; add `role-sync` service |
| `docker/role_sync.py` | **Create** | Python sync service: polls Keycloak admin events, generates Caddy routes, pushes via Caddy Admin API |
| `docker/rbac_routes.yaml` | **Create** | Role-to-path mapping: YAML file that maps role names to protected Caddy paths |
| `docker/README.md` | Modify | Update architecture diagram, role naming convention, user access matrix, setup instructions |
| `docs/IMPLEMENTATION_RBAC.md` | Create | This document |
| `docker/docker-compose.yaml` | Modify (optional) | Add Valkey service for immediate session invalidation |
| `docker/oidc-main.toml` | Modify (optional) | Add `session_store_type = "redis"` for immediate session invalidation (Valkey is protocol-compatible) |
