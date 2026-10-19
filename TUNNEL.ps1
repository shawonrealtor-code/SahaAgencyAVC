# Saha AVC - make this PC's concierge backend reachable from the internet,
# so the hosted website (securepayllc.com) and phones on any network get answers.
#   powershell -ExecutionPolicy Bypass -File .\TUNNEL.ps1
#
# Uses a free Cloudflare "quick tunnel" (no account needed). Keep this window open.
# The address changes each time this runs, so open the printed link again on each device.
Set-Location $PSScriptRoot
$Site = 'https://securepayllc.com'   # where the screen is hosted

# 1. Backend must be running.
try { Invoke-RestMethod "http://127.0.0.1:8081/health" -TimeoutSec 5 | Out-Null }
catch {
  Write-Host "The backend is not running. Run START.ps1 first (Docker Desktop + Ollama)." -ForegroundColor Red
  exit 1
}

# 2. Install cloudflared once.
if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
  Write-Host "Installing Cloudflare tunnel (one time)..." -ForegroundColor Cyan
  winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
  $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
  if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Host "cloudflared was installed but is not found yet. Close this window, open a new PowerShell and run TUNNEL.ps1 again." -ForegroundColor Yellow
    exit 1
  }
}

# 3. Start the tunnel and wait for its public address.
$log = Join-Path $env:TEMP 'saha-avc-tunnel.log'
Remove-Item $log -ErrorAction SilentlyContinue
$tunnel = Start-Process cloudflared -ArgumentList 'tunnel', '--no-autoupdate', '--url', 'http://localhost:8081' `
  -RedirectStandardError $log -PassThru -WindowStyle Hidden
Write-Host "Opening the secure tunnel..." -ForegroundColor Cyan

$url = $null
for ($i = 0; $i -lt 60 -and -not $url; $i++) {
  Start-Sleep -Seconds 1
  if (Test-Path $log) {
    $m = Select-String -Path $log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' | Select-Object -First 1
    if ($m) { $url = $m.Matches[0].Value }
  }
}
if (-not $url) {
  Write-Host "Could not open the tunnel. Last lines of $log :" -ForegroundColor Red
  if (Test-Path $log) { Get-Content $log -Tail 15 | ForEach-Object { Write-Host "  $_" } }
  if ($tunnel.HasExited) { Write-Host "cloudflared stopped with exit code $($tunnel.ExitCode)." -ForegroundColor Red }
  Stop-Process -Id $tunnel.Id -ErrorAction SilentlyContinue
  exit 1
}

$link = "$Site/?api=$url"
Set-Clipboard -Value $link
Write-Host ""
Write-Host "Backend is online at: $url" -ForegroundColor Green
Write-Host ""
Write-Host "Open this link once on each phone/tablet/screen (copied to clipboard):" -ForegroundColor Green
Write-Host "  $link" -ForegroundColor White
Write-Host ""
Write-Host "Each device remembers it. Keep this window open - closing it takes the concierge offline." -ForegroundColor Yellow

try { Wait-Process -Id $tunnel.Id }
finally { Stop-Process -Id $tunnel.Id -ErrorAction SilentlyContinue }
