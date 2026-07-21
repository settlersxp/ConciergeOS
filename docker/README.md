# ConciergeOS Docker Setup

## Architecture

```
Browser → Caddy (443) → oauth2-proxy (oidc-main:4182) → Caddy internal (8000)
                                                 ├─ static assets → frontend:80 (always allowed)
                                                 ├─ /settings → deny if group "all"
                                                 ├─ !/settings → deny if group "single"
                                                 └─ allow → frontend:80
                                                              → /api/* proxied to backend:8000
                                                              → all other routes → static SPA
```

- **Caddy (https-server)**: Reverse proxy and HTTPS terminator (internal CA), routes `/auth/*` to Keycloak and all other traffic to oauth2-proxy
- **Caddy (internal-server)**: Internal server on port 8000 that enforces group-based access control using `X-Forwarded-Groups` header from oauth2-proxy:
  - Static assets (`.css`, `.js`, fonts, images) are always allowed through to frontend
  - Users in group `single`: access only `/settings` (403 on all other paths)
  - Users in group `all`: access all pages (403 on `/settings`)
- **oauth2-proxy (oidc-main)**: Handles OIDC authentication with Keycloak, passes user groups via `X-Forwarded-Groups` header
- **Keycloak**: OIDC identity provider (realms: `testing`, `production`; users: `user1`→single, `user2`→all)
- **Frontend**: Node.js static file server with built-in API proxy to backend
- **Backend**: FastAPI application (not directly accessible from outside Docker network)

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (with Docker Compose)
- Docker daemon running

## Build & Start

### Build images

```bash
docker compose build
```

This builds both images:
- `concos-frontend:latest` — Vite SPA built with Node.js, served by a minimal static file server
- `concos-backend:latest` — FastAPI app with Python 3.12 + uv

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

Then visit: `https://out-customer.com`

## Troubleshooting

### Certificate not trusted

Re-run the certificate installation steps for your OS. On macOS, you may need to explicitly set the certificate to "Always Trust" in Keychain Access.

### Services not starting

Check logs for errors:
```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f caddy
```

### Port already in use

If ports 80 or 443 are occupied, modify the port mappings in `docker-compose.yaml`:
```yaml
ports:
  - "8080:80"
  - "8443:443"
```
Then access via `https://out-customer.com:8443`.

## Accepted tradeoff

`server.js` is needed because without it Caddy would have to serve the static files, thus `/api/*` would have to be exposed as well. Since the purpose of this setup is to secure FastAPI and expose only the frontend, `server.js` was created as a lightweight static file server with built-in API proxy.

## Keycloak Setup

The Keycloak admin console is available at:
```
https://out-customer.com/auth/admin#/master
```

### Initial Keycloak Configuration

Run the setup script from **inside the Docker network** to provision realms, users, groups, and clients:

```bash
docker run --rm --network docker_app-network \
  -v "$(pwd)/docker":/work python:3.12-slim \
  bash -c "cd /work && pip install requests -q && python3 keycloak_setup.py keycloak 8080"
```

This creates:
- **Realms**: `testing`, `production`
- **Groups**: `single` (settings-only access), `all` (full access)
- **Users**: `user1` (password: `password1`, group: `single`), `user2` (password: `password2`, group: `all`)
- **Client**: `concierge` (confidential, PKCE S256, groups claim in ID token)

**Important:** Keycloak 26 always generates a random client secret (ignoring any value passed in the request). The `keycloak_setup.py` script handles this automatically by reading back the generated secret after client creation and writing it to `oidc-main.toml`. No manual secret synchronization is needed.

### Restart Services After Setup

After running the setup script, restart oauth2-proxy to pick up the updated client secret:

```bash
docker compose restart oidc-main
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

3. **Reset the `oidc-main.toml` client secret** to `changeme` (placeholder value):
   ```bash
   sed -i.bak 's/client_secret = .*/client_secret = "changeme"/' docker/oidc-main.toml
   ```

4. **Start services fresh:**
   ```bash
   docker compose up -d
   ```

5. **Wait for Keycloak to start** (check logs):
   ```bash
   docker compose logs -f keycloak
   ```
   Wait until you see `KEYCLOAK_SKIP_INITIAL_HEALTH_CHECK=false` and the server is ready.

6. **Run the setup script:**
   ```bash
   docker run --rm --network docker_app-network \
     -v "$(pwd)/docker":/work python:3.12-slim \
     bash -c "cd /work && pip install requests -q && python3 keycloak_setup.py keycloak 8080"
   ```

7. **Restart oauth2-proxy:**
   ```bash
   docker compose restart oidc-main
   ```

### Diagnostic Script

To inspect Keycloak configuration (realms, users, groups, clients):

```bash
docker run --rm --network docker_app-network \
  -v "$(pwd)/docker":/work python:3.12-slim \
  bash -c "cd /work && pip install requests -q && python3 keycloak_diagnose.py"
```

### Users and Access Control

| User   | Password  | Group    | Access                         |
|--------|-----------|----------|--------------------------------|
| user1  | password1 | single   | `/settings` only               |
| user2  | password2 | all      | All pages (except `/settings`) |

Access control is enforced by Caddy's internal server (port 8000) using the `X-Forwarded-Groups` header set by oauth2-proxy.