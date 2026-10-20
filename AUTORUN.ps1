# Saha AVC - keeps the whole concierge running (started hidden at Windows login by AUTOSTART-ON.ps1).
# Every 30 seconds it checks each part and starts whatever is not running:
#   Docker Desktop -> Ollama -> Kokoro voice -> backend -> screen server -> ngrok (online address)
# Log: logs\autorun.log
Set-Location $PSScriptRoot
$ErrorActionPreference = 'Continue'

# Only one copy at a time.
$mutex = New-Object System.Threading.Mutex($false, 'Local\SahaAVC-Autorun')
if (-not $mutex.WaitOne(0)) { exit 0 }

$logs = Join-Path $PSScriptRoot 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$logFile = Join-Path $logs 'autorun.log'
function Log($msg) {
  if ((Test-Path $logFile) -and (Get-Item $logFile).Length -gt 1MB) { Move-Item $logFile "$logFile.old" -Force }
  Add-Content -Path $logFile -Value ("{0:yyyy-MM-dd HH:mm:ss}  {1}" -f (Get-Date), $msg)
}
function Ok($url) {
  try { Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 5 | Out-Null; return $true } catch { return $false }
}
function Listening($port) {
  [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

$settings = @{}
$autoFile = Join-Path $PSScriptRoot 'autostart-settings.json'
if (Test-Path $autoFile) { $settings = Get-Content $autoFile -Raw | ConvertFrom-Json }
$online = $null
$onlineFile = Join-Path $PSScriptRoot 'online-settings.json'
if (Test-Path $onlineFile) { $online = Get-Content $onlineFile -Raw | ConvertFrom-Json }

Log "Autorun started."
$screenOpened = $false

while ($true) {
  # 1. Docker Desktop
  docker info *> $null
  if ($LASTEXITCODE -ne 0) {
    $exe = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (-not (Get-Process 'Docker Desktop' -ErrorAction SilentlyContinue) -and (Test-Path $exe)) {
      Log "Starting Docker Desktop..."
      Start-Process $exe
    }
    Start-Sleep -Seconds 15
    continue   # wait for Docker before anything else
  }

  # 2. Ollama (the AI)
  if (-not (Ok 'http://127.0.0.1:11434/api/tags')) {
    $app = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama app.exe'
    if (Test-Path $app) { Log "Starting Ollama..."; Start-Process $app }
    elseif (Get-Command ollama -ErrorAction SilentlyContinue) { Log "Starting ollama serve..."; Start-Process ollama -ArgumentList 'serve' -WindowStyle Hidden }
  }

  # 3. Kokoro (her voice) - the Docker container that publishes port 8880
  if (-not (Listening 8880)) {
    $kokoro = docker ps -a --filter 'publish=8880' --format '{{.Names}}' | Select-Object -First 1
    if ($kokoro) { Log "Starting voice container $kokoro..."; docker start $kokoro *> $null }
  }

  # 4. Backend
  if (-not (Ok 'http://127.0.0.1:8081/health')) {
    Log "Starting backend..."
    docker compose up -d *>> (Join-Path $logs 'docker.log')
  }

  # 5. Screen server (the concierge page on this PC / Wi-Fi)
  if (-not (Listening 5173)) {
    Log "Starting screen server..."
    Start-Process npm.cmd -ArgumentList 'run', 'dev' -WorkingDirectory (Join-Path $PSScriptRoot 'avatar-frontend') `
      -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'screen.log') -RedirectStandardError (Join-Path $logs 'screen-errors.log')
  }

  # 6. ngrok permanent address (so securepayllc.com works)
  if ($online -and $online.domain -and -not (Get-Process ngrok -ErrorAction SilentlyContinue)) {
    if (Get-Command ngrok -ErrorAction SilentlyContinue) {
      Log "Starting ngrok on $($online.domain)..."
      Start-Process ngrok -ArgumentList 'http', "--url=$($online.domain)", '8081', '--log=stdout' `
        -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'ngrok.log') -RedirectStandardError (Join-Path $logs 'ngrok-errors.log')
    }
  }

  # 7. Open the concierge screen once (full screen), if chosen in AUTOSTART-ON.ps1
  if (-not $screenOpened -and $settings.openScreen -and (Listening 5173) -and (Ok 'http://127.0.0.1:8081/health')) {
    $chrome = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
                "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
                "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($chrome) {
      $kioskProfile = Join-Path $env:LOCALAPPDATA 'SahaAVC\kiosk-profile'
      Start-Process $chrome -ArgumentList "--kiosk", "--user-data-dir=`"$kioskProfile`"", "--no-first-run",
        "--autoplay-policy=no-user-gesture-required", "--use-fake-ui-for-media-stream", "http://localhost:5173"
    } else {
      Start-Process "http://localhost:5173"
    }
    Log "Concierge screen opened."
    $screenOpened = $true
  }

  Start-Sleep -Seconds 30
}
