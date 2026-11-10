# Re-run the Windows launcher with no console. SIRO_SELF and SIRO_RELAUNCH_ARGS
# are set by Start-SIRO-VRM-Win.cmd. /s makes cmd strip one pair of wrapping quotes.
$ErrorActionPreference = "Stop"
$self = $env:SIRO_SELF
$relaunch = $env:SIRO_RELAUNCH_ARGS
if ([string]::IsNullOrWhiteSpace($self)) { exit 1 }
$command = '"' + $self + '" ' + $relaunch
$argument = '/d /s /c "' + $command + '"'
Start-Process -FilePath $env:ComSpec -ArgumentList $argument -WindowStyle Hidden
