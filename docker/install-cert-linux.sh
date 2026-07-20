#!/usr/bin/env bash
set -e

echo "=== Installing Caddy CA Certificate (Linux) ==="

# Extract the CA certificate from the Caddy container
CERT=$(docker exec caddy cat /data/caddy/pki/authorities/local/root.crt)

if [ -z "$CERT" ]; then
    echo "ERROR: Could not extract certificate. Is the Caddy container running?"
    echo "Run 'docker compose up -d' first, then try again."
    exit 1
fi

# Write to system CA certificates directory
echo "Installing certificate to system trust store..."
echo "$CERT" | sudo tee /usr/local/share/ca-certificates/caddy-local-ca.crt > /dev/null

# Update the CA certificate store
if command -v update-ca-certificates &> /dev/null; then
    # Debian/Ubuntu
    sudo update-ca-certificates
elif command -v update-ca-trust &> /dev/null; then
    # RHEL/CentOS/Fedora
    sudo update-ca-trust extract
else
    echo "WARNING: Could not find update-ca-certificates or update-ca-trust."
    echo "Certificate installed to /usr/local/share/ca-certificates/caddy-local-ca.crt"
    echo "Please update your system's CA store manually."
fi

echo ""
echo "Certificate installed successfully!"
echo "You may need to restart your browser for the changes to take effect."
echo "Visit https://out-customer.com to verify."