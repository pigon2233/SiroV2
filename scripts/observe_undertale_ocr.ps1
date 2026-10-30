# Windows PowerShell 5.1: one read-only frame, no disk images, no raw text output and no inputs.
param([switch]$CompareModel)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Globalization.Language, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class SiroOcrWindow {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
}
'@
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and
  $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1
if ($null -eq $asTask) { throw 'winrt_async_adapter_unavailable' }
function Await-Operation($operation, [Type]$resultType) {
  $task = $asTask.MakeGenericMethod($resultType).Invoke($null, @($operation))
  return $task.GetAwaiter().GetResult()
}

$handle = [SiroOcrWindow]::GetForegroundWindow(); [uint32]$pidValue = 0
[void][SiroOcrWindow]::GetWindowThreadProcessId($handle, [ref]$pidValue)
if ($handle -eq [IntPtr]::Zero -or $pidValue -eq 0) { throw 'no_foreground_window' }
if ([System.Diagnostics.Process]::GetProcessById([int]$pidValue).ProcessName.ToLowerInvariant() -ne 'undertale') { throw 'undertale_not_foreground' }
$rect = New-Object SiroOcrWindow+RECT
if (-not [SiroOcrWindow]::GetWindowRect($handle, [ref]$rect)) { throw 'window_rect_unavailable' }
$width = $rect.Right - $rect.Left; $height = $rect.Bottom - $rect.Top
if ($width -lt 64 -or $height -lt 64 -or $width -gt 4096 -or $height -gt 4096) { throw 'window_size_invalid' }
$bitmap = [System.Drawing.Bitmap]::new($width, $height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap); $dc = $graphics.GetHdc()
try { $ok = [SiroOcrWindow]::PrintWindow($handle, $dc, 2) }
finally { $graphics.ReleaseHdc($dc); $graphics.Dispose() }
$stream = $null; $randomStream = $null; $softwareBitmap = $null
try {
  [uint32]$afterPid = 0; $after = [SiroOcrWindow]::GetForegroundWindow()
  [void][SiroOcrWindow]::GetWindowThreadProcessId($after, [ref]$afterPid)
  if (-not $ok -or $after -ne $handle -or $afterPid -ne $pidValue) { throw 'capture_or_foreground_changed' }
  $stream = [System.IO.MemoryStream]::new()
  $bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
  $stream.Position = 0
  $randomStream = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($stream)
  $decoder = Await-Operation ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($randomStream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $softwareBitmap = Await-Operation ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $ocrTexts = @{}
  foreach ($language in @('en-US', 'ja')) {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new($language))
    if ($null -eq $engine) { Write-Output ($language + ': unavailable'); continue }
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $result = Await-Operation ($engine.RecognizeAsync($softwareBitmap)) ([Windows.Media.Ocr.OcrResult])
    $watch.Stop()
    $text = [string]$result.Text
    $ocrTexts[$language] = $text
    $japanese = [regex]::Matches($text, '[\u3040-\u30ff\u3400-\u9fff]').Count
    Write-Output ($language + ': lines=' + @($result.Lines).Count + '; characters=' + $text.Length +
      '; japanese_characters=' + $japanese + '; ocr_seconds=' + [Math]::Round($watch.Elapsed.TotalSeconds, 4))
  }
  if ($CompareModel) {
    $payload = @{
      model = 'gemma4:e4b'; stream = $false; think = $false
      messages = @(@{role = 'user'; content = 'Transcribe all text visible in this image exactly. Use an empty string when no text is readable. Return JSON with a single field text.'; images = @([Convert]::ToBase64String($stream.ToArray()))})
      format = @{type = 'object'; properties = @{text = @{type = 'string'}}; required = @('text')}
      options = @{temperature = 0; num_ctx = 8192; num_predict = 256}
    } | ConvertTo-Json -Depth 10 -Compress
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $response = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:11434/api/chat' -ContentType 'application/json' -Body $payload -TimeoutSec 60
    $watch.Stop()
    $model = $response.message.content | ConvertFrom-Json
    if ($response.done_reason -ne 'stop' -or $null -eq $model.text -or $model.text -isnot [string]) { throw 'invalid_model_output' }
    $modelText = [regex]::Replace($model.text, '\s+', '').ToUpperInvariant()
    foreach ($language in $ocrTexts.Keys) {
      $ocrText = [regex]::Replace($ocrTexts[$language], '\s+', '').ToUpperInvariant()
      Write-Output ($language + ': exact_text_match=' + ($ocrText -eq $modelText))
    }
    Write-Output ('model_characters=' + $modelText.Length + '; model_seconds=' + [Math]::Round($watch.Elapsed.TotalSeconds, 4))
  }
} finally {
  if ($null -ne $softwareBitmap) { $softwareBitmap.Dispose() }
  if ($null -ne $randomStream) { $randomStream.Dispose() }
  if ($null -ne $stream) { $stream.Dispose() }
  $bitmap.Dispose()
}
