# Saha AVC 3.1 - starts everything and opens the concierge screen.
#   powershell -ExecutionPolicy Bypass -File .\START.ps1
Set-Location $PSScriptRoot

try { Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null }
catch { Write-Host "Ollama is not running. Open Ollama from the Start menu, then run this again." -ForegroundColor Red; exit 1 }

docker compose up -d
if ($LASTEXITCODE -ne 0) { Write-Host "Docker failed. Is Docker Desktop running?" -ForegroundColor Red; exit 1 }

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\avatar-frontend'; npm.cmd run dev"
Start-Sleep -Seconds 6
Start-Process "http://localhost:5173"
Write-Host "Opened http://localhost:5173 - press F11 in Chrome for full screen." -ForegroundColor Green
