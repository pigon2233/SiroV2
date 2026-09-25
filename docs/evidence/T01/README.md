# T01 驗收證據

日期：2026-09-23｜結果：PASS｜環境：T00 Ubuntu 開發主機、Python 3.14.4、uv 0.12.18

## 交付

- `pyproject.toml`、`uv.lock`、`.python-version`
- `src/siro` package：versioned settings、CLI、read-only doctor、structured redaction
- `scripts/check`：locked sync、format、lint、strict mypy、pytest、secret scan
- `.github/workflows/check.yml`：Python 3.12 CI baseline
- `.gitignore`、`.env.example`
- `tests/`：settings rejection/defaults、doctor disclosure、redaction

## 執行結果

```text
scripts/check
25 files already formatted
All checks passed!
Success: no issues found in 8 source files
6 passed in 0.12s
secret scan: no findings (exit 0)
```

```text
uv run siro doctor --json
exit 0
minimal: Python 3.14.4 and data directory available
optional unavailable: rustc, NVIDIA driver/runtime
```

`uv run siro config-schema` 產生有效 JSON，settings schema_version 固定為 1，未知欄位與未支援版本有測試拒絕。預設 profile 是 minimal、privacy 是 local_only、cloud/telemetry/proactivity 關閉、只綁 loopback。

## 限制

- CI workflow 已建立，尚未由遠端 GitHub Actions 執行；本機同一命令已通過。
- Doctor 目前判斷 Docker CLI 存在，不代表 daemon 有權限；T00 文件已記錄 daemon 權限缺口，T09 前處理。
- Redaction 是 SIRO structured diagnostics 的第一層，不代替後續資料分類與完整 logging policy。
- 沒有模型、帳號、外部服務、Rust 或 GPU 功能參與本次驗收。

## 2026-09-25 可重現性複驗

從目前來源建立 `/tmp/siro-clean-final-7Mn9Ip`，排除 `.git`、`.venv`、`target`、`.env.local` 與所有 cache，於該目錄由零建立環境並執行 `scripts/check`。結果：140 files formatted、ruff pass、strict mypy 94 source files pass、Python 105 passed/5 explicit opt-in skips、Rust 6 passed、Clippy/schema/secret scan pass。這證明目前來源不依賴工作區既有 virtualenv、build output 或 credential。
