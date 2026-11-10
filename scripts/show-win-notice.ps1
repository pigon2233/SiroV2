param(
  [string]$Path,
  [ValidateSet("backend", "electron")]
  [string]$Kind = "backend"
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
$fallback = @{
  backend = "SIRO 後端無法啟動。請看 docs\WSL_SETUP.md。"
  electron = "請先在 desktop-win 資料夾執行 npm install，再重新開啟 SIRO。"
}[$Kind]
$detail = $fallback
if ($Path -and (Test-Path -LiteralPath $Path)) {
  $text = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
  if ($text -and $text.Trim()) { $detail = $text.Trim() }
}
[void][System.Windows.Forms.MessageBox]::Show($detail, "SIRO")
