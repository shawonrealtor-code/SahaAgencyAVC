# Saha AVC 3.1 - one-time install. Run from this folder:
#   powershell -ExecutionPolicy Bypass -File .\INSTALL.ps1
Set-Location $PSScriptRoot

Write-Host "1/4  Removing the old lip-sync service (no longer used)..." -ForegroundColor Cyan
docker rm -f saha-avc-face 2>$null | Out-Null

Write-Host "2/4  Building and starting the backend..." -ForegroundColor Cyan
docker compose up -d --build --remove-orphans
if ($LASTEXITCODE -ne 0) { Write-Host "Docker failed. Is Docker Desktop running?" -ForegroundColor Red; exit 1 }

Write-Host "3/4  Installing the screen..." -ForegroundColor Cyan
Push-Location ".\avatar-frontend"
npm.cmd install
Pop-Location

Write-Host "4/4  Checking the backend..." -ForegroundColor Cyan
Start-Sleep -Seconds 5
try {
  $h = Invoke-RestMethod "http://127.0.0.1:8081/health" -TimeoutSec 10
  Write-Host ("OK: " + $h.knowledge + " | premade answers: " + $h.premade_answers + " | voice: " + $h.voice) -ForegroundColor Green
} catch { Write-Host "Backend not answering yet. Check: docker logs saha-avc-api" -ForegroundColor Yellow }

Write-Host "`nInstalled. Start it with:  powershell -ExecutionPolicy Bypass -File .\START.ps1"
Write-Host "Optional: free about 15 GB from the old lip-sync image with:  docker image rm saha-avc-face"
