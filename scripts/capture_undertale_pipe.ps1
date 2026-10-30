# Read one authorized foreground Undertale window to a pipe, never to a screenshot file.
# Pipe stdout directly to the paired readonly consumer; do not log or run this alone.
param([switch]$EmitToPipe)
$ErrorActionPreference = 'Stop'
if (-not $EmitToPipe) { throw 'explicit_pipe_flag_required' }
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class SiroProbeWindow {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
}
'@
$h = [SiroProbeWindow]::GetForegroundWindow(); [uint32]$p = 0
[void][SiroProbeWindow]::GetWindowThreadProcessId($h, [ref]$p)
if ($h -eq [IntPtr]::Zero -or $p -eq 0 -or [Diagnostics.Process]::GetProcessById([int]$p).ProcessName.ToLowerInvariant() -ne 'undertale') { throw 'undertale_not_foreground' }
$r = New-Object SiroProbeWindow+RECT
if (-not [SiroProbeWindow]::GetWindowRect($h, [ref]$r)) { throw 'window_rect_unavailable' }
$width = $r.Right - $r.Left; $height = $r.Bottom - $r.Top
if ($width -lt 64 -or $height -lt 64 -or $width -gt 4096 -or $height -gt 4096) { throw 'window_size_invalid' }
$bmp = [Drawing.Bitmap]::new($width, $height)
$g = [Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc()
try { $ok = [SiroProbeWindow]::PrintWindow($h, $dc, 2) }
finally { $g.ReleaseHdc($dc); $g.Dispose() }
try {
  $h2 = [SiroProbeWindow]::GetForegroundWindow(); [uint32]$p2 = 0
  [void][SiroProbeWindow]::GetWindowThreadProcessId($h2, [ref]$p2)
  $r2 = New-Object SiroProbeWindow+RECT
  if (-not $ok -or $h -ne $h2 -or $p -ne $p2 -or -not [SiroProbeWindow]::GetWindowRect($h2, [ref]$r2) -or
      $r.Left -ne $r2.Left -or $r.Top -ne $r2.Top -or $r.Right -ne $r2.Right -or $r.Bottom -ne $r2.Bottom) { throw 'capture_or_foreground_changed' }
  $nonblack = 0
  for ($x = 0; $x -lt 10; $x++) { for ($y = 0; $y -lt 10; $y++) {
    $c = $bmp.GetPixel([int](($width - 1) * $x / 9), [int](($height - 1) * $y / 9))
    if ($c.R + $c.G + $c.B -gt 15) { $nonblack++ }
  } }
  if ($nonblack -eq 0) { throw 'blank_or_capture_unsupported' }
  $stream = [IO.MemoryStream]::new()
  try {
    $bmp.Save($stream, [Drawing.Imaging.ImageFormat]::Png)
    if ($stream.Length -gt 6000000) { throw 'frame_too_large' }
    @{ image = [Convert]::ToBase64String($stream.ToArray()); width = $width; height = $height } | ConvertTo-Json -Compress
  } finally { $stream.Dispose() }
} finally { $bmp.Dispose() }
