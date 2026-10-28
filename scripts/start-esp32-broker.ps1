# Start the ESP32 MQTT broker hidden unless something already listens on 1883.
# Silent no-op when secrets.h is absent, so SIRO startup is never affected.
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $root 'firmware\esp32\include\secrets.h'))) { exit 0 }
if (Get-NetTCPConnection -LocalPort 1883 -State Listen -ErrorAction SilentlyContinue) { exit 0 }
Start-Process -FilePath cmd.exe -ArgumentList '/c', ('"' + (Join-Path $root 'Start-ESP32-Broker.cmd') + '"') -WindowStyle Hidden
