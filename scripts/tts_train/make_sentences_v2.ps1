# Step 2 of make_sentences_v2.py: ask Claude (haiku) to rewrite the broken sentences.
# Windows PowerShell; keep this file ASCII. Reads <work>\rewrite_input.txt, writes <work>\rewrite_output.txt.
param(
  [string]$Work = ("\\wsl.localhost\Ubuntu\home\$env:USERNAME\tts-train\data\sentences-v2"),
  [string]$Model = "claude-haiku-5-5"
)
$ErrorActionPreference = "Stop"
$prompt = Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot "rewrite_sentences.prompt.txt")
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$lines = Get-Content -Raw -Encoding UTF8 (Join-Path $Work "rewrite_input.txt")
$reply = & claude -p --model $Model ($prompt + "`n`n" + $lines)
[IO.File]::WriteAllText((Join-Path $Work "rewrite_output.txt"), ($reply -join "`n"), [Text.UTF8Encoding]::new($false))
Write-Output ("rewrite_output.txt: {0} lines" -f @($reply).Count)
