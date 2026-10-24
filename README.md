# SIRO 2 — 開發計劃與 Sol 執行入口

本儲存庫是**規劃完成、T00–T33 已完成各任務所標示層級驗證**的 SIRO 2；T34 與 T36–T38 只有部分 L1 實作，不能視為整張任務卡完成。文件更新：2026-09-26；目前具備持久 Core、真正串流的 Groq/Ollama adapter、JetStream、認證 gateway、真 Live2D renderer、版本化音訊協定、Groq Whisper/Orpheus、播放/打斷管線、主動性決策、受限 Rust Runtime、Linux skill sandbox、scoped Chrome driver、allowlisted user-systemd、device registry、authenticated MQTT simulator、Home Assistant REST/WebSocket adapter、受 policy/readback 保護的房間閉環，以及 review-only procedural-memory candidates。未驗平台與能力均明示 unsupported 或 simulator-only；ESP32 與真實 Home Assistant instance 尚未驗證。

目標：建立可長期陪伴、保留人格與記憶、使用電腦與外部設備、擴充技能及受控迭代的數位角色。開發流程以使用者在 Codex 選用 Sol（GPT-5.6 Sol）逐項實作為設計前提；SIRO 執行時使用哪個模型則是獨立設定。

## 文件入口

Windows／E 槽 WSL 的本機啟動方式見 [WSL 操作說明](docs/WSL_SETUP.md)。

| 文件 | 用途 |
|---|---|
| [完整作業流程計劃書](docs/PLAN.md) | 願景、架構決策、模組責任、階段順序、效能與完成定義 |
| [介面與資料契約](docs/CONTRACTS.md) | 事件、通訊、取消、資料庫、技能、算力節點規格 |
| [逐項任務與依賴](docs/TASKS.md) | 可以直接交给 Sol 的任務卡、產出與驗收 |
| [驗收與故障演練](docs/ACCEPTANCE.md) | 測試場景、量測方式、發布門檻 |
| [Sol 操作手冊](docs/SOL_RUNBOOK.md) | 啟動、續作、除錯、變更與交接提示詞 |
| [需求與研究來源](docs/SOURCES.md) | 原對話需求追蹤、參考專案、論文與應用界線 |
| [使用體驗與設定](docs/EXPERIENCE.md) | 首次設定、日常流程、畫面、錯誤與使用者控制 |
| [安全與隱私](docs/SECURITY_PRIVACY.md) | 信任區、威脅模型、資料生命週期與 kill switches |
| [目前進度](docs/STATUS.md) | 已完成內容、待辦與下次起點 |
| [本機操作手冊](docs/OPERATIONS.md) | locked 安裝、user service、診斷、啟停、log retention、備份還原 |
| [決策紀錄](docs/DECISIONS.md) | 暫定技術基線與變更歷史 |
| [規劃完成度稽核](docs/PLANNING_AUDIT.md) | 逐項核對規劃需求與證據，區分規劃和產品狀態 |

## 開始實作

在此專案選用 Sol，貼上：

```text
請先讀 AGENTS.md、docs/STATUS.md、docs/SOL_RUNBOOK.md，再讀 docs/TASKS.md 中下一個依賴已滿足的任務，以及該任務引用的契約和驗收條件。從 T00 開始實作，每次完成一張任務卡並留下測試證據；不要只更新文件便宣告功能完成。延續現有規劃，完成後更新 STATUS.md，記錄下一個明確動作。需要外部帳號或硬體時，先完成不依賴它們的部分並標示待實測。
```

所有尚未完成的開發指令與目錄若標為「目標」，代表待後續任務建立。計劃旨在降低實作歧義，無法保證模型在所有環境一次成功。真實硬體、帳號授權、角色資產與最終使用體驗仍需實際驗收。

不需 API key 即可啟動持久化文字 demo：

```bash
uv run siro demo --data .siro-demo
```

輸入 `/quit` 結束。可用 `--once '訊息'` 做單次 smoke test；只有 owner 明示使用 `--edit-persona` 時，`--name` 與 `--persona` 才會修改既有身份核心。

本機 Ollama 服務已安裝為 user service，可用以下命令檢查並執行真實 adapter 測試：

```bash
systemctl --user status ollama
SIRO_OLLAMA_MODEL=qwen3:4b uv run pytest -m real_provider tests/real/test_model_providers.py -vv
```

日常使用請啟動獨立 SIRO 桌寵（必要時啟動正式後端，讀取本機 `.env.local` 模型設定）：

```bash
scripts/start-companion
```

桌面角色提供「聊聊／移動／控制台／暫藏／退出」，控制台也可從 [SIRO](http://127.0.0.1:8000/?view=control) 開啟。若只需要後端，執行 `scripts/start-runtime-product`。頁面應顯示「雲端對話」或「本機對話」，以及「Live2D 已就緒」；缺少模型或角色時入口會明確停止。詳細設定與功能限制見 [產品操作說明](docs/runtime-evolution/PRODUCT_QUICKSTART.md)。

### Windows 桌面開啟與退出（VRM 角色）

| 動作 | 做法 |
|---|---|
| 開啟 | 雙擊桌面 `SIRO-VRM-Start`（即根目錄 `Start-SIRO-VRM.cmd`），載入已登記的 `config/body-assets/siro-vrm/model.vrm` |
| 只關視窗 | 關閉桌寵視窗；後端與資料保留，下次開啟會接回同一服務 |
| 完全退出 | 雙擊桌面 `SIRO-Stop`（`Stop-SIRO.cmd`），停止後端與桌寵並確認 port 8000 已無回應 |
| 預覽候選模型 | 先完全退出，再執行 `Start-SIRO-VRM-Candidate.cmd`；後端仍在執行時會拒絕，避免誤載正式模型。候選 manifest 在 Git 忽略的 `.siro-data/vroid/candidate-registered/` |

桌面捷徑與 WSL 啟動腳本（`~/.local/bin/siro-companion-vrm`、`siro-companion-vrm-candidate`、`siro-stop`）在 Git 外，細節見 [WSL 操作說明](docs/WSL_SETUP.md)。

需要 PID 管理可用 `scripts/start .siro-data/companion-service.pid`，停止用 `scripts/stop .siro-data/companion-service.pid`。這兩種正式入口使用同一個 launcher。

開發用離線示範另用 `scripts/start /tmp/siro-demo.pid --demo` 或 `uv run siro-gateway`。低階 gateway 不讀 `.env.local` 或自動選角色；沒有明確模型／renderer 環境設定時，會使用固定示範回覆與替身，不是日常可用的 SIRO。下載的 Cubism Core、角色資產與授權接受紀錄不得提交 Git；準備方式見 `config/body-assets/README.md`。

## 開發環境

T01 起使用 Python 3.12–3.14 與 uv。安裝固定工具版本後執行：

```bash
uv sync --locked --all-groups
scripts/check
uv run siro doctor
uv run siro config-schema
```

建立本機 user service 與操作流程見 [本機操作手冊](docs/OPERATIONS.md)。預設安裝不會自行啟動；檢視
unit 後以 `scripts/install --enable` 啟用。

`doctor` 是唯讀診斷；minimal profile 不需要模型、API key、GPU 或外部設備。當前主機與部署限制見 [環境盤點](docs/ENVIRONMENT.md) 和 [初始部署政策](docs/DEPLOYMENT_POLICY.md)。
