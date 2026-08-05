# ConciergeOS Docker Setup

## Architecture

```
Browser → Caddy (443)
         ├─ /auth/*        → Keycloak (8080)
         └─ everything else → oauth2-proxy oidc (4180)
                                  ├─ /api/*        → backend (8000)
                                  ├─ /client-api/* → client-backend (8000)
                                  └─ default       → frontend (80)
```

A single oauth2-proxy instance handles all authenticated routes using path-based upstream routing.

### Services

| Service | Image | Port | Description |
|---------|-------|------|-------------|
| **Caddy** | `caddy:2-alpine` | 80, 443, 2019 (admin) | Reverse proxy & HTTPS terminator using internal CA. Routes `/auth/*` to Keycloak, all other traffic to the single oauth2-proxy instance. Admin API exposed on port 2019 for the role-sync service. |
| **oauth2-proxy (oidc)** | `oauth2-proxy:v7.15.3` | 4180 | Single instance handling OIDC authentication for all routes. Uses path-based upstream routing: `/api/*` → backend, `/client-api/*` → client-backend, default → frontend. Extracts user roles from access token via `realm_access.roles` claim and passes them through `X-Forwarded-Groups` header. Sessions stored in Valkey. |
| **role-sync** | `concos-role-sync:latest` | N/A | Background service that polls Keycloak's Admin Events API to detect role changes, regenerates Caddy deny rules, and pushes them via the Caddy Admin API. Also persists role attributes to `rbac_routes.json`. |
| **valkey** | `valkey/valkey:8-alpine` | 6379 | Redis-compatible session store used by oauth2-proxy for session persistence and invalidation. |
| **frontend** | `concos-frontend:latest` | 80 | Node.js static file server (App1) serving the Vite SPA build. |
| **frontend-two** | `concos-frontend-two:latest` | 80 | Node.js static file server (App2) serving a second tenant instance of the Vite SPA build (built with `BASE_URL=/app2`). |
| **client-backend** | `concos-client-backend:latest` | 8000 | FastAPI service demonstrating service-to-service authentication via Keycloak (Client Credentials Grant). Exposes `/client-api/*` endpoints for health checks, token inspection, user info (RBAC menus), and backend proxying. |
| **backend** | `concos-backend:latest` | 8000 | FastAPI application. Accessible via Caddy at `/api/*` and internally by client-backend. |
| **keycloak** | `keycloak:26.0` | 8080 | OIDC identity provider. Exposed externally via Caddy at `/auth/*`. Realms: `testing`, `production`. |

### Access Control Flow

Access control is role-based and **dynamically synced** from Keycloak to Caddy:

1. **oauth2-proxy** authenticates the user via Keycloak OIDC and extracts roles from the `realm_access.roles` claim
2. Roles are passed to upstream services via the `X-Forwarded-Groups` header (format: `role:<name>,role:<name>`)
3. **role-sync** service polls Keycloak's Admin Events API every 10 seconds (configurable via `SYNC_INTERVAL`)
4. On role changes (create, update, delete), role-sync fetches role attributes from Keycloak, generates Caddy deny rules, and pushes them via the Caddy Admin API
5. Role attributes (paths, menus) are persisted to `rbac_routes.json` for documentation and version control

### Roles

Roles are defined in `docker/rbac_routes.json` and synced to Keycloak during setup. Each role defines paths that require that role to access:

| Role | Protected Paths |
|------|-----------------|
| `settings:view` | `/settings`, `/api/settings` |
| `models:admin` | `/api/models` |
| `prompts:admin` | `/prompt-management`, `/prompt-groups`, `/prompt-chain-page*`, `/api/prompts`, `/api/prompt-groups` |
| `performance:view` | `/performance-testing`, `/performance-dashboard`, `/api/performance-testing` |
| `performance:run` | `/api/performance-testing/batch/*`, `/api/performance-testing/result/*`, etc. |
| `reservations:view` | `/reservations`, `/api/reservations` |
| `reservations:write` | `/api/reservations/shift` |
| `guest-search:view` | `/api/guest-search` |
| `guest-search:extract` | `/api/guest-search/extract-name` |
| `full-access` | Composite role inheriting all granular roles |

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (with Docker Compose)
- Docker daemon running

## Environment Configuration

Copy the example environment file and adjust values:

```bash
cp docker/.env.docker.example docker/.env
```

Key variables (see `docker/.env.docker.example` for a complete list):

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_DOMAIN` | `https://out-customer.com` | Full domain with scheme |
| `APP_DOMAIN_HOST` | `out-customer.com` | Hostname only |
| `OIDC_REALM` | `production` | Keycloak realm |
| `OIDC_CLIENT_ID` | `concierge` | OIDC client ID |
| `OIDC_CLIENT_SECRET` | _(empty)_ | Set by keycloak_setup.py |
| `CLIENT_API_CLIENT_SECRET` | _(empty)_ | Set by keycloak_setup.py |
| `KEYCLOAK_ADMIN_USER` | `admin` | Keycloak admin username |
| `KEYCLOAK_ADMIN_PASSWORD` | `admin` | Keycloak admin password |
| `SYNC_INTERVAL` | `10` | Role-sync polling interval in seconds |
| `OAUTH2_COOKIE_SECRET` | _(random)_ | oauth2-proxy cookie signing secret |
| `VALKEY_URL` | `redis://valkey:6379/0` | Valkey/Redis connection URL |

## Build & Start

### Build images

```bash
cd docker
docker compose build
```

This builds the following images:
- `concos-frontend:latest` — Vite SPA built with Node.js, served by a minimal static file server
- `concos-frontend-two:latest` — Second tenant instance of the SPA (built with `BASE_URL=/app2`)
- `concos-backend:latest` — FastAPI app with Python 3.12 + uv
- `concos-client-backend:latest` — Service-to-service authentication demo
- `concos-role-sync:latest` — Role synchronization background service

### Start all services

```bash
docker compose up -d
```

### Stop all services

```bash
docker compose down
```

### View logs

```bash
docker compose logs -f
```

### View logs for a specific service

```bash
docker compose logs -f role-sync
docker compose logs -f keycloak
docker compose logs -f oidc
```

### Rebuild and restart (after code changes)

```bash
docker compose up -d --build
```

## Install Local CA Certificate

Caddy uses an internal CA to issue TLS certificates for `out-customer.com`. You must install the CA root certificate to access the site via HTTPS without browser warnings.

### Using the installation scripts (recommended)

After starting the services with `docker compose up -d`, run the appropriate script for your OS:

**macOS:**
```bash
chmod +x docker/install-cert-macos.sh
sudo bash docker/install-cert-macos.sh
```

**Windows (PowerShell as Administrator):**
```powershell
docker\install-cert-windows.ps1
```

**Linux:**
```bash
chmod +x docker/install-cert-linux.sh
sudo bash docker/install-cert-linux.sh
```

The script will:
1. Extract the CA certificate from the Caddy container
2. Install it to your system's trust store
3. Clean up temporary files

### Certificate persistence

The CA certificate is stored in the `caddy_config` Docker volume. As long as you don't delete this volume, the CA root certificate stays the same and you only need to install it **once**. Even if Caddy regenerates domain certificates, they're still signed by the same CA.

To extract the CA certificate from the running container at any time:
```bash
docker exec caddy cat /root/.local/share/caddy/pki/authorities/local/root.crt
```

## Accessing the Application

After installing the CA certificate, add `out-customer.com` to your hosts file if not already configured:

```bash
# macOS / Linux
echo "127.0.0.1 out-customer.com" | sudo tee -a /etc/hosts

# Windows (PowerShell as Administrator)
Add-Content -Path "C:\Windows\System32\drivers\etc\hosts" -Value "127.0.0.1 out-customer.com"
```

Then visit:
- **App1**: `https://out-customer.com/app1`
- **App2**: `https://out-customer.com/app2`
- **Root fallback**: `https://out-customer.com` (routed to App1)

## Running Tests

The test suite is located in `docker/tests/` and runs inside a Docker container connected to the `app-network`, allowing it to reach Keycloak, Caddy, and Valkey.

### Prerequisites

The main services must be running before executing tests:

```bash
docker compose up -d
```

### Run all tests

```bash
cd docker
docker compose -f docker-compose.yaml -f docker-compose.pytest.yaml run --rm pytest
```

This builds the `concos-pytest:latest` image on first run, then executes all tests.

### Run specific tests

```bash
# Run a single test file
docker compose -f docker-compose.yaml -f docker-compose.pytest.yaml run --rm pytest pytest tests/test_pure_functions.py -v

# Run a specific test class
docker compose -f docker-compose.yaml -f docker-compose.pytest.yaml run --rm pytest pytest tests/test_keycloak_auth.py::TestLiveKeycloakAuth -v

# Run a single test method
docker compose -f docker-compose.yaml -f docker-compose.pytest.yaml run --rm pytest pytest tests/test_pure_functions.py::TestHasRoleEvents::test_detects_create_role_event -v

# Run tests matching a pattern
docker compose -f docker-compose.yaml -f docker-compose.pytest.yaml run --rm pytest pytest tests/ -k "test_issuer" -v
```

### Local Development Override

By default, the tests use Docker container names for service discovery (e.g., `keycloak:8080`). To run tests against a locally running Keycloak instance:

```bash
OIDC_CONFIG_HOST=localhost docker compose -f docker-compose.yaml -f docker-compose.pytest.yaml run --rm pytest
```

### Test Categories

| Test File | Description | Requires Running Stack |
|-----------|-------------|----------------------|
| `test_pure_functions.py` | Unit tests for role_sync pure functions | No |
| `test_event_persistence.py` | Valkey-backed event persistence | Valkey only |
| `test_keycloak_auth.py` | Keycloak authentication & role fetching | Keycloak |
| `test_keycloak_events.py` | Keycloak events API & realm config | Keycloak |
| `test_oidc_config.py` | OIDC config consistency & reachability | Keycloak + Caddy |
| `test_rbac_routes_to_keycloak.py` | RBAC routes mapping validation | Keycloak |
| `test_routes_persistence.py` | Route persistence to rbac_routes.json | Keycloak |
| `test_sync_flow.py` | Full sync flow (Keycloak → Caddy) | Keycloak + Caddy |
| `test_valkey_session.py` | Valkey session storage & invalidation | Keycloak + Caddy + Valkey |

## Keycloak Setup

The Keycloak admin console is available at:
```
https://out-customer.com/auth/admin#/master
```

### Initial Keycloak Configuration

Run the setup script from **inside the Docker network** to provision realms, users, roles, and clients:

```bash
docker run --rm --network docker_app-network \
  -v "$(pwd)/docker":/work python:3.12-slim \
  bash -c "cd /work && pip install requests pydantic -q && python3 keycloak_setup.py keycloak 8080"
```

This creates:
- **Realms**: `testing`, `production`
- **Roles**: Granular roles loaded from `rbac_routes.json` (`settings:view`, `models:admin`, `prompts:admin`, `performance:view`, `performance:run`, `reservations:view`, `reservations:write`, `guest-search:view`, `guest-search:extract`)
- **Composite role**: `full-access` (inherits all granular roles)
- **Users**: `user1` (password: `password1`, roles: `reservations:view`, `guest-search:view`), `user2` (password: `password2`, role: `full-access`)
- **Client**: `concierge` (confidential, PKCE S256, `realm_access.roles` claim in access token)
- **Client API**: `client-api` (confidential, Client Credentials Grant, service accounts enabled)

**Important:** Keycloak 26 always generates a random client secret (ignoring any value passed in the request). The `keycloak_setup.py` script handles this automatically by reading back the generated secrets after client creation, printing them to stdout, and updating `docker/.env` with `OIDC_CLIENT_SECRET` and `CLIENT_API_CLIENT_SECRET`.

### Sync Role Attributes to Keycloak

After the initial Keycloak setup, the roles exist in Keycloak but **without attributes** (paths, messages). The `rbac_routes_to_keycloak.py` script reads `docker/rbac_routes.json` and injects the `paths` and `message` attributes into each Keycloak role.

**When to run:**
- After initial Keycloak setup (`keycloak_setup.py`)
- When `rbac_routes.json` has been modified (new roles, paths, or messages)

**Run via Docker (recommended):**

```bash
docker run --rm --network docker_app-network \
  -v "$(pwd)/docker":/work python:3.12-slim \
  bash -c "cd /work && pip install requests pydantic -q && python3 rbac_routes_to_keycloak.py"
```

**Run locally (with Keycloak URL override):**

```bash
cd docker
KEYCLOAK_URL=http://localhost:8080/auth python rbac_routes_to_keycloak.py
```

This updates each role in Keycloak with:
- `paths` — The paths protected by the role (from `rbac_routes.json`)
- `message` — The access denied message for the role

### Full Setup Sequence

The complete order of operations to bootstrap the RBAC system:

1. **Start services:** `docker compose up -d`
2. **Wait for Keycloak to be ready:** `docker compose logs -f keycloak`
3. **Run Keycloak setup:** (see "Initial Keycloak Configuration" above)
4. **Inject role attributes:** (see "Sync Role Attributes to Keycloak" above)
5. **Restart services:** (see "Restart Services After Setup" below)

### Restart Services After Setup

After running the setup scripts, restart oauth2-proxy and role-sync to pick up the updated client secrets and role attributes:

```bash
docker compose restart oidc role-sync
```

### Regenerating the Keycloak Configuration

To completely reset and regenerate the Keycloak configuration from scratch:

1. **Stop all services:**
   ```bash
   docker compose down
   ```

2. **Remove the Keycloak data volume** (this will delete all Keycloak data):
   ```bash
   docker volume rm docker_keycloak_data
   ```
   > Note: Check `docker volume ls` for the exact volume name. If you're using default Docker Compose volumes, the Keycloak container state is ephemeral (no persistent volume), so simply restarting is sufficient.

3. **Clear the client secrets** in `docker/.env`:
   ```bash
   sed -i.bak 's/OIDC_CLIENT_SECRET=.*/OIDC_CLIENT_SECRET=/' docker/.env
   sed -i.bak 's/CLIENT_API_CLIENT_SECRET=.*/CLIENT_API_CLIENT_SECRET=/' docker/.env
   ```

4. **Start services fresh:**
   ```bash
   docker compose up -d
   ```

5. **Wait for Keycloak to start** (check logs):
   ```bash
   docker compose logs -f keycloak
   ```
   Wait until you see the server is ready.

6. **Run the Keycloak setup:**
   ```bash
   docker run --rm --network docker_app-network \
     -v "$(pwd)/docker":/work python:3.12-slim \
     bash -c "cd /work && pip install requests pydantic -q && python3 keycloak_setup.py keycloak 8080"
   ```

7. **Inject role attributes:**
   ```bash
   docker run --rm --network docker_app-network \
     -v "$(pwd)/docker":/work python:3.12-slim \
     bash -c "cd /work && pip install requests pydantic -q && python3 rbac_routes_to_keycloak.py"
   ```

8. **Restart oauth2-proxy and role-sync:**
    ```bash
    docker compose restart oidc role-sync
    ```

### Diagnostic Script

To inspect Keycloak configuration (realms, users, roles, clients):

```bash
docker run --rm --network docker_app-network \
  -v "$(pwd)/docker":/work python:3.12-slim \
  bash -c "cd /work && pip install requests -q && python3 debug/keycloak_diagnose.py keycloak 8080"
```

### Users and Access Control

| User | Password | Roles | Access |
|------|----------|-------|--------|
| user1 | password1 | `reservations:view`, `guest-search:view` | `/reservations`, `/api/reservations`, `/api/guest-search` |
| user2 | password2 | `full-access` | All pages |

## Troubleshooting

### Certificate not trusted

Re-run the certificate installation steps for your OS. On macOS, you may need to explicitly set the certificate to "Always Trust" in Keychain Access.

### Services not starting

Check logs for errors:
```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f caddy
docker compose logs -f role-sync
docker compose logs -f keycloak
```

### Port already in use

If ports 80 or 443 are occupied, modify the port mappings in `docker-compose.yaml`:
```yaml
ports:
  - "8080:80"
  - "8443:443"
```
Then access via `https://out-customer.com:8443`.

### Role-sync not syncing

Check role-sync logs for connection issues:
```bash
docker compose logs -f role-sync
```

Common issues:
- Keycloak not ready yet (role-sync waits up to 120 seconds on startup)
- Caddy admin API unreachable (port 2019)
- Valkey unreachable (port 6379)
- Invalid `OIDC_CLIENT_SECRET` in `.env`

### Role changes not reflected

The role-sync service polls every 10 seconds by default (configurable via `SYNC_INTERVAL`). If changes don't appear after 10-15 seconds:

1. Check role-sync is running: `docker compose ps role-sync`
2. Check logs for errors: `docker compose logs -f role-sync`
3. Restart role-sync: `docker compose restart role-sync`

## Accepted tradeoff

`server.js` is needed because without it Caddy would have to serve the static files, thus `/api/*` would have to be exposed as well. Since the purpose of this setup is to secure FastAPI and expose only the frontend, `server.js` was created as a lightweight static file server with built-in API proxy.

## Role-Sync Service

The `role-sync` service (`docker/role_sync.py`) is a background process that keeps Caddy's access control rules in sync with Keycloak roles.

### How it works

1. **Startup**: Waits for Keycloak and Caddy to be ready, then performs an initial full sync
2. **Polling**: Every `SYNC_INTERVAL` seconds (default: 10), polls Keycloak's Admin Events API
3. **Role change detection**: Detects role create, update, and delete operations
4. **Route regeneration**: On role changes, fetches all roles with their attributes from Keycloak, generates Caddy deny rules, and pushes them via the Caddy Admin API
5. **Session invalidation**: On user deletion events, invalidates all sessions stored in Valkey
6. **Persistence**: Syncs role attributes back to `rbac_routes.json` for documentation and version control

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `KEYCLOAK_URL` | `http://keycloak:8080/auth` | Keycloak base URL |
| `KEYCLOAK_REALM` | `production` | Keycloak realm |
| `KEYCLOAK_ADMIN_USER` | `admin` | Keycloak admin username |
| `KEYCLOAK_ADMIN_PASSWORD` | `admin` | Keycloak admin password |
| `CADDY_ADMIN_URL` | `http://caddy:2019` | Caddy Admin API URL |
| `SYNC_INTERVAL` | `10` | Polling interval in seconds |
| `VALKEY_URL` | `redis://valkey:6379/0` | Valkey/Redis connection URL |
| `SESSION_COOKIE_NAME` | `_oauth2_proxy` | oauth2-proxy session cookie name |

## Client-Backend Service

The `client-backend` service (`client_backend/`) demonstrates service-to-service authentication using Keycloak's Client Credentials Grant.

### Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /client-api/health` | Health check |
| `GET /client-api/token-info` | Inspect current OAuth2 token |
| `POST /client-api/refresh-token` | Force token refresh |
| `GET /client-api/me` | Current user's roles and accessible menu items (reads `X-Forwarded-Groups` header) |
| `GET /client-api/backend/health` | Proxy to main backend's root endpoint |
| `GET /client-api/backend/models` | Proxy to main backend's `/api/models` |
| `GET /client-api/backend/settings` | Proxy to main backend's `/api/settings` |
| `POST /client-api/backend/{path}` | Generic POST proxy to any backend endpoint |

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `KEYCLOAK_URL` | `http://keycloak:8080/auth` | Keycloak base URL |
| `KEYCLOAK_REALM` | `production` | Keycloak realm |
| `CLIENT_API_CLIENT_ID` | `client-api` | OAuth2 client ID |
| `CLIENT_API_CLIENT_SECRET` | _(required)_ | OAuth2 client secret (set by keycloak_setup.py) |
| `BACKEND_URL` | `http://backend:8000` | Main backend URL |