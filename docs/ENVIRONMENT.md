# SIRO 2 開發環境盤點

盤點日期：2026-09-23｜任務：T00｜用途：第一個開發與驗證主機，不代表最終部署硬體。

## 已確認主機

| 項目 | 實際狀態 | 對實作的影響 |
|---|---|---|
| 作業系統 | Ubuntu 26.04 LTS、Linux 7.0.0、x86_64 | Linux 是第一個實測平台 |
| 桌面 | GNOME、Wayland | 桌面 UI 操作需走 portal/支援 Wayland 的 adapter，不能假設 X11 注入可用 |
| CPU | AMD Ryzen 9 5900HX，8 cores/16 threads | 足以開發 Core、測試與輕量服務 |
| 記憶體 | 14 GiB 可見；盤點時 4.5 GiB available、swap 4 GiB | 採 minimal/companion profile；重型模型不可常駐 |
| 儲存 | 根分割區 915 GiB，約 814 GiB available | 足以放 source、測試資料和後續選定的小型模型；模型不進 Git |
| GPU | NVIDIA RTX 3050 Laptop GPU，3.7 GiB VRAM；AMD Cezanne iGPU | Ollama 0.34.3 真實載入 `qwen3:4b` 時成功使用 CUDA，31/37 層 offload |
| NVIDIA runtime | T00 時 `nvidia-smi` 失敗；T07 時 Ollama CUDA 13.2 backend 實際推論成功 | 驅動可供 Ollama 使用；一般 CUDA tooling 仍應在 T33 重新盤點 |
| 音訊 | PipeWire 1.6.2；內建類比 input/output 與 Bluetooth headset 可見 | speaker AEC／20 次真人打斷通過；實體 headset 未測 |
| 相機 | PipeWire 未列 video source | T24/T26 前需確認相機硬體或使用合成畫面 |
| Python | CPython 3.14.4、pip 25.1.1、venv 可用 | 專案支援範圍先設 `>=3.12,<3.15`，本機以 3.14 驗證 |
| Node | 24.21.0、Corepack 0.36.0 | 後續 UI 可用；T01 不建立前端 |
| Rust | rustup stable 1.97.1、rustfmt、Clippy 已安裝並由 `rust-toolchain.toml` 鎖定 | T21–T23 Runtime gate 已使用 |
| Containers | Docker CLI 29.1.3；目前無 `/var/run/docker.sock` 權限 | T09 broker 測試前解決權限或採非 Docker 啟動方式 |
| Git | 2.53.0；branch `main`；初始 commit `c060f1b` | 規劃文件與實作仍是未提交變更，需保留 |

## Repo 與外部來源

- 本 repo remote 設為 `https://github.com/pigon2233/SiroV2.git`，本次未驗證寫入權限。
- 舊 SIRO 公開 repository 可讀，2026-09-23 的 HEAD 為 `b0e95e61c7fbade88253da3ab8b4801e14880e62`。只在對應任務稽核可移植能力，不整體搬入。
- AIRI、Open-LLM-VTuber、Luna 的公開 HEAD 可讀；未稽核 source、license compatibility 或穩定外部 API，T11 才鎖定 commit 做 PoC。

## 第一個可跑 profile

`minimal`：本地 Core、CLI、SQLite、mock model、合成資料。它不需要 GPU、雲端 key、Live2D、Rust、broker 或硬體設備，適用 T01–T08 的早期工作。

`companion`：後續整合 broker、UI/Live2D 與音訊。由於目前 RAM 只有 14 GiB，預設不和大型本地 LLM 同時常駐。

`local-ai`：Ollama 0.34.3、`qwen3:4b` Q4_K_M 與 loopback chat API 已通過 T07 L2 smoke test。服務以 user systemd unit 運行，模型不進 Git；長時間負載與資源預算仍在 T33 驗證。

`distributed`：目前 BLOCKED-EXTERNAL。尚未提供第二個可信節點。

## 未確認條件與解鎖任務

| 條件 | 現況 | 最遲處理 |
|---|---|---|
| 最終是否以此主機部署 | 未確認；只作第一開發基線 | T33/T34 |
| NVIDIA driver 與 VRAM | driver 不可用，VRAM 未量測 | T33 |
| 雲端模型帳號、資料範圍、預算 | 未提供；預設全部停用 | T07/T38 |
| Live2D 模型與聲音授權 | 未提供 | T12/T15 |
| AEC 與實際 mic/speaker 品質 | speaker 修正版 20 次成功、0 誤觸發；headset 未測 | T16 headset 待驗 |
| 相機 | 未偵測 | T24/T26 |
| ESP32/Home Assistant | 未提供 | T27–T29 |
| 第二台主機 | 未提供 | T39 |
| Windows 支援主機 | 未提供 | T24/T25 |

以上缺口不阻擋 minimal profile。真實整合必須清楚標示 L1/L2/L3，不用 mock 取代真機完成狀態。
