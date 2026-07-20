# Install Caddy CA Certificate (Windows)
# Run this script in PowerShell as Administrator

Write-Host "=== Installing Caddy CA Certificate (Windows) ===" -ForegroundColor Cyan

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator." -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator', then try again." -ForegroundColor Yellow
    exit 1
}

# Extract the CA certificate from the Caddy container
$crt = docker exec caddy cat /data/caddy/pki/authorities/local/root.crt 2>$null

if ([string]::IsNullOrWhiteSpace($crt)) {
    Write-Host "ERROR: Could not extract certificate. Is the Caddy container running?" -ForegroundColor Red
    Write-Host "Run 'docker compose up -d' first, then try again." -ForegroundColor Yellow
    exit 1
}

# Write to a temporary file
$tempCert = [System.IO.Path]::GetTempPath() + "caddy-ca.crt"
$crt | Out-File -FilePath $tempCert -Encoding ASCII

# Import to Trusted Root Certification Authorities
Write-Host "Installing certificate to Trusted Root store..." -ForegroundColor Yellow
Import-Certificate -FilePath $tempCert -CertStoreLocation Cert:\LocalMachine\Root

# Clean up
Remove-Item $tempCert

Write-Host ""
Write-Host "Certificate installed successfully!" -ForegroundColor Green
Write-Host "You may need to restart your browser for the changes to take effect." -ForegroundColor Green
Write-Host "Visit https://out-customer.com to verify." -ForegroundColor Green