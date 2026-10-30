# Read-only one-run diagnostic: no screenshots, hashes, text, or input events leave memory.
param([int]$Samples = 20, [int]$IntervalMs = 500, [switch]$SelfTest)
$ErrorActionPreference = 'Stop'
if ($Samples -lt 2 -or $Samples -gt 60 -or $IntervalMs -lt 200 -or $IntervalMs -gt 2000) { throw 'invalid_bounds' }
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class SiroFrameStudy {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
  public static byte[] Pixels(IntPtr scan0, int stride, int width, int height) {
    if (stride != width * 4) throw new Exception("unsupported_stride");
    byte[] bytes = new byte[stride * height]; Marshal.Copy(scan0, bytes, 0, bytes.Length);
    return bytes;
  }
  public static int Changed(byte[] first, byte[] second, int threshold) {
    if (first.Length != second.Length) throw new Exception("different_size");
    int changed = 0;
    for (int i = 0; i < first.Length; i += 4) {
      if (Math.Abs((int)first[i] - second[i]) > threshold ||
          Math.Abs((int)first[i+1] - second[i+1]) > threshold ||
          Math.Abs((int)first[i+2] - second[i+2]) > threshold) changed++;
    }
    return changed;
  }
  public static int NonBlack(byte[] pixels) {
    int count = 0;
    for (int i = 0; i < pixels.Length; i += 4) if (pixels[i] + pixels[i+1] + pixels[i+2] > 15) count++;
    return count;
  }
}
'@
if ($SelfTest) {
  [byte[]]$a = @(0,0,0,255, 20,20,20,255)
  [byte[]]$b = @(1,0,0,255, 20,20,20,255)
  if ([SiroFrameStudy]::Changed($a,$a,0) -ne 0 -or
      [SiroFrameStudy]::Changed($a,$b,0) -ne 1 -or
      [SiroFrameStudy]::Changed($a,$b,8) -ne 0 -or
      [SiroFrameStudy]::NonBlack($a) -ne 1) { throw 'pixel_comparator_failed' }
  Write-Output 'pixel_comparator_selftest=passed'
  return
}
$handle = [SiroFrameStudy]::GetForegroundWindow(); [uint32]$pidValue = 0
[void][SiroFrameStudy]::GetWindowThreadProcessId($handle, [ref]$pidValue)
if ($handle -eq [IntPtr]::Zero -or $pidValue -eq 0) { throw 'no_foreground_window' }
if ([System.Diagnostics.Process]::GetProcessById([int]$pidValue).ProcessName.ToLowerInvariant() -ne 'undertale') { throw 'undertale_not_foreground' }
$rect = New-Object SiroFrameStudy+RECT
if (-not [SiroFrameStudy]::GetWindowRect($handle, [ref]$rect)) { throw 'window_rect_unavailable' }
$width = $rect.Right - $rect.Left; $height = $rect.Bottom - $rect.Top
if ($width -lt 64 -or $height -lt 64 -or $width -gt 4096 -or $height -gt 4096) { throw 'window_size_invalid' }
$outWidth = [Math]::Min(1280, $width); $outHeight = [int][Math]::Round($height * $outWidth / $width)
$previous = $null; $identical = 0; $changes = @(); $captureMs = @(); $blank = 0
$unique = [System.Collections.Generic.HashSet[string]]::new()
$sha = [System.Security.Cryptography.SHA256]::Create()
$overall = [System.Diagnostics.Stopwatch]::StartNew()
try {
  for ($i = 0; $i -lt $Samples; $i++) {
    [uint32]$beforePid = 0; $before = [SiroFrameStudy]::GetForegroundWindow()
    [void][SiroFrameStudy]::GetWindowThreadProcessId($before, [ref]$beforePid)
    $currentRect = New-Object SiroFrameStudy+RECT
    if ($before -ne $handle -or $beforePid -ne $pidValue -or -not [SiroFrameStudy]::GetWindowRect($before, [ref]$currentRect) -or
        $currentRect.Left -ne $rect.Left -or $currentRect.Top -ne $rect.Top -or $currentRect.Right -ne $rect.Right -or $currentRect.Bottom -ne $rect.Bottom) { throw 'foreground_changed' }
    $bitmap = [System.Drawing.Bitmap]::new($width, $height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap); $dc = $graphics.GetHdc()
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    try { $ok = [SiroFrameStudy]::PrintWindow($handle, $dc, 2) }
    finally { $graphics.ReleaseHdc($dc); $graphics.Dispose(); $watch.Stop() }
    try {
      [uint32]$afterPid = 0; $after = [SiroFrameStudy]::GetForegroundWindow()
      [void][SiroFrameStudy]::GetWindowThreadProcessId($after, [ref]$afterPid)
      if (-not $ok -or $after -ne $handle -or $afterPid -ne $pidValue) { throw 'capture_or_foreground_changed' }
      $scaled = [System.Drawing.Bitmap]::new($outWidth, $outHeight, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
      $resize = [System.Drawing.Graphics]::FromImage($scaled)
      try {
        $resize.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBilinear
        $resize.DrawImage($bitmap, 0, 0, $outWidth, $outHeight)
      } finally { $resize.Dispose() }
      try {
        $lockRect = [System.Drawing.Rectangle]::new(0, 0, $outWidth, $outHeight)
        $bits = $scaled.LockBits($lockRect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        try { $pixels = [SiroFrameStudy]::Pixels($bits.Scan0, $bits.Stride, $outWidth, $outHeight) }
        finally { $scaled.UnlockBits($bits) }
      } finally { $scaled.Dispose() }
      if ([SiroFrameStudy]::NonBlack($pixels) -eq 0) { $blank++ }
      [void]$unique.Add([Convert]::ToBase64String($sha.ComputeHash($pixels)))
      if ($null -ne $previous) {
        $changed = [SiroFrameStudy]::Changed($previous, $pixels, 0)
        if ($changed -eq 0) { $identical++ }
        $changes += [Math]::Round($changed / ($outWidth * $outHeight), 6)
      }
      $previous = $pixels; $captureMs += [Math]::Round($watch.Elapsed.TotalMilliseconds, 3)
    } finally { $bitmap.Dispose() }
    if ($i -lt $Samples - 1) { Start-Sleep -Milliseconds $IntervalMs }
  }
} finally { $overall.Stop(); $sha.Dispose() }
if ($blank -gt 0) { throw 'blank_or_unsupported_capture' }
$ordered = @($changes | Sort-Object)
@{ status = 'complete'; samples = $Samples; requested_interval_ms = $IntervalMs;
  elapsed_seconds = [Math]::Round($overall.Elapsed.TotalSeconds, 3); unique_frames = $unique.Count;
  identical_adjacent_pairs = $identical; median_changed_fraction = $ordered[[int][Math]::Floor($ordered.Count / 2)];
  max_changed_fraction = $ordered[-1]; capture_ms_mean = [Math]::Round(($captureMs | Measure-Object -Average).Average, 3);
  capture_ms_max = ($captureMs | Measure-Object -Maximum).Maximum; blank_frames = $blank;
  caveat = 'PrintWindow is not Electron capture and may return stale frames; no gameplay input was sent.' } | ConvertTo-Json -Compress
