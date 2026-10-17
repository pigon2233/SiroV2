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
- Ollama 0.34.3 已以官方 Linux 發行檔安裝到 `~/.local/ollama`，`~/.local/bin/ollama` 指向 CLI；user systemd service 綁定 `127.0.0.1:11434`。2026-10-17 E 槽 WSL 選用 `qwen3:4b-instruct` Q4_K_M，模型位於使用者資料目錄，不進 Git。

## 授權與供應鏈

T01 只使用公開 Python registry 的鎖定套件。lockfile 與 dependency metadata 進 Git，cache、wheel、venv 不進 Git。第三方 repo 或模型不可只追 branch；PoC 後鎖 commit/version，記錄 license 與取得來源。更新在 T32 前不得直接替換 active production environment。

## 2026-10-16 native presentation runtime

本機使用已安裝GJS1.88.0、GTK3.24.52、WebKitGTK2.52.6（GI API4.1）。未新增Electron、Python GUI dependency或關閉sandbox；launcher缺GJS/連線/renderer時明確停止。其他主機需由官方OS套件安裝gjs與gir1.2-webkit2-4.1，不能把本機已安裝當成跨平台保證。官方API依據：[RGBA](https://webkitgtk.org/reference/webkit2gtk/2.40.5/method.WebView.set_background_color.html)、[input region](https://docs.gtk.org/gdk3/method.Window.input_shape_combine_region.html)、[WebKit sandbox](https://webkitgtk.org/reference/webkit2gtk/stable/method.WebContext.set_sandbox_enabled.html)。

## 2026-10-17 E 槽 WSL 設定

2026-10-18 T10 注音修復：E 槽 Ubuntu 26.04.1 安裝官方 Ubuntu 套件 `ibus=1.5.34~rc2-1`、`ibus-chewing=2.1.7-1`（含 `libchewing3=0.11.0-1`）、`x11-xkb-utils=7.7+9build1`。後者提供 IBus 切換鍵盤配置時需要的 `setxkbmap`；缺少時實際入口無法選用 Chewing。來源：[Ubuntu ibus](https://packages.ubuntu.com/source/resolute/ibus)、[Ubuntu ibus-chewing](https://packages.ubuntu.com/source/resolute/ibus-chewing)、[Ubuntu x11-xkb-utils](https://packages.ubuntu.com/resolute/x11-xkb-utils)；安裝後核對本機 `/usr/share/doc/ibus/copyright`（LGPL-2.1+）、`/usr/share/doc/ibus-chewing/copyright`（GPL-2+）及 `/usr/share/doc/x11-xkb-utils/copyright`（`setxkbmap` 為 X/MIT 型授權）。這是 WSL 系統輸入法，不是 Python 專案依賴，故 `uv.lock` 不變。桌寵啟動時只在 WSL 選用 Chewing 並向 GTK 傳遞 IBus 環境。

D66使用者選B後新增官方 [Qwen0.6B Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base)（Apache-2.0），revision `5d83992436eae1d760afd27aff78a71d676296fc`，主權重及同一tokenizer的LFS／Git blob均核對。沿D65獨立SDK環境，以本機data下受核對的venv alias啟動，沒有另改專案lockfile。固定B合成reference／對應台詞及voice_id由顯式profile載入；worker offline／local-files-only，實跑GPU新句、cache、取消／回收與原生播放成功。仍未建立首音SLO或正式release認證。

D65 聲音試聽為獨立環境，不改專案 lockfile：官方 [Qwen VoiceDesign](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign)（Apache-2.0），revision `5ecdb67327fd37bb2e042aab12ff7391903235d3`，所有 LFS／Git blob 核對；[官方 SDK](https://github.com/QwenLM/Qwen3-TTS) qwen-tts0.1.1、Torch／torchaudio2.8.0、Transformers4.57.3／accelerate1.12.0。SDK及CUDA依賴在 E 槽 WSL `voice-design-py312`，完整 freeze 見 D65 RESULTS。CUDA index 的 NVIDIA cuDNN wheel 首次下載 timeout，改相同版本官方 PyPI 發布成功，實際 RTX3050 GPU 合成通過。SDPA 模式，未安裝 FlashAttention；SoX CLI 未補，SDK警告不妨礙本次 VoiceDesign 合成，不冒稱 voice-clone 的 SoX 路徑已驗。此環境、模型與試聽音檔均沒有取代正式 provider。

D64 音訊修復補充：本機 STT 使用 [faster-whisper 1.2.1](https://github.com/SYSTRAN/faster-whisper)（MIT），CPU int8、固定 `Systran/faster-whisper-small` revision `536b0662742c02347bc0e980a01041f333bce120`（MIT）。模型／來源摘要外置 E 槽 Ubuntu manifest，顯式 `SIRO_WHISPER_MODEL_DIR` 才啟用；推論 local-files-only，不外送原音。`uv.lock` 現為103 packages。首次真合成辨識重現 PyAV19 移除 `metadata_errors` 的上游不相容，依[官方變更](https://github.com/PyAV-Org/PyAV/releases)及[faster-whisper 1589](https://github.com/SYSTRAN/faster-whisper/issues/1589)，明確限制 `av>=16.1,<17`、鎖16.1.0後通過；沒有改第三方SDK source或假裝未知API可用。

WebKit MediaRecorder 真失敗缺 `uritranscodebin`，補 Ubuntu 官方 `gstreamer1.0-plugins-bad`（此版連帶extra）後 WebM Opus錄製／解碼通過；default MP4仍在該環境解碼失敗，產品明確優先 WebM Opus。`pulseaudio-utils`／`gstreamer1.0-tools`只供診斷，沒有另啟Pulse/音訊server或關閉sandbox。

Ubuntu 26.04.1 的執行副本選 Python 3.12.14，因鎖定的 Kokoro／Misaki 不支援 3.14；不更動系統 Python，D64 的 lock 變更如上。uv 0.12.18、Rust 1.97.1、Node 22.22.1 與上述 GJS／GTK／WebKit 配合既有程式。中文字型使用 Ubuntu 官方 `fonts-noto-cjk`，emoji 使用 `fonts-noto-color-emoji`。

[Ollama 官方 0.34.3](https://github.com/ollama/ollama/releases/tag/v0.34.3) 採 MIT；[Qwen3 4B instruct](https://ollama.com/library/qwen3:4b-instruct) 採 Apache-2.0，完整本機 digest 記於本輪驗收。Ollama 使用 loopback／`OLLAMA_NO_CLOUD=1`、4096 context，沒有新增雲端 key。此 profile 明確選 byte-budget mode，並未建立經認證的 native-token profile。

使用者已在本聊天同意 [Live2D 官方 SDK／素材條款](https://www.live2d.com/en/sdk/download/web/)。Cubism Web 5-r.5 archive、Core、Haru 與接受紀錄均外置；原 archive pin 保持。SDK build-only npm lock 在外置 SDK 內做相容修補，`npm audit` 最終 0，重新 build；不是改專案 Python／Cargo lock 或正式 release。

既有 `kokoro-onnx==0.6.1`／`misaki==0.9.4`／`onnxruntime==1.30.0` 不變。備妥官方 Kokoro v1.0 q4 ONNX 與 voices；來源、固定 revision、別名、SHA 與 Apache-2.0／SDK MIT 記在本機 manifest 及驗收報告。這是既有本機備用路由，原 Qwen reference 聲線與真人聽驗尚未恢復。
