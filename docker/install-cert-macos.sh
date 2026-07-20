#!/usr/bin/env bash
set -e

echo "=== Installing Caddy CA Certificate (macOS) ==="

# Extract the CA certificate from the Caddy container
CERT=$(docker exec caddy cat /data/caddy/pki/authorities/local/root.crt)

if [ -z "$CERT" ]; then
    echo "ERROR: Could not extract certificate. Is the Caddy container running?"
    echo "Run 'docker compose up -d' first, then try again."
    exit 1
fi

# Write to a temporary file
TEMP_CERT=$(mktemp /tmp/caddy-ca-XXXXXX.crt)
echo "$CERT" > "$TEMP_CERT"

# Install to system keychain
echo "Installing certificate to system keychain..."
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain "$TEMP_CERT"

# Set trust settings for SSL
sudo security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k /Library/Keychains/System.keychain

# Clean up
rm "$TEMP_CERT"

echo ""
echo "Certificate installed successfully!"
echo "You may need to restart your browser for the changes to take effect."
echo "Visit https://out-customer.com to verify."