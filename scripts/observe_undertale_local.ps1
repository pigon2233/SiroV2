# Read-only, one-frame diagnostic. Image stays in memory and goes only to loopback Ollama.
# No desktop input, process launch, save-file access, screenshot files, or raw transcript output.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class SiroReadOnlyGameWindow {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
}
'@

$handle = [SiroReadOnlyGameWindow]::GetForegroundWindow()
[uint32]$pidValue = 0
[void][SiroReadOnlyGameWindow]::GetWindowThreadProcessId($handle, [ref]$pidValue)
if ($handle -eq [IntPtr]::Zero -or $pidValue -eq 0) { throw 'no_foreground_window' }
$proc = [System.Diagnostics.Process]::GetProcessById([int]$pidValue)
if ($proc.ProcessName.ToLowerInvariant() -ne 'undertale') { throw 'undertale_not_foreground' }
$rect = New-Object SiroReadOnlyGameWindow+RECT
if (-not [SiroReadOnlyGameWindow]::GetWindowRect($handle, [ref]$rect)) { throw 'window_rect_unavailable' }
$width = $rect.Right - $rect.Left; $height = $rect.Bottom - $rect.Top
if ($width -lt 64 -or $height -lt 64 -or $width -gt 4096 -or $height -gt 4096) { throw 'window_size_invalid' }
$bitmap = [System.Drawing.Bitmap]::new($width, $height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$dc = $graphics.GetHdc()
try { $ok = [SiroReadOnlyGameWindow]::PrintWindow($handle, $dc, 2) }
finally { $graphics.ReleaseHdc($dc); $graphics.Dispose() }
try {
  [uint32]$afterPid = 0
  $after = [SiroReadOnlyGameWindow]::GetForegroundWindow()
  [void][SiroReadOnlyGameWindow]::GetWindowThreadProcessId($after, [ref]$afterPid)
  if (-not $ok -or $after -ne $handle -or $afterPid -ne $pidValue) { throw 'capture_or_foreground_changed' }
  $nonblack = 0
  for ($x = 0; $x -lt 10; $x++) { for ($y = 0; $y -lt 10; $y++) {
    $color = $bitmap.GetPixel([int](($width - 1) * $x / 9), [int](($height - 1) * $y / 9))
    if ($color.R + $color.G + $color.B -gt 15) { $nonblack++ }
  } }
  if ($nonblack -eq 0) { Write-Output 'scene=blank_or_capture_unsupported'; exit 0 }
  $stream = [System.IO.MemoryStream]::new()
  try {
    $bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
    $payload = @{
      model = 'gemma4:e4b'; stream = $false; think = $false
      messages = @(@{ role = 'user'; content = 'Classify this game image as one of title, menu, dialogue, gameplay, black, unknown. Return JSON with a single field scene. Do not transcribe text or names.'; images = @([Convert]::ToBase64String($stream.ToArray())) })
      format = @{ type = 'object'; properties = @{ scene = @{ type = 'string'; enum = @('title','menu','dialogue','gameplay','black','unknown') } }; required = @('scene') }
      options = @{ temperature = 0; num_ctx = 8192; num_predict = 64 }
    } | ConvertTo-Json -Depth 10 -Compress
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $response = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:11434/api/chat' -ContentType 'application/json' -Body $payload -TimeoutSec 60
    $watch.Stop()
    $result = $response.message.content | ConvertFrom-Json
    if ($response.done_reason -ne 'stop' -or $result.scene -notin @('title','menu','dialogue','gameplay','black','unknown')) { throw 'invalid_model_output' }
    Write-Output ('scene=' + $result.scene + '; model_seconds=' + [Math]::Round($watch.Elapsed.TotalSeconds, 3))
  } finally { $stream.Dispose() }
} finally { $bitmap.Dispose() }
