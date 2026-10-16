# SIRO 2 依賴基線

核對日期：2026-09-23｜任務：T00。版本在 T01 的 lockfile 解析後以 `uv.lock` 為實際權威；本文件說明選擇範圍與用途。

## T01 Python 基線

| 依賴 | 初始範圍 | 用途與來源 |
|---|---|---|
| Python | `>=3.12,<3.15` | 3.12 是 PLAN 基線；本機 3.14.4 必須實測 |
| uv | `0.12.18` tool | 建立/鎖定/同步環境；[官方安裝與 project 文件](https://docs.astral.sh/uv/) |
| pydantic | `>=2.13,<3` | versioned settings/schema；[官方安裝文件](https://pydantic.dev/docs/validation/latest/get-started/install/) |
| pytest | `>=9.1,<10` | unit/contract tests；[官方文件](https://docs.pytest.org/en/stable/getting-started.html) |
| pytest-asyncio | `>=1.2,<2` | strict asyncio event bus tests；實際鎖定版本見 `uv.lock` |
| ruff | `>=0.16.8,<0.17` | formatting/lint；[官方安裝文件](https://docs.astral.sh/ruff/installation/) |
| mypy | `>=2.3,<3` | strict static typing；[官方文件](https://mypy.readthedocs.io/en/stable/getting_started.html) |
| detect-secrets | T01 lockfile 決定 | repository secret baseline/scan；實際規則與誤報需納入證據 |

CLI T01 使用 Python 標準庫 `argparse`，不先增加 CLI framework。Runtime dependency 只加入 Pydantic；測試、lint、typecheck 與 secret scan 放在 dev group。版本範圍避免任意 floating latest，實際 transitive versions 全部由 lockfile 固定。

## 後續依賴的引入 gate

| 元件 | 最早任務 | 加入前必須確認 |
|---|---|---|
| NATS/JetStream client/server | T09 | 官方 client 相容性、ack/redelivery tests、server 啟動方式 |
| HTTP/WebSocket framework | T10 | single-writer 模式、Origin/session control、graceful shutdown |
| AIRI/Live2D | T11 | license、可用外部接口、鎖定 commit、退出方案 |
| STT/TTS/VAD | T14/T15 | 模型 license、CPU/GPU/RAM、stream/cancel、語言品質 |
| Rust toolchain/RPC | T21 | 官方 rustup/toolchain、單一 protocol、generated client |
| MQTT/HA/ESP32 | T27/T28 | broker/API authentication、firmware board、真實 readback |
| Compute worker transport | T36 | mutual auth、privacy scope、lease/cancel semantics |

不得為未開始的任務預裝全部 SDK。每次新增 dependency 要更新 lockfile、license/來源紀錄、support matrix 和受影響測試。

## 主機工具狀態

- uv 0.12.18 已安裝於使用者目錄，專案依賴以 `uv.lock` 為權威。
- Rust 1.97.1 已由官方 rustup 1.29 系列安裝到使用者目錄，minimal profile 加 rustfmt/clippy；`rust-toolchain.toml` 與 `Cargo.lock` 鎖定 workspace，`scripts/check` 執行 fmt/test/clippy。
- Docker daemon 對目前使用者不可用：T09 前決定修權限或改用直接啟動 broker。
- Python 3.14 是新版本；若 dependency 無 wheel/不相容，uv 可安裝專案支援範圍內的 Python 3.13，不改系統 Python，並記錄 ADR。
- Ollama 0.34.3 已以官方 Linux 發行檔安裝到 `~/.local/ollama`，`~/.local/bin/ollama` 指向 CLI；user systemd service 綁定 `127.0.0.1:11434`。`qwen3:4b` Q4_K_M 模型位於使用者資料目錄，不進 Git。

## 授權與供應鏈

T01 只使用公開 Python registry 的鎖定套件。lockfile 與 dependency metadata 進 Git，cache、wheel、venv 不進 Git。第三方 repo 或模型不可只追 branch；PoC 後鎖 commit/version，記錄 license 與取得來源。更新在 T32 前不得直接替換 active production environment。

## 2026-10-16 native presentation runtime

本機使用已安裝GJS1.88.0、GTK3.24.52、WebKitGTK2.52.6（GI API4.1）。未新增Electron、Python GUI dependency或關閉sandbox；launcher缺GJS/連線/renderer時明確停止。其他主機需由官方OS套件安裝gjs與gir1.2-webkit2-4.1，不能把本機已安裝當成跨平台保證。官方API依據：[RGBA](https://webkitgtk.org/reference/webkit2gtk/2.40.5/method.WebView.set_background_color.html)、[input region](https://docs.gtk.org/gdk3/method.Window.input_shape_combine_region.html)、[WebKit sandbox](https://webkitgtk.org/reference/webkit2gtk/stable/method.WebContext.set_sandbox_enabled.html)。
