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

A mature Caddy OIDC plugin now exists — **[caddy-oidc](https://github.com/relvacode/caddy-oidc)** — that was specifically designed to solve the N+1 oauth2-proxy problem. See the [Alternative: caddy-oidc](#alternative-caddy-oidc) section below for a detailed analysis.

The current design (1 Caddy + 3 oauth2-proxy) is the standard, well-tested architecture for multi-service OIDC authentication. oauth2-proxy is a mature, production-tested project with active maintenance and comprehensive OIDC support (PKCE, SSO, session sharing, etc.).

---

## Alternative: caddy-oidc

[caddy-oidc](https://github.com/relvacode/caddy-oidc) is a native Caddy middleware for OIDC authentication and authorization, explicitly inspired by oauth2-proxy but designed to eliminate its architectural limitations.

### What Problem Does caddy-oidc Solve?

caddy-oidc performs authentication and authorization **at the Caddy level** instead of requiring a separate oauth2-proxy process per upstream. Its README states:

> "Inspired by [oauth2-proxy](https://github.com/oauth2-proxy/oauth2-proxy) but instead of requiring each application to be configured individually, perform authentication and authorization at the Caddy level."

It was created precisely to avoid the N+1 oauth2-proxy instance problem documented above.

### How It Works

caddy-oidc registers as a Caddy middleware handler (`http.handlers.oidc`). Each route can have its own `oidc` directive with per-route authentication configuration, followed by `reverse_proxy` to a different upstream:

```caddyfile
{
    oidc {
        issuer https://out-customer.com/auth/realms/production
        client_id concierge
        client_secret {env.OIDC_CLIENT_SECRET}
        scope openid profile email roles
        username sub
        authenticate cookie {
            name caddy_session
            secret {env.COOKIE_SECRET}
        }
    }
}

out-customer.com {
    tls internal

    # Keycloak
    @keycloak path /auth/*
    handle @keycloak {
        reverse_proxy keycloak:8080
    }

    # Frontend (/, /app1/*, /app2/*)
    @frontend path / /app1/* /app2/*
    handle @frontend {
        oidc {
            allow { user * }
        }
        reverse_proxy frontend:80
    }

    # Backend API
    @backend path /api/*
    handle @backend {
        oidc {
            allow { user * }
        }
        reverse_proxy backend:8000
    }

    # Client API
    @clientapi path /client-api/*
    handle @clientapi {
        oidc {
            allow { user * }
        }
        reverse_proxy client-backend:8000
    }
}
```

### Architecture with caddy-oidc

```
Browser → Caddy + caddy-oidc (single instance, port 443)
           ├─ /auth/*           → keycloak:8080
           ├─ /app2/*           → [oidc middleware] → frontend:80
           ├─ /app1/*           → [oidc middleware] → frontend:80
           ├─ /client-api/*     → [oidc middleware] → client-backend:8000
           ├─ /api/*            → [oidc middleware] → backend:8000
           └─ /*                → [oidc middleware] → frontend:80
```

### What Gets Eliminated

| Current (oauth2-proxy) | With caddy-oidc |
|------------------------|-----------------|
| 3 oauth2-proxy containers | 0 |
| 1 valkey/Redis container | 0 (sessions in encrypted cookies) |
| Complex Caddy routing to 3 proxy ports | Direct routing to backends |
| Redis session sync across instances | Not needed (stateless cookies) |
| 6 total services | 2 total (Caddy + role-sync) |

### Key Capabilities

| Feature | Description |
|---------|-------------|
| **Per-route `oidc` directive** | Each `handle` block gets its own auth middleware + `reverse_proxy` |
| **Named global providers** | Define base OIDC config once, override per route via inheritance |
| **Per-route `redirect_url`** | Each route can have its own OIDC callback path |
| **Cookie-based SSO** | Single session cookie (path `/`) shared across all routes |
| **Claim-based authorization** | `allow`/`deny` rules with user, claim, and anonymous matchers |
| **Multiple authenticators** | Cookie (browser), bearer token, header, and query parameter |
| **RFC9728 support** | OAuth 2.0 Protected Resource Metadata (`/.well-known/oauth-protected-resource`) |
| **PKCE** | Full OAuth 2.0 PKCE (S256) support for browser flows |
| **Workload Identity Federation** | JWT bearer client assertions (RFC 7523) for Kubernetes |

### Token Lifecycle Comparison

This is the **most significant trade-off** when evaluating caddy-oidc.

| Feature | oauth2-proxy (current) | caddy-oidc |
|---------|----------------------|------------|
| **Session Storage** | Server-side (Redis/Valkey) | Stateless (encrypted cookie) |
| **Token Refresh** | ✅ Automatic (`--cookie-refresh=5m`) | ❌ Not implemented |
| **Session Expiry** | Sliding window (refreshes while valid) | Fixed at login time |
| **Refresh Token** | Stored in Redis, used for silent refresh | Discarded after initial code exchange |
| **Session Sharing** | Across instances via Redis | Single cookie across routes |

#### How caddy-oidc Handles Sessions

From the source code (`cookie.go` + `session.go`):

1. During login, the OAuth code is exchanged for tokens **once**
2. Session stores only: `UID`, `ExpiresAt` (unix timestamp), `Claims` (flattened JSON)
3. The `oauth2.Token` (including refresh token) is **not stored** — only claims are extracted
4. Session expiry is either the OAuth token's `exp` claim or a fixed `max_age` duration
5. When the session expires, the user must **re-authenticate from scratch** (full OIDC redirect)

There is **no token refresh mechanism**. The `max_age` directive only controls cookie lifetime — it does not trigger a background token refresh.

#### Mitigating the No-Refresh Limitation

Set `max_age` to a long duration (e.g., `720h` / 30 days) to compensate:

```caddyfile
authenticate cookie {
    name caddy_session
    secret {env.COOKIE_SECRET}
    max_age 720h
}
```

The session cookie is encrypted (HMAC) and signed (AES-256), so it's secure. The trade-off is that token revocation on the Keycloak side won't be reflected until the cookie expires.

### Can oauth2-proxy and caddy-oidc Be Combined?

**No.** Both are OIDC authentication gateways that:

- Initiate the OIDC authorization flow
- Set their own session cookies
- Expect to be the first handler in the request chain

Running them together would create a double-authentication loop. caddy-oidc is a **replacement**, not a complement.

### Header Injection

oauth2-proxy injects user identity as HTTP headers. caddy-oidc provides the same data as Caddy placeholder variables that can be forwarded via the `header` directive with `defer`:

| oauth2-proxy Header | caddy-oidc Placeholder |
|---------------------|----------------------|
| `X-Forwarded-User` | `{http.auth.user.id}` |
| `X-Forwarded-Email` | `{http.auth.user.claim.email}` |
| `X-Forwarded-Preferred-Username` | `{http.auth.user.claim.preferred_username}` |
| `X-Forwarded-Groups` | `{http.auth.user.claim.realm_access.roles}` |
| `X-Forwarded-Access-Token` | Not available (token discarded after exchange) |

Example:

```caddyfile
handle @backend {
    oidc {
        allow { user * }
    }
    header X-Forwarded-User {http.auth.user.id} { defer }
    header X-Forwarded-Email {http.auth.user.claim.email} { defer }
    reverse_proxy backend:8000
}
```

### Claim Matching for RBAC

caddy-oidc provides built-in `allow`/`deny` rules with claim matchers:

```caddyfile
oidc {
    allow "AllowAdmins" {
        user *
        claim role admin
    }
    allow "AllowReaders" {
        user *
        claim role reader
    }
    deny "DenyAnonymous" {
        anonymous
    }
}
```

**Caveat:** Keycloak stores roles in nested claims (`realm_access.roles`). caddy-oidc's `claim` matcher uses GJSON path syntax, so nested claims are accessed via dot notation: `claim realm_access.roles admin`.

### Decision Matrix

| Priority | Recommendation |
|----------|----------------|
| **Token refresh + sliding sessions** | Keep oauth2-proxy (current setup) |
| **Simplified architecture** | Switch to caddy-oidc |
| **Short-lived tokens + immediate revocation** | Keep oauth2-proxy |
| **Minimal infrastructure** | Switch to caddy-oidc |
| **Mature, battle-tested auth** | Keep oauth2-proxy |
| **Path-based routing + auth in one service** | Switch to caddy-oidc |

### Summary

| | oauth2-proxy (current) | caddy-oidc |
|---|----------------------|------------|
| Services | 6 (Caddy + 3×proxy + Valkey + role-sync) | 2 (Caddy + role-sync) |
| Path-based routing | ❌ Requires 3 instances | ✅ Native per-route |
| Token refresh | ✅ Automatic | ❌ Not implemented |
| SSO | ✅ Via Redis | ✅ Via shared cookie |
| Session type | Server-side (sliding) | Stateless (fixed) |
| Architecture complexity | High | Low |
| Maturity | Production-tested | Active development |

### Summary

- **1 Caddy instance** handles all path-based routing (optimal, already the case)
- **3 oauth2-proxy instances** handle authentication for 3 different upstream backends (required by the library)
- All instances **share sessions** via Valkey/Redis (single login experience)
- Consolidation to 1 oauth2-proxy is **not possible** without replacing the library with custom code