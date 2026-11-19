# LLM fluency pass for check_corpus_text.py (step 2). Windows PowerShell; keep this file ASCII.
# Reads <work>\batch_*.txt (id|text per line) and writes <work>\llm_*.txt with the model's verdicts.
# Skips batches that already have an output file, so it can be re-run after a failure.
param(
  [string]$Work = "\\wsl.localhost\Ubuntu\home\$env:USERNAME\tts-train\data\siro-sweet-b-v1\textcheck",
  [string]$Model = "claude-haiku-5-5"
)
$ErrorActionPreference = "Stop"
$prompt = Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot "check_corpus_text.prompt.txt")
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
foreach ($batch in Get-ChildItem $Work -Filter "batch_*.txt" | Sort-Object Name) {
  $out = Join-Path $Work ($batch.Name -replace "^batch_", "llm_")
  if (Test-Path $out) { continue }
  $lines = Get-Content -Raw -Encoding UTF8 $batch.FullName
  $reply = & claude -p --model $Model ($prompt + "`n`n" + $lines)
  [IO.File]::WriteAllText($out, ($reply -join "`n"), [Text.UTF8Encoding]::new($false))
  Write-Output ("{0}: {1} lines" -f $batch.Name, @($reply).Count)
}
