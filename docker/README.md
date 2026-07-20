# ConciergeOS Docker Setup

## Architecture

```
Browser → Caddy (443) → frontend:80 → /api/* proxied to backend:8000
                                    → all other routes → static SPA
```

- **Caddy**: Reverse proxy and HTTPS terminator (internal CA)
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
server.js is needed because without it caddy would have to serve the static files thus "/api/*" has to be exposed as well. Since the purpose of this feature is to secure FastAPI and expose only frontend, server.js was created.

## Keycloak setup:
They keycloak admin can be found at:
```
https://out-customer.com/auth/admin#/master
```

To populate keycloak with users run:
```
python keycloak_setup.py localhost 8080
python update_oidc_secret.py localhost 8080
docker compose restart oidc-main oidc-settings
```