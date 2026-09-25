# SIRO 2 — 開發計劃與 Sol 執行入口

本儲存庫是**規劃完成、T00–T11、T13–T15、T17–T23 已完成自動驗證，T12/T16 等待外部驗收**的 SIRO 2。文件更新：2026-09-25；目前具備持久 Core、真正串流的 Groq/Ollama adapter、JetStream、認證 gateway、版本化音訊協定、Groq Whisper STT、TTS/播放/打斷管線、主動性決策、受限 Rust Runtime 與 Linux skill sandbox。真 Live2D、Orpheus 條款後的真 TTS、AEC 與真人打斷仍待驗。

目標：建立可長期陪伴、保留人格與記憶、使用電腦與外部設備、擴充技能及受控迭代的數位角色。開發流程以使用者在 Codex 選用 Sol（GPT-5.6 Sol）逐項實作為設計前提；SIRO 執行時使用哪個模型則是獨立設定。

## 文件入口

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

本機 gateway 與明示為 placeholder 的 body shell：

```bash
uv run siro-gateway
```

開啟 `http://127.0.0.1:8000/` 查看控制頁，或 `http://127.0.0.1:8000/body` 查看 renderer shell。下載的 Cubism Core、角色資產與授權接受紀錄不得提交 Git；格式見 `config/body-assets/README.md`。

## 開發環境

T01 起使用 Python 3.12–3.14 與 uv。安裝固定工具版本後執行：

```bash
uv sync --locked --all-groups
scripts/check
uv run siro doctor
uv run siro config-schema
```

`doctor` 是唯讀診斷；minimal profile 不需要模型、API key、GPU 或外部設備。當前主機與部署限制見 [環境盤點](docs/ENVIRONMENT.md) 和 [初始部署政策](docs/DEPLOYMENT_POLICY.md)。
