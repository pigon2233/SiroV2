# Windows PowerShell 5.1 only. Reads generated fixtures on stdin; no desktop or game input.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Globalization.Language, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null

$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and
  $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1
if ($null -eq $asTask) { throw 'winrt_async_adapter_unavailable' }
function Await-Operation($operation, [Type]$resultType) {
  $task = $asTask.MakeGenericMethod($resultType).Invoke($null, @($operation))
  return $task.GetAwaiter().GetResult()
}

$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new('en-US'))
if ($null -eq $engine) { throw 'english_ocr_unavailable' }
$fixtures = [Console]::In.ReadToEnd() | ConvertFrom-Json
$rows = @()
foreach ($fixture in $fixtures) {
  $watch = [System.Diagnostics.Stopwatch]::StartNew()
  $row = @{ case = $fixture.case; expected = [bool]$fixture.expected; passed = $false }
  $stream = $null; $bitmap = $null; $randomStream = $null
  try {
    $bytes = [Convert]::FromBase64String([string]$fixture.image)
    $stream = New-Object System.IO.MemoryStream(,$bytes)
    $randomStream = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($stream)
    $decoder = Await-Operation ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($randomStream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await-Operation ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Await-Operation ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $text = [string]$result.Text
    $normalized = (($text.ToUpperInvariant() -replace '[^A-Z0-9]+', ' ').Trim())
    $actual = $normalized -eq 'UNDERTALE PRESS Z OR ENTER'
    $row.text = $text; $row.actual = $actual; $row.passed = ($actual -eq [bool]$fixture.expected)
  } catch { $row.error = $_.Exception.GetType().Name }
  finally {
    if ($null -ne $bitmap) { $bitmap.Dispose() }
    if ($null -ne $randomStream) { $randomStream.Dispose() }
    if ($null -ne $stream) { $stream.Dispose() }
  }
  $watch.Stop(); $row.seconds = [Math]::Round($watch.Elapsed.TotalSeconds, 4)
  $rows += $row
}
@{ engine = 'Windows.Media.Ocr en-US'; cases = $rows } | ConvertTo-Json -Depth 8
