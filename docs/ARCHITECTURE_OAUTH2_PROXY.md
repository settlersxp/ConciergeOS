# OAuth2 Proxy Architecture

## Why Three oauth2-proxy Instances?

It is **not possible** to consolidate the three `oauth2-proxy` instances into a single instance. This document explains why.

### The Limitation

oauth2-proxy v7 does **not** support path-based upstream routing. The `--upstream` flag accepts multiple URLs only for **load balancing** (round-robin distribution), not for routing to different backends based on the request path. Each oauth2-proxy instance can proxy to a **single upstream** only.

Reference: [`oauth2-proxy/pkg/apis/options/upstreams.go`](https://github.com/oauth2-proxy/oauth2-proxy/blob/main/pkg/apis/options/upstreams.go) — the `Upstream` struct has a single `URI` field with no path-matching logic for the legacy `--upstream` flag.

### Why Three Instances Are Required

Each service requires a different upstream backend and a different OIDC redirect URL for the callback:

| Instance | Port | Upstream | Path | Redirect URL |
|----------|------|----------|------|--------------|
| `oidc` | 4180 | `frontend:80` | `/`, `/app1/*`, `/app2/*` | `.../app1/oauth2/callback` |
| `oidc-api` | 4184 | `backend:8000` | `/api/*` | `.../api/oauth2/callback` |
| `oidc-client-api` | 4186 | `client-backend:8000` | `/client-api/*` | `.../client-api/oauth2/callback` |

The `redirect_url` must match the OIDC client registration in Keycloak and the callback route in Caddy, so it cannot be shared across instances serving different paths.

### Current Architecture (Optimal)

You **already use a single Caddy instance** as the routing layer. The three oauth2-proxy instances are simple authentication middleware:

```
Browser → Caddy (single instance, port 443)
           ├─ /auth/*           → keycloak:8080
           ├─ /app2/*           → oidc:4180          (rewrite path → /)
           ├─ /app1/*           → oidc:4180          (rewrite path → /)
           ├─ /client-api/*     → oidc-client-api:4186
           ├─ /api/*            → oidc-api:4184
           ├─ /oauth2/*         → oidc:4180
           └─ /*                → oidc:4180

           Each oauth2-proxy instance:
             ├─ oidc            → frontend:80
             ├─ oidc-api        → backend:8000
             └─ oidc-client-api → client-backend:8000
```

### Shared Session Across Instances

All three instances share the same OIDC session via a **central Valkey (Redis) store** (`OAUTH2_PROXY_SESSION_STORE_TYPE=redis`). This means:

- The user authenticates **once** regardless of which path they access first
- Session state is synchronized across all three instances
- Logout from any path invalidates the session everywhere

### What Each oauth2-proxy Instance Does

Each instance is a thin, stateless authentication layer that:

1. **Intercepts** incoming requests
2. **Validates** the authentication cookie (shared via Valkey)
3. **Authenticates** via OIDC flow if not authenticated
4. **Injects headers** into the upstream request:
   - `X-Forwarded-User` — user subject identifier
   - `X-Forwarded-Email` — user email
   - `X-Forwarded-Preferred-Username` — username
   - `X-Forwarded-Groups` — Keycloak roles (used for RBAC)
   - `X-Forwarded-Access-Token` — JWT access token (when `pass-access-token=true`)
5. **Forwards** the request to its single configured upstream

### Could oauth2-proxy Be Eliminated Entirely?

The only way to have a single reverse proxy handle everything would be to move OIDC authentication into Caddy itself. Options:

| Approach | Effort | Risk | Notes |
|----------|--------|------|-------|
| Caddy OIDC plugin | Medium | High | No mature plugin exists that matches oauth2-proxy's feature set |
| Custom Caddy module | High | High | Would need to implement PKCE, session management, cookie handling, RBAC header injection |
| nginx + auth_request | Medium | Medium | Would still need separate auth service per upstream |

The current design (1 Caddy + 3 oauth2-proxy) is the standard, well-tested architecture for multi-service OIDC authentication. oauth2-proxy is a mature, production-tested project with active maintenance and comprehensive OIDC support (PKCE, SSO, session sharing, etc.).

### Summary

- **1 Caddy instance** handles all path-based routing (optimal, already the case)
- **3 oauth2-proxy instances** handle authentication for 3 different upstream backends (required by the library)
- All instances **share sessions** via Valkey/Redis (single login experience)
- Consolidation to 1 oauth2-proxy is **not possible** without replacing the library with custom code