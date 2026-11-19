# Point the desktop pet's electron.exe at a GPU before the process starts.
# Windows reads HKCU\Software\Microsoft\DirectX\UserGpuPreferences at launch.
# Keep the rules aligned with desktop-win/gpu-preference.js.
#   unset / low-power     -> GpuPreference=1 (integrated), but an existing value
#                            is left alone unless SIRO_PET_GPU is set explicitly
#   high-performance / discrete -> GpuPreference=2
#   default               -> do not write
param(
  [Parameter(Mandatory = $true)]
  [string] $ExePath
)

$ErrorActionPreference = 'Continue'
if (-not (Test-Path -LiteralPath $ExePath)) { exit 0 }

$raw = $env:SIRO_PET_GPU
if ($null -eq $raw) { $raw = '' }
$mode = $raw.Trim().ToLowerInvariant()
$explicit = $raw.Trim() -ne ''

if ($mode -eq 'default') { exit 0 }
$kind = 'low'
if ($mode -eq 'high-performance' -or $mode -eq 'discrete') { $kind = 'high' }
elseif ($mode -eq '' -or $mode -eq 'low-power') { $kind = 'low' }
else { exit 0 }

$key = 'HKCU\Software\Microsoft\DirectX\UserGpuPreferences'
$existing = $null
$query = & reg.exe query $key /v $ExePath 2>$null
if ($LASTEXITCODE -eq 0 -and $query) {
  $text = $query | Out-String
  if ($text -match 'GpuPreference=\d+;') { $existing = $Matches[0] }
}

$data = 'GpuPreference=1;'
if ($kind -eq 'high') { $data = 'GpuPreference=2;' }
elseif ($existing -and -not $explicit) { exit 0 }
if ($existing -eq $data) { exit 0 }

& reg.exe add $key /v $ExePath /t REG_SZ /d $data /f | Out-Null
exit 0
