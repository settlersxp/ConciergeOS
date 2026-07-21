# Role-Based Access Control (RBAC) Implementation Plan

> **Status:** Draft — pending refinement
> **Objective:** Replace the current group-based access model with a fine-grained role-based architecture using Keycloak roles, oauth2-proxy role extraction, and Caddy path-based enforcement — without modifying frontend or backend code.

---

## Table of Contents

1. [Current State](#1-current-state)
2. [Target State](#2-target-state)
3. [Architecture](#3-architecture)
4. [Role Naming Convention](#4-role-naming-convention)
5. [Component Changes](#5-component-changes)
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
4. **Scalable** — adding a new permission requires 1 role in Keycloak + 1 route in Caddy
5. **Realm switching** — controlled via environment variable for testing/production parity

### Target Access Model

| Component | Mechanism | Details |
|-----------|-----------|---------|
| Keycloak | Realm roles with naming convention | Auto-extracted from access token by oauth2-proxy |
| oauth2-proxy | `allowed_groups = ["*"]` (deny-by-default pushed to Caddy) | Roles auto-extracted with `role:` prefix into `X-Forwarded-Groups` |
| Caddy | Explicit role-to-path deny rules | `header_regexp` matches `role:<name>` patterns, deny-by-default |

---

## 3. Architecture

### Data Flow: Roles from Keycloak to Caddy

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
| 2 regex rules (2 groups × 2 paths) | N explicit deny rules (1 per protected path) |
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

### 5.4 Docker Compose (`docker/docker-compose.yaml`)

#### Changes

Add environment variable support for realm switching:

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
```

**Usage:**
```bash
# Use production realm (default)
docker compose up -d

# Use testing realm
OIDC_REALM=testing docker compose up -d
```

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

1. In `Caddyfile.json` `internal-server` routes, replace the 2 existing deny rules with the full set of role-based deny rules (see [Route Structure](#route-structure-order-matters))
2. Keep the static assets route and the default catch-all proxy route unchanged
3. Validate JSON syntax

### Phase 4: Docker Compose

1. Add `OIDC_REALM` environment variable to `oidc-main` service
2. Pass realm as CLI flag to override TOML config

### Phase 5: Documentation

1. Update `docker/README.md` with:
   - New architecture diagram
   - Role naming convention and guidelines
   - User access matrix
   - Setup instructions
2. Create this document (`docs/IMPLEMENTATION_RBAC.md`)

### Phase 6: Testing

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

**Step 2 — Add the deny rule in Caddy (`Caddyfile.json`):**

Insert a new route **before** the final default-allow route:

```jsonc
{
  "handle": [{ "handler": "static_response", "status_code": "403", "body": "Access denied." }],
  "match": [{
    "path": ["/reports*", "/api/reports*"],
    "not": [{ "header_regexp": { "X-Forwarded-Groups": { "pattern": ".*role:reports:view.*" } } }]
  }],
  "terminal": true
}
```

**Step 3 — Assign the role to users** via the Keycloak admin console or API.

**Step 4 — Restart Caddy** to pick up config changes.

#### Adding a New User

1. Create user in Keycloak (realm → Users → Create user)
2. Assign roles (Role mapping tab → Assign roles)
3. No config file changes needed

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

### Decision Matrix: When to Create a New Role vs Reuse Existing

| Scenario | Action |
|----------|--------|
| New frontend page | Create role `<module>:view`, add Caddy deny rule |
| New API endpoint (read) | If module role exists (e.g., `reservations:view`), reuse; otherwise create |
| New API endpoint (write) | Create role `<module>:write` (or `<module>:<action>` for granularity), add Caddy deny rule |
| New API endpoint (destructive) | Create role `<module>:admin`, add Caddy deny rule |
| User needs subset of existing module | Create finer-grained role: `<module>:<resource>:<action>` |

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

**Concern:** Accepting all groups at the oauth2-proxy level means an unauthenticated-but-logged-in user passes through oauth2-proxy and only gets blocked at Caddy.

**Reality:** This is acceptable because:
1. The user **is** authenticated (oauth2-proxy enforces authentication)
2. Authorization (what they can access) is intentionally pushed to Caddy
3. The user sees 403 from Caddy, which is the correct behavior for "authenticated but not authorized"

### Header Regexp Performance

**Concern:** Multiple `header_regexp` patterns on every request.

**Reality:** The `X-Forwarded-Groups` header is small (comma-separated list of role strings). Regex matching is fast for this size. Even with 15 rules, the overhead is negligible (<1ms per request).

### Realm Duplication

**Decision:** Keep 2 realms (`testing`, `production`) as requested.

**Cost:** Roles must be created in both realms. The setup script handles this automatically.

**Benefit:** Environment isolation — testing realm can have different users/roles without affecting production.

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

### 9.3 Manual Verification Steps

1. Start all services: `docker compose up -d`
2. Run setup script: `docker run --rm --network docker_app-network -v "$(pwd)/docker":/work python:3.12-slim bash -c "cd /work && pip install requests -q && python3 keycloak_setup.py keycloak 8080"`
3. Restart oauth2-proxy: `docker compose restart oidc-main`
4. Login as `user1` → verify access to assigned pages only
5. Login as `user2` → verify access to all pages
6. Check Caddy logs for 403 responses on denied paths
7. Switch realm: `OIDC_REALM=testing docker compose up -d` → verify same behavior

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

## Appendix C: Files to Modify

| File | Action | Lines Affected |
|------|--------|----------------|
| `docker/keycloak_setup.py` | Modify | Group → Role throughout |
| `docker/oidc-main.toml` | Modify | Remove 2 lines, keep rest |
| `docker/Caddyfile.json` | Modify | Replace 2 deny rules with ~12 |
| `docker/docker-compose.yaml` | Modify | Add env var to oidc-main |
| `docker/README.md` | Modify | Update architecture, user table, setup docs |
| `docs/IMPLEMENTATION_RBAC.md` | Create | This document |