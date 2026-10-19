# Saha AVC - put this PC's concierge backend online at a PERMANENT ngrok address,
# so https://securepayllc.com works for every visitor (no ?api= link needed).
#   powershell -ExecutionPolicy Bypass -File .\ONLINE.ps1
#
# One-time: free ngrok account -> copy your Authtoken and your free static domain
# (dashboard.ngrok.com > Domains). The script asks for both the first time and remembers them.
# Keep this window open - closing it takes the concierge offline.
Set-Location $PSScriptRoot
$settings = Join-Path $PSScriptRoot 'online-settings.json'   # stays on this PC (not uploaded to GitHub)

# 1. Backend must be running.
try { Invoke-RestMethod "http://127.0.0.1:8081/health" -TimeoutSec 5 | Out-Null }
catch {
  Write-Host "The backend is not running. Run START.ps1 first (Docker Desktop + Ollama)." -ForegroundColor Red
  exit 1
}

# 2. Install ngrok once.
if (-not (Get-Command ngrok -ErrorAction SilentlyContinue)) {
  Write-Host "Installing ngrok (one time)..." -ForegroundColor Cyan
  winget install --id Ngrok.Ngrok -e --accept-source-agreements --accept-package-agreements
  $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
  if (-not (Get-Command ngrok -ErrorAction SilentlyContinue)) {
    Write-Host "ngrok was installed but is not found yet. Close this window, open a new PowerShell and run ONLINE.ps1 again." -ForegroundColor Yellow
    exit 1
  }
}

# 3. Token + domain (asked once, then remembered).
$cfg = $null
if (Test-Path $settings) { $cfg = Get-Content $settings -Raw | ConvertFrom-Json }
if (-not $cfg -or -not $cfg.domain) {
  Write-Host ""
  Write-Host "First-time setup (from https://dashboard.ngrok.com):" -ForegroundColor Cyan
  $token = (Read-Host "Paste your ngrok Authtoken").Trim()
  $domain = (Read-Host "Paste your free static domain (e.g. saha-concierge.ngrok-free.app)").Trim()
  $domain = $domain -replace '^https?://', '' -replace '/.*$', ''
  if (-not $token -or -not $domain) { Write-Host "Both are needed. Run ONLINE.ps1 again." -ForegroundColor Red; exit 1 }
  ngrok config add-authtoken $token | Out-Null
  if ($LASTEXITCODE -ne 0) { Write-Host "ngrok did not accept the Authtoken. Check it and run again." -ForegroundColor Red; exit 1 }
  $cfg = [pscustomobject]@{ domain = $domain }
  $cfg | ConvertTo-Json | Set-Content $settings -Encoding UTF8
}

$url = "https://$($cfg.domain)"
Write-Host ""
Write-Host "Concierge backend going online at: $url" -ForegroundColor Green
Write-Host "The site file avatar-frontend/public/backend.json must contain:  { `"api`": `"$url`" }" -ForegroundColor Gray
Write-Host "Keep this window open. Press Ctrl+C to take it offline." -ForegroundColor Yellow
Write-Host ""

# 4. Run the tunnel (shows ngrok's live status screen; restarts if it drops).
while ($true) {
  ngrok http --url=$($cfg.domain) 8081
  Write-Host "ngrok stopped. Restarting in 5 seconds (Ctrl+C to quit)..." -ForegroundColor Yellow
  Start-Sleep -Seconds 5
}
