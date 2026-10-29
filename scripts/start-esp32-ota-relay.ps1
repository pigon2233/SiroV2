# Start the ESP32 OTA/event relay hidden, but only when an OTA image is configured:
#   %USERPROFILE%\siro-ota\{firmware.bin, version.txt (x.y.z), node-ip.txt}
# Silent no-op otherwise (or when 8765 is taken), so SIRO startup is never affected.
$dir = Join-Path $env:USERPROFILE 'siro-ota'
foreach ($name in 'firmware.bin', 'version.txt', 'node-ip.txt') {
  if (-not (Test-Path (Join-Path $dir $name))) { exit 0 }
}
if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalAddress -eq '0.0.0.0' }) { exit 0 }
$token = (& "$env:SystemRoot\System32\wsl.exe" -d Ubuntu -- bash -c 'cat ~/.config/siro/esp32-relay-token 2>/dev/null') -join ''
$token = $token.Trim()
if ($token.Length -lt 32) { exit 0 }
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $env:LOCALAPPDATA 'siro\broker-venv\Scripts\python.exe'
if (-not (Test-Path $python)) { exit 0 }
$env:SIRO_ESP32_RELAY_TOKEN = $token
$env:SIRO_ESP32_ALLOWED_IP = (Get-Content (Join-Path $dir 'node-ip.txt') -TotalCount 1).Trim()
Start-Process -FilePath $python -ArgumentList '-I', (Join-Path $root 'scripts\esp32_http_receiver.py') -WindowStyle Hidden
