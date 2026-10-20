# Saha AVC - start the concierge automatically every time this PC logs in.
#   powershell -ExecutionPolicy Bypass -File .\AUTOSTART-ON.ps1
# Turn it off again with AUTOSTART-OFF.ps1.
Set-Location $PSScriptRoot
$task = 'Saha AVC Concierge'

if (-not (Test-Path (Join-Path $PSScriptRoot 'online-settings.json'))) {
  Write-Host "Note: ONLINE.ps1 has not been set up yet, so securepayllc.com won't be connected." -ForegroundColor Yellow
  Write-Host "      Run ONLINE.ps1 once first if you use the hosted website." -ForegroundColor Yellow
}

# 1. Open the concierge screen full screen on this PC at login?
$answer = Read-Host "Also open the concierge screen full screen on THIS PC at login? (y/n)"
@{ openScreen = ($answer -match '^(y|yes)$') } | ConvertTo-Json | Set-Content (Join-Path $PSScriptRoot 'autostart-settings.json') -Encoding UTF8

# 2. Windows task: run AUTORUN.ps1 hidden at login.
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
  -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSScriptRoot\AUTORUN.ps1`"" `
  -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
try {
  Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
} catch {
  Write-Host "Could not create the startup task: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "Try again in a PowerShell opened with 'Run as administrator'." -ForegroundColor Yellow
  exit 1
}
Write-Host "Startup task created: '$task' (runs hidden at every login)." -ForegroundColor Green

# 3. Keep the PC awake while plugged in (it can't answer while asleep).
powercfg /change standby-timeout-ac 0 | Out-Null
$sleepOk = ($LASTEXITCODE -eq 0)
powercfg /change hibernate-timeout-ac 0 | Out-Null
if ($sleepOk) { Write-Host "Sleep turned off while plugged in (the screen can still turn off)." -ForegroundColor Green }
else { Write-Host "Could not change sleep. Set it by hand: Settings > System > Power > Sleep: Never (plugged in)." -ForegroundColor Yellow }

# 4. Docker Desktop and Ollama also start with Windows (AUTORUN starts them too, as a backup).
Write-Host "Tip: in Docker Desktop > Settings > General, tick 'Start Docker Desktop when you sign in'." -ForegroundColor Gray

# 5. Start it now. Close the old START / ONLINE windows first so nothing runs twice.
Write-Host ""
Write-Host "Close any open START (npm run dev) and ONLINE (ngrok) windows now, then press Enter." -ForegroundColor Cyan
Read-Host | Out-Null
Start-ScheduledTask -TaskName $task
Write-Host "Started. Everything comes up in about a minute (longer right after a reboot)." -ForegroundColor Green
Write-Host "Check progress any time in: $PSScriptRoot\logs\autorun.log" -ForegroundColor Gray
