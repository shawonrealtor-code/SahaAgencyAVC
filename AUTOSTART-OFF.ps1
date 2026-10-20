# Saha AVC - stop starting the concierge automatically at login.
#   powershell -ExecutionPolicy Bypass -File .\AUTOSTART-OFF.ps1
$task = 'Saha AVC Concierge'
Stop-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
  Where-Object { $_.CommandLine -like '*AUTORUN.ps1*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Write-Host "Autostart is off. The backend, ngrok and screen keep running until you close them or restart." -ForegroundColor Green
Write-Host "Use START.ps1 and ONLINE.ps1 to start things by hand." -ForegroundColor Gray
