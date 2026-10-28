# SIRO 自主性審計（唯讀）

範圍：`src/siro`（main 工作區，未改程式）。「預設」= 未設 env 時的行為。`gateway.py` = `src/siro/services/presentation/gateway.py`，`integrated.py` 同目錄。

## A. 只能手動觸發的功能

| 功能 | file:line | 現行觸發 | 預設 |
|---|---|---|---|
| `/plan` ／`規劃：` 規劃 | integrated.py:122-127, 411-446 | 使用者訊息前綴；flag 關閉時回覆說明但不執行 | **關**（需 `SIRO_AGENT_PLANNER_ENABLED=1` + candidate + planner_factory，planning_adapters.py:22-26） |
| 規劃續做（resume） | resume.py:39；integrated.py:1432, 1458 | 重啟時自動續做未完成 read-only plan；不是對話觸發 | **關**（`SIRO_AGENT_RESUME_ENABLED=0`，且需 planner 已開） |
| `/recap` | 未找到 | 程式內無此指令（僅有 `SIRO_CONTEXT_SUMMARY_ENABLED` 的舊回應摘要，gateway.py:2185，預設開，非使用者指令） | 不存在 |
| 請記住／remember 寫入記憶 | core/memory.py:190；memory_candidates.py:34；integrated.py:624 | 僅「記住：」「請記住：」「幫我記住：」「remember:」開頭的使用者句；無推論式自動記憶 | 開（`SIRO_MEMORY_INGRESS_ENABLED`，gateway.py:2808，僅 candidate） |
| 提醒（建立／取消／列出） | agent/reminders.py:233-251；integrated.py:407；gateway.py:2954 | 使用者句含「提醒」「取消…鬧鐘」才建立；到期後自動播報（deliver_reminder，integrated.py:365） | 開（`SIRO_REMINDER_ENABLED`，reminders.py:173） |
| 觸摸回應 | integrated.py:292；gateway.py:2812, 3097 | 桌面角色 pat/poke/carry 事件；說話受冷卻（60s）、每日 15 句、忙碌抑制 | 開（`SIRO_TOUCH_REPLY_ENABLED`）；關閉仍記觸碰 |
| 目標任務（goal tasks／read tasks） | gateway.py:2875, 2891 | API `/v1/goal-tasks/*`（gateway.py:138）使用者建立 | 開（`SIRO_GOAL_TASKS_ENABLED`，僅 candidate+workspace） |
| 事後修改／刪除記憶 | HTTP correct/delete/revisions（DECISIONS.md:191） | 只有人工 API；無模糊文字更正 | n/a |

## B. 自主／背景功能與 flag

| 功能 | file:line | 現行觸發 | 預設 |
|---|---|---|---|
| Self-activity（自主活動排程＋自筆記） | gateway.py:2905-2950（`SelfActivityScheduler`）, 2862 | 閒置＋`work_context.may_interrupt()`＋非前景時自動；完成後 `share_finished_note` 自動分享並寫入記憶（gateway.py:2921-2929） | 開（`SIRO_SELF_ACTIVITY_ENABLED=1`，僅 candidate，且需 `tools` kill-switch 允許） |
| 閒置記憶整理 | gateway.py:2899 | 閒置自動；前景忙碌暫停 | 開（`SIRO_MEMORY_ORGANIZATION_ENABLED`，僅 candidate） |
| ESP32 MQTT 感測／世界狀態 | gateway.py:2365 | 訂閱 broker→DeviceRegistry/WorldModel（mqtt_subscriber.py，未追蹤新檔） | **關**（`SIRO_ESP32_MQTT_ENABLED` 須 =="1"，無預設值；需 `SIRO_ESP32_MQTT_HOST`） |
| ESP32 HTTP 狀態讀取 | gateway.py:2338-2363, 3107 | 僅被動讀取（`on_esp32_http_state`），只供查詢，沒有主動反應 | 依 device 設定存在與否 |
| 感測／世界狀態 → 角色主動反應 | 未找到 | WorldModel 只存狀態；除觸摸外沒有「感測器變化→主動說話」路徑（`react_to_touch` 為唯一 body 事件反應） | 不存在 |
| 速率限制恢復 | gateway.py:2198 | 自動等待重試 | **關**（`SIRO_RATE_LIMIT_RECOVERY_ENABLED=0`） |

## C. 其他預設開的 `*_ENABLED`（參考，非缺口）

`SIRO_CONTEXT_SUMMARY_ENABLED`(gateway.py:2185)、`SIRO_MODEL_RETRY_ENABLED`(2195)、`SIRO_CONTEXT_TOKEN_BUDGET_ENABLED`(2230，launch_companion.py:70)、`SIRO_BROWSER_SESSION_ENABLED`(2405)、`SIRO_WORKSPACE_ENABLED`(2618)、`SIRO_CODEX_ENABLED`(2649)、`SIRO_SESSION_RESTORE_ENABLED`(2802)；皆預設 1。

## D. 結論：預設關閉或僅手動的缺口

1. **規劃器＋續做**：`SIRO_AGENT_PLANNER_ENABLED`、`SIRO_AGENT_RESUME_ENABLED` 預設 0；規劃只能由 `/plan`／`規劃：` 觸發，沒有自主發起規劃。
2. **ESP32 MQTT** 預設關，且感測資料不會觸發主動反應（只有觸摸）。
3. **`/recap` 不存在**。
4. **記憶寫入僅限明確「記住」前綴**（設計如此，見 DECISIONS.md:191）；唯一自動寫入是 self-activity 的 sourced note。
5. **速率限制恢復**預設關。
6. 多數 flag 僅在 `runtime_profile == "candidate"` 生效；legacy 無此功能。
7. self-activity、提醒、觸摸、記憶整理雖預設開，但需 candidate／kill-switch／quiet 條件，實際是否運作取決於啟動 profile，審計未實跑驗證。

---

## E. 代理人化評估（companion → daughter：由她自己判斷，不靠手動輸入）

判準：①誰決定要做（使用者字串／規則 vs 模型自行判斷）②有無主動發起 ③有無回饋閉環。

| 能力 | 現況：誰決定 | 離「自己判斷」的差距 | 建議方向 |
|---|---|---|---|
| 記憶寫入 | 規則：只認「記住：」前綴 regex（core/memory.py:190）；自主活動筆記是唯一自動寫入 | 她聽到重要事實（生日、偏好、重要事件）不會自己記；無「值得記嗎」判斷 | 對話結束後由模型提名候選記憶（memory_candidates.py 已有雛形）→ 低風險自動提交（可刪、標來源），高風險請確認 |
| 提醒 | 關鍵字「提醒」＋規則解析時間（reminders.py:235） | 「我下週三要面試」不會自動建立提醒；無法自己決定何時主動關心 | 模型工具 `reminder.create`，或由記憶中的時間事件自行排程 |
| 規劃 | 使用者前綴 `/plan`；flag 預設關 | 不會自己判斷「這件事該先規劃」；resume 預設關 | 讓模型在 tool loop 中自行呼叫 planner；先開 PLANNER／RESUME flag 做隔離驗證 |
| 自主活動 | **已是自主**：10 分鐘 tick、主人離開≥10 分、冷卻 45 分、每日 6 次（interests.py:163-185），興趣由 InterestPicker 選 | 只能做「興趣探索」；不會因主人狀態／待辦／記憶而選題；目標來源單一 | 把選題輸入擴到：未完成目標、近期記憶、提醒、感測狀態 |
| 目標任務 | 使用者呼叫 API 建立 | 不會自己提出或接續目標 | 允許自主活動產生 goal task 提案（待主人批准） |
| 觸摸 | 事件驅動＋規則冷卻（TouchReplies） | 這是反應式，可接受；但不影響情緒／長期關係 | 觸摸寫入情緒狀態，供自主活動參考 |
| 感測／世界狀態 | 只存不反應；MQTT 預設關 | 沒有「PIR 偵測到人回家→打招呼／結束自主活動」 | 世界狀態變化訂閱 → 觸發決策 tick（在場/離開驅動自主活動與問候） |
| 記憶整理 | 閒置自動（已自主） | 僅合併相同內容，不推論 | 維持，符合保守設計 |
| 工具使用 | 模型在對話中可呼叫工具（tool orchestrator），受 kill-switch／核准 | 屬模型自行判斷，已符合；自主活動內亦可用 | 無 |
| 主動開口 | 只有提醒到期、自主活動完成後分享（share_finished_note）、觸摸 | 缺「主動關心／問候／追問」的統一決策器 | 新增單一 proactive 決策層（輸入：在場、時間、記憶、情緒、冷卻），輸出：說／不說／做事 |

### 結論
- **已自主**：自主活動排程、記憶整理、工具選擇。
- **規則式（需模型判斷化）**：記憶寫入、提醒建立、規劃發起。
- **完全缺**：感測驅動反應、統一主動決策層、自主提出目標。
- 建議順序：①感測在場→決策 tick ②模型提名記憶／提醒（工具化）③開 planner/resume ④統一 proactive 層。皆須沿用既有安全邊界（kill-switch、可刪除、來源標註、每日上限）。
