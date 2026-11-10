# Pure process-name matching helpers. No capture, focus or native input.
function ConvertTo-SiroProcessKey([string]$Name) {
  if (-not $Name -or $Name.Length -gt 80 -or $Name.IndexOfAny([char[]]"/\:`0") -ge 0) { return '' }
  $Name = $Name.Trim().ToLowerInvariant() -replace '\.exe$', ''
  $result = New-Object System.Text.StringBuilder
  foreach ($c in $Name.ToCharArray()) {
    if ([char]::IsLetterOrDigit($c)) { [void]$result.Append($c) }
    elseif ([char]::IsWhiteSpace($c) -or [char]::IsPunctuation($c) -or ([int]$c -ge 33 -and [int]$c -le 126)) { continue }
    else { return '' }
  }
  return $result.ToString()
}
function Select-SiroNormalizedProcess([object[]]$Candidates, [string]$Name) {
  $key = ConvertTo-SiroProcessKey $Name
  if (-not $key) { return $null }
  $matches = @($Candidates | Where-Object {
    $_.MainWindowHandle -ne 0 -and (ConvertTo-SiroProcessKey ($_.ProcessName + '.exe')) -ceq $key
  })
  # A canonical name collision or multiple windows is ambiguous: do not focus either.
  if ($matches.Count -ne 1) { return $null }
  return $matches[0]
}
