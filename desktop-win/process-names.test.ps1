# Pure shared vectors only: does NOT load input-helper.ps1 or any native input.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'process-names.ps1')
$cases = Get-Content (Join-Path $PSScriptRoot '../tests/fixtures/computer-process-names.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($case in $cases) {
  $left = ConvertTo-SiroProcessKey $case[0]
  $right = ConvertTo-SiroProcessKey $case[1]
  $actual = [bool]($left -and $left -ceq $right)
  if ($actual -ne $case[2]) { throw "mismatch: $($case | ConvertTo-Json -Compress), $left/$right" }
}
$one = [pscustomobject]@{ProcessName='Slay the Spire 2';MainWindowHandle=123}
$other = [pscustomobject]@{ProcessName='slaythespire2helper';MainWindowHandle=124}
if ((Select-SiroNormalizedProcess @($one,$other) 'slaythespire2').MainWindowHandle -ne 123) { throw 'wrong process' }
if ($null -ne (Select-SiroNormalizedProcess @($one,$one) 'slaythespire2')) { throw 'ambiguous process accepted' }
Write-Output "native pure vectors passed: $($cases.Count); ambiguity rejected"

$tokens = $null; $errors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'input-helper.ps1'),[ref]$tokens,[ref]$errors)
if ($errors.Count -gt 0) { throw ($errors | Out-String) }
Write-Output 'input-helper syntax passed (NOT executed)'

# ProcessName is already a stem: preserve a meaningful embedded .exe instead of stripping twice.
$plain = [pscustomobject]@{ProcessName='game';MainWindowHandle=201}
$double = [pscustomobject]@{ProcessName='game.exe';MainWindowHandle=202}
if ((Select-SiroNormalizedProcess @($plain,$double) 'game.exe.exe').MainWindowHandle -ne 202) { throw 'double extension widened' }
if ($null -ne (Select-SiroNormalizedProcess @($double) 'game.exe')) { throw 'embedded exe removed' }
Write-Output 'stem/extension boundary passed'
