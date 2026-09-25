# T00 驗收證據

日期：2026-09-23｜結果：PASS（環境盤點與規格落定）

## 執行與觀測

- `uname -a`, `/etc/os-release`, `lscpu`, `free -h`, `df -h .`：確認 Ubuntu 26.04、Ryzen 9 5900HX、14 GiB RAM 與可用儲存。
- `lspci -nnk`, `nvidia-smi`：RTX 3050 Mobile 硬體可見，但 NVIDIA driver/runtime 目前不可用。
- `wpctl status`：PipeWire、內建音訊與 Bluetooth headset 可見；未偵測 video source。
- Python/Node/Docker/Git version commands：Python 3.14.4、Node 24.21.0、Docker CLI 29.1.3、Git 2.53.0；Rust/uv 未安裝。
- `docker info`：目前使用者無 Docker socket 權限，記為 T09 前的外部環境缺口。
- `git ls-remote`：舊 SIRO、AIRI、Open-LLM-VTuber、Luna 公開來源可讀；本 repo remote 讀取要求憑證，沒有執行登入或寫入。
- PyPI index 與官方文件：核對 uv、Pydantic、pytest、Ruff、mypy 的可用版本與官方安裝方式。

## 產出

- `docs/ENVIRONMENT.md`
- `docs/DEPENDENCIES.md`
- `docs/DEPLOYMENT_POLICY.md`

## 驗收判定

另一個執行者可從文件辨識第一個可跑的 `minimal` profile、真實主機限制、尚缺硬體/帳號，以及每項解鎖任務。沒有安裝模型、改 driver、Docker group、系統權限或全域服務。開發機明確標示為第一基線而非最終部署承諾。

Mock vs real：硬體/OS/工具盤點為真實主機觀測；模型、Live2D、設備與第二節點沒有測試。
