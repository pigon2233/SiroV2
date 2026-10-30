# Read-only paired capture; output must go directly to paired consumer, never logs or a file.
param([switch]$EmitToPipe, [int]$WaitMs = 7500)
$ErrorActionPreference = 'Stop'
if (-not $EmitToPipe) { throw 'explicit_pipe_flag_required' }
if ($WaitMs -lt 5000 -or $WaitMs -gt 15000) { throw 'invalid_wait' }
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class SiroPairWindow {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
}
'@
$h = [SiroPairWindow]::GetForegroundWindow(); [uint32]$p = 0
[void][SiroPairWindow]::GetWindowThreadProcessId($h, [ref]$p)
if ($h -eq [IntPtr]::Zero -or $p -eq 0 -or [Diagnostics.Process]::GetProcessById([int]$p).ProcessName.ToLowerInvariant() -ne 'undertale') { throw 'undertale_not_foreground' }
$r = New-Object SiroPairWindow+RECT
if (-not [SiroPairWindow]::GetWindowRect($h, [ref]$r)) { throw 'window_rect_unavailable' }
$width = $r.Right - $r.Left; $height = $r.Bottom - $r.Top
if ($width -lt 64 -or $height -lt 64 -or $width -gt 4096 -or $height -gt 4096) { throw 'window_size_invalid' }
function Read-Frame {
  $current = [SiroPairWindow]::GetForegroundWindow(); [uint32]$currentPid = 0
  [void][SiroPairWindow]::GetWindowThreadProcessId($current, [ref]$currentPid)
  $currentRect = New-Object SiroPairWindow+RECT
  if ($current -ne $h -or $currentPid -ne $p -or -not [SiroPairWindow]::GetWindowRect($current, [ref]$currentRect) -or
      $r.Left -ne $currentRect.Left -or $r.Top -ne $currentRect.Top -or $r.Right -ne $currentRect.Right -or $r.Bottom -ne $currentRect.Bottom) { throw 'window_changed' }
  $bmp = [Drawing.Bitmap]::new($width, $height)
  $g = [Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc()
  try { $ok = [SiroPairWindow]::PrintWindow($h, $dc, 2) }
  finally { $g.ReleaseHdc($dc); $g.Dispose() }
  try {
    $after = [SiroPairWindow]::GetForegroundWindow(); [uint32]$afterPid = 0
    [void][SiroPairWindow]::GetWindowThreadProcessId($after, [ref]$afterPid)
    $afterRect = New-Object SiroPairWindow+RECT
    if (-not $ok -or $after -ne $h -or $afterPid -ne $p -or -not [SiroPairWindow]::GetWindowRect($after, [ref]$afterRect) -or
        $r.Left -ne $afterRect.Left -or $r.Top -ne $afterRect.Top -or $r.Right -ne $afterRect.Right -or $r.Bottom -ne $afterRect.Bottom) { throw 'capture_or_foreground_changed' }
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
      return ,$stream.ToArray()
    } finally { $stream.Dispose() }
  } finally { $bmp.Dispose() }
}
$first = Read-Frame
Start-Sleep -Milliseconds $WaitMs
$second = Read-Frame
$sha = [Security.Cryptography.SHA256]::Create()
try { $same = [Convert]::ToBase64String($sha.ComputeHash($first)) -eq [Convert]::ToBase64String($sha.ComputeHash($second)) }
finally { $sha.Dispose() }
if (-not $same) { @{same = $false; width = $width; height = $height} | ConvertTo-Json -Compress; return }
@{same = $true; width = $width; height = $height; image = [Convert]::ToBase64String($second)} | ConvertTo-Json -Compress
