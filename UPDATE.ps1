# Saha AVC - get the latest version from GitHub and restart the backend.
#   powershell -ExecutionPolicy Bypass -File .\UPDATE.ps1
# Keeps your PC-only files (online-settings.json, cache, node_modules).
Set-Location $PSScriptRoot
$repo = 'https://github.com/shawonrealtor-code/SahaAgencyAVC'

Write-Host "1/3  Downloading the latest version..." -ForegroundColor Cyan
if ((Test-Path '.git') -and (Get-Command git -ErrorAction SilentlyContinue)) {
  git pull --ff-only
  if ($LASTEXITCODE -ne 0) { Write-Host "git pull failed." -ForegroundColor Red; exit 1 }
} else {
  $zip = Join-Path $env:TEMP 'saha-avc-latest.zip'
  $dir = Join-Path $env:TEMP 'saha-avc-latest'
  try {
    Invoke-WebRequest "$repo/archive/refs/heads/main.zip" -OutFile $zip -UseBasicParsing
  } catch {
    Write-Host "Download failed: $($_.Exception.Message)" -ForegroundColor Red; exit 1
  }
  Remove-Item $dir -Recurse -Force -ErrorAction SilentlyContinue
  Expand-Archive $zip $dir -Force
  $src = (Get-ChildItem $dir -Directory | Select-Object -First 1).FullName
  robocopy $src $PSScriptRoot /E /XD node_modules cache .git /XF online-settings.json /NFL /NDL /NJH /NJS /NP | Out-Null
  if ($LASTEXITCODE -ge 8) { Write-Host "Copying the new files failed (robocopy $LASTEXITCODE)." -ForegroundColor Red; exit 1 }
}

Write-Host "2/3  Rebuilding the backend..." -ForegroundColor Cyan
docker compose up -d --build --remove-orphans
if ($LASTEXITCODE -ne 0) { Write-Host "Docker failed. Is Docker Desktop running?" -ForegroundColor Red; exit 1 }
Push-Location '.\avatar-frontend'; npm.cmd install --no-fund --no-audit | Out-Null; Pop-Location

Write-Host "3/3  Checking..." -ForegroundColor Cyan
Start-Sleep -Seconds 5
try {
  $h = Invoke-RestMethod "http://127.0.0.1:8081/health" -TimeoutSec 10
  Write-Host ("OK: video answers {0} | instant answers {1} ({2} questions) | voice {3}" -f `
    $h.premade_answers, $h.instant_answers, $h.instant_questions, $h.voice) -ForegroundColor Green
  Write-Host "Her voice for the prepared answers is being recorded in the background (a few minutes, first time only)." -ForegroundColor Gray
} catch { Write-Host "Backend not answering yet. Check: docker logs saha-avc-api" -ForegroundColor Yellow }
