# Makes a short sample of each female voice so you can compare them.
# Run from C:\Saha AVC 2.0 3D Test :   powershell -ExecutionPolicy Bypass -File .\voice-samples.ps1
$text = "Hello, and welcome to Saha Agency. I can help you with home, auto, and business insurance. How can I help you today?"
$voices = @(
  "af_heart","af_bella","af_nicole","af_sarah","af_sky","af_nova","af_jessica","af_river","af_aoede","af_kore","af_alloy",
  "bf_emma","bf_isabella","bf_alice","bf_lily",
  "af_heart+af_bella","af_heart+af_nicole"
)
$out = Join-Path $PSScriptRoot "voice-samples"
New-Item -ItemType Directory -Force -Path $out | Out-Null
foreach ($v in $voices) {
  $file = Join-Path $out (($v -replace '\+','_and_') + ".mp3")
  $body = @{ model = "kokoro"; input = $text; voice = $v; response_format = "mp3"; speed = 1.0 } | ConvertTo-Json
  try {
    Invoke-WebRequest -Method Post -Uri "http://127.0.0.1:8880/v1/audio/speech" -ContentType "application/json" -Body $body -OutFile $file
    Write-Host "OK   $v"
  } catch {
    Write-Host "SKIP $v (not available in your Kokoro)"
  }
}
Write-Host "`nDone. Opening the folder..."
Start-Process $out
