# SIRO 2 目前進度與接續點

更新：2026-09-25

## 當前狀態

**T00–T23 稽核修復已完成所有可自動驗證項目。** T12 等待 Live2D SDK/模型授權與真畫面；T15 已完成 Groq 真 TTS；T16 等待 AEC 與至少 20 次真人打斷。原 repo 初始 commit `c060f1b`，所有新工作仍未提交。

已完成：分享對話解析與需求追蹤、架構與介面規格、使用體驗、威脅/隱私與資料生命週期、41 張實作任務卡、3 張研究卡、24 個驗收情境、Sol 啟動/續作/除錯手冊、初始 ADR，以及逐項規劃完成度稽核。

尚未完成：T12/T15/T16 的外部驗收、T24–T40、完整產品驗收與後續真機測試。AIRI 已完成鎖定 source/license/API 稽核。

## 下一個具體動作

完成三個外部驗收節點後封存 T00–T23 證據，再開始 T24。若外部條件尚未就緒，保持相應任務為 BLOCKED-EXTERNAL，不把 placeholder 或自動測試冒充真人驗收。

## 外部條件清單

| 項目 | 目前狀態 | 最遲影響任務 |
|---|---|---|
| 最終部署 OS/CPU/RAM/GPU | 第一開發基線已盤點；最終部署仍未確認，NVIDIA driver 不可用 | T33 |
| 模型 backend 認證與費用上限 | Groq 免費 API 與本機 Ollama 已完成 L2；正式費用上限未設定 | 發布前 |
| Live2D/聲音資產與授權 | Live2D 未接受/取得；Groq Orpheus 條款已接受並通過真實閉環 | T12 |
| 麥克風/喇叭測試環境 | PipeWire 裝置可見，AEC/品質未測 | T16 |
| ESP32/HA instance 與設備 | 未確認 | T27–T29 |
| 第二台算力節點 | 未確認 | T39 |
| Windows 支援範圍和實測主機 | 未確認 | T24/T25 |

## 任務狀態

T00–T11、T13–T15（除真 TTS）、T17–T23 已完成相應 L1/L2；T12 與 T16 部分完成且等待外部驗收；R01–R03 為 RESEARCH-PENDING。不能從文件數推算產品完成百分比。

| 範圍 | 狀態 | 證據 |
|---|---|---|
| 規劃文件包 | COMPLETE | 本 repo 的 13 份 Markdown 文件與 `docs/evidence/planning-check.json`；逐項證據見 PLANNING_AUDIT |
| T00 | DONE | `docs/ENVIRONMENT.md`、`DEPENDENCIES.md`、`DEPLOYMENT_POLICY.md`、`evidence/T00/README.md` |
| T01 | DONE | `pyproject.toml`、`uv.lock`、`src/siro`、`scripts/check`、CI、`evidence/T01/README.md` |
| T02 | DONE | `src/siro/contracts`、`schemas/events`、`tests/contract`、`evidence/T02/README.md` |
| T03 | DONE | `src/siro/ports/events.py`、`src/siro/events/local.py`、24 tests、`evidence/T03/README.md` |
| T04 | DONE | `src/siro/persistence`、migrations、SQLite integration tests、`evidence/T04/README.md` |
| T05 | DONE | identity/world、35-test gate、`evidence/T05/README.md` |
| T06 | DONE | conversation/mock/CLI、A01/A02 L1、100-race、`evidence/T06/README.md` |
| T07 | DONE | 兩 adapter/L1、Groq L2、Ollama L2、A03 backend swap，見 `evidence/T07/README.md` |
| T08 | DONE (L1) | persistent memory/persona/demo、A03 L1、`evidence/T08/README.md` |
| T09 | DONE | JetStream/outbox/redelivery/quarantine/replay、A04 L2、`evidence/T09/README.md` |
| T10 | DONE | loopback gateway/control UI/single writer、A05/A06 L2、`evidence/T10/README.md` |
| T11 | DONE (research + L1) | AIRI commit/license/API 阻礙、body contract、最小 Web adapter，見 `ADR-embodiment.md` 與 `evidence/T11/README.md` |
| T12 | IN-PROGRESS / ASSET BLOCKED | body WS、單 owner/writer、有界 queue、offline/reconnect、A07 L1、asset manifest、browser shell 已完成；缺合法 SDK Core/模型與真 Live2D A07，見 `evidence/T12/README.md` |
| T13 | DONE (L1 + local L2) | binary header、Python/Node golden、mic/output WS、single owner、ring buffer，見 `evidence/T13/README.md` |
| T14 | DONE (L1 + Groq L2) | VAD、partial/final、endpoint、Groq Whisper 真實 fixture，見 `evidence/T14/README.md` |
| T15 | DONE (L1 + Groq L2) | 分句、stream transport、ACK/口型/文字降級與 Orpheus→Whisper 真實閉環，見 `evidence/T15/README.md` |
| T16 | IN-PROGRESS / FIELD BLOCKED | barge-in、generation fence、100 races、故障矩陣完成；缺 AEC/20 次真人打斷，見 `evidence/T16/README.md` |
| T17 | DONE (L1 + SQLite integration) | 五類 memory、FTS、版本/來源/scope、A10/A11、管理 API，見 `evidence/T17/README.md` |
| T18 | DONE (L1 + SQLite integration) | bounded/resumable scheduler、A12、trait clamps、relationship revisions，見 `evidence/T18/README.md` |
| T19 | DONE (L1 + SQLite integration) | Attention/Drives/Workspace、hard gates、Goal lifecycle/budgets、noise replay，見 `evidence/T19/README.md` |
| T20 | DONE (L1) / L3 PENDING | 預設關閉、quiet/busy/speaking/cooldown/day limit、7-day replay，見 `evidence/T20/README.md` |
| T21 | DONE (L1 + L2) | Runtime clock、SQLite grant/revoke/audit/action、跨程序 A14、ASK workflow，見 `evidence/T21/README.md` |
| T22 | DONE (Linux L2) | Bubblewrap network/filesystem/env isolation、resource limits、Core heartbeat，見 `evidence/T22/README.md` |
| T23 | DONE (Linux L2) | Rust Runtime grant → filesystem/process driver、持久 action ledger、A16，見 `evidence/T23/README.md` |
| T24–T25 | TODO | 無 |
| T26–T29 | TODO | 無 |
| T30–T35 | TODO | 無 |
| T36–T40 | TODO | 無 |
| R01–R03 | RESEARCH-PENDING | 無實驗證據 |

## 2026-09-23／T00 交接

- 完成與變更：盤點 OS/CPU/RAM/GPU/audio/tooling/repo，定義 dependency 與保守 deployment policy。
- 驗收：真實 shell 查詢與官方 dependency 文件；證據見 `docs/evidence/T00/README.md`。
- 工作區：`main`，原有規劃與本次 T00 均未提交；無 secret。
- 真實／mock：環境盤點真實；模型、身體、設備、第二節點尚未驗證。
- 下一步：T01 建立 `pyproject.toml`、`uv.lock`、`src/siro/cli`、`scripts/check`、CI 與測試。

## 2026-09-23／T01 交接

- 完成與變更：Python package、settings schema v1、CLI doctor/config schema、locked dependencies、統一 checks、CI、redaction 和測試。
- 驗收：`scripts/check` 通過 format/lint/mypy/6 tests/secret scan；doctor exit 0；證據見 `docs/evidence/T01/README.md`。
- 工作區：`main`，所有規劃/T00/T01 變更仍未提交；`.venv` 已 gitignore，無 secret。
- 真實／mock：CLI 與環境診斷為真實本機；沒有模型或外部整合。
- 下一步：T02 建立 `src/siro/contracts`、`schemas/events` 和 contract/boundary tests。

## 2026-09-23／T02 交接

- 完成與變更：event envelope、9 個首批 typed events、有界 JSON validation、causal session guard、JSON Schema export/stale check、Core import boundary。
- 驗收：`scripts/check` 通過 format/lint/mypy/17 tests/schema/secret scan；證據見 `docs/evidence/T02/README.md`。
- 工作區：`main`，所有變更仍未提交；無 secret。
- 真實／mock：純 deterministic contract tests；沒有 broker 或跨程序 transport。
- 下一步：T03 實作 `src/siro/ports/events` 與 bounded local bus，驗證慢 consumer、expiry、priority 和 shutdown cleanup。

## 2026-09-23／T03 交接

- 完成與變更：EventBus/Clock ports、有界 priority buffers、每訂閱者 worker、TTL/dedup、滿載結果、例外隔離及 shutdown cleanup。
- 驗收：`scripts/check` 通過 format/lint/mypy/24 tests/schema/secret scan；10,000-event、slow consumer、priority/fairness、expiry/duplicate、worker cleanup 均通過。
- 工作區：`main`，所有變更仍未提交；無 secret。
- 真實／mock：asyncio 本機 bus 為真實程式，測試資料合成；沒有 broker/durability。
- 下一步：T04 建立 SQLite WAL schema/migrations、transaction、outbox/inbox 與一致 backup/restore。

## 2026-09-23／T04–T08 交接

- 完成與變更：SQLite WAL/migrations/outbox/inbox/backup、identity/world、conversation 狀態機與 durable messages、OpenAI-compatible/Ollama/failover adapters、source-backed memory、persona prompt 與 offline CLI demo。
- 驗收：`scripts/check` 通過 format/lint/mypy/47 tests/schema/secret scan，2 個真 provider tests 因外部條件明確 skip；A01 單 trace/有序 delta/唯一 terminal、A02 100 次 race、三次 DB 重啟記憶、adapter 切換 identity、unknown 無假來源均通過。證據見 `docs/evidence/T04` 至 `T08`。
- 工作區：`main`，所有變更仍未提交；無 secret。
- 真實／mock：T05、SQLite 與 CLI 為真實本機程式；A01/A02 為 L1 deterministic。Groq `openai/gpt-oss-20b`、Ollama 0.34.3 + `qwen3:4b` 與 A03 backend swap 已通過 L2。
- 新決策與缺陷：雲端外送必須明示 `cloud_allowed`；failover 只准在尚未顯示文字前發生；Groq SSE 與 Ollama NDJSON 已改為真正 streaming，取消會關閉 response。
- 下一步：有 credential/model 時補 T07 L2；否則進 T09 broker/outbox replay。

## 2026-09-24／T09 交接

- 完成與變更：NATS JetStream adapter、SQLite outbox dispatcher、bounded retry/quarantine、durable inbox dedup、read-only replay runtime、broker config 與 CI broker install。
- 驗收：`scripts/check` 通過 50 tests（另 3 個明示 opt-in provider tests skip）；真實 JetStream crash-before-ack redelivery 保持單次副作用；broker outage 與 replay safety 通過。
- 工作區：`main`，所有變更仍未提交；Groq key 只在 ignored mode-600 `.env.local`，tracked prefix scan clean。
- 真實／mock：NATS server 2.15.0 與 nats-py 2.16.0 為真實 L2；故障時點由測試控制。
- 下一步：T10 gateway/session/Origin/single-writer/snapshot/reconnect 與小型控制 UI。

## 2026-09-24／T10 交接

- 完成與變更：FastAPI loopback gateway、短效 session/Origin/Bearer auth、single-writer per client、bounded urgent/normal queues、snapshot/reconnect、turn/cancel/kill-switch APIs 與小型控制 UI。
- 驗收：`scripts/check` 通過 55 tests（3 real-provider opt-in skips）；慢 client 隔離、50 producers、100 reconnect、真瀏覽器 walkthrough 及 disconnect cleanup regression 通過。
- 工作區：`main`，所有變更仍未提交；Groq key 保持於 ignored mode-600 `.env.local`。
- 真實／mock：Uvicorn/HTTP/WebSocket/browser 為本機真實 L2；Core turn handler 尚為注入 port，T10 不執行工具或音訊。
- 下一步：T11 核實 AIRI commit/license/API，完成 speech/emotion/cancel/offline adapter spike 或記錄可重現阻礙。

## 2026-09-24／T11 交接

- 完成與變更：鎖定並稽核 AIRI `595ea7260d95d25a654572cfdd52e96cb9441290`；確認 MIT；提交公開 body API 的可重現缺口；選定最小 Web renderer；建立 speech/emotion/cancel/status port 與 fail-closed adapter。
- 驗收：`tests/contract/test_body_adapter.py` 覆蓋三種控制與 offline；完整 gate 結果見 T11 evidence。
- 工作區：`main`，所有變更仍未提交；Groq key 保持於 ignored mode-600 `.env.local`。
- 真實／mock：AIRI source/license/API 稽核為真實；body adapter 為 L1 合成 transport；未使用或宣稱假 Live2D 資產。
- 新決策與缺陷：AIRI 的 body 原語是 Stage 內部 API，公開 extension protocol 無直接 speech/emotion/cancel；改採最小 Web renderer。
- 下一步：T12 先完成 renderer transport/故障隔離；真 Live2D 動作與畫面因缺合法資產保持 BLOCKED-EXTERNAL。

## 2026-09-24／T12 部分交接

- 完成與變更：新增獨立 `/ws/body`、單 owner/單 writer renderer transport、有界 queue、offline/reconnect isolation，以及可實際開啟的 `/body` renderer shell。
- 驗收：`scripts/check` 通過 61 tests（3 real-provider opt-in skips）；A07 L1 證明 body failure 後文字/記憶持續及重連；真 Uvicorn/browser 顯示 renderer online，HTTP session 與 body WebSocket 成功。
- 真實／mock：gateway/browser/WS 為本機真實 L2 transport；角色只是明示 placeholder，沒有宣稱 Live2D。
- 外部阻礙：Cubism Core 為專有授權，官方 sample models 另受 Free Material License；需要 owner 接受適用條款並由官方來源取得 SDK/模型。
- 下一步：取得合法 SDK Core 與模型後接上 motion/expression/idle/look target，執行 kill/restart A07。

## 2026-09-24／T17 交接

- 完成與變更：五類記憶、migration 005/FTS5、identity/person/time/source/kind filters、衝突 semantic facts、revision/correction/deletion/derived invalidation，以及認證管理 API。
- 驗收：A10 固定 20 組為 20/20 top-5；A11 更正、刪除、scope、FTS rebuild、backup/restore 均通過；`scripts/check` 66 passed、3 opt-in skips。
- 工作區：`main`，所有變更仍未提交；secret 維持 ignored。
- 真實／mock：SQLite、FTS5、migration、backup/restore、ASGI API 為真實 integration；資料為 deterministic 合成 L1。
- 下一步：T18 實作 bounded/cancellable/idempotent consolidation、provenance、relationship revisions 與 trait clamps。

合法實作狀態：TODO → IN-PROGRESS → VERIFYING → DONE；有問題可標 BLOCKED-EXTERNAL/FAILED，解除後回 IN-PROGRESS。若只有模擬測試完成，寫「L1 完成，L2/L3 待驗」，不改成完整 DONE。

## 每次交接追加

```text
日期／任務：
完成與變更檔案：
驗收命令、結果、證據路徑：
目前 branch/commit/dirty state：
真實／mock／尚未驗證：
新的決策與缺陷：
下一步具體動作：
```
