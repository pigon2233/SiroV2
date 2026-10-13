# Data flow 與 state ownership

| 輸入 | 路徑 | owner / persistence | 實際 output consumer | 缺口 |
|---|---|---|---|---|
| typed text | index POST turns → on_turn → IntegratedCompanion → Core → model | conversation SQLite + in-memory WorkingMemory | control WS → DOM | UI 固定 browser session；重啟不載回 WorkingMemory |
| microphone | MediaRecorder → WAV → POST transcriptions → GroqWhisper → submitText(speech) | browser capture；API key 在 server | 與文字共用回覆 | 本次未測真 mic/AEC；binary audio service 不等於主頁錄音路徑 |
| affect | user event → appraise → SQLite record_result | affect repository、in-memory affect system | context、affect_state WS、ExpressionPolicy/body | 自我喜好種子/文字判定存在；不代表自主長期學習已接通 |
| relationship | user text → relationship_event_from_text → update | relationship revisions | model verified_context、UI state | 非所有工具 outcome 都經此主路徑更新 |
| memory | recall + authenticated browse/correct/delete | SQLite FTS/source/revisions | prompt、API | 未見每次正式聊天自動 remember；event/message 寫入不等於 memory commit |
| tool call | ModelChunk → proposal → approved → executor → observation | proposals + AgentRun tables | continuation prompt + tool_result WS | 無原生 call/result message pairing；result 被宣稱 trusted text |
| speech | assistant terminal → browser fetch speech → render worker | worker cache + browser playback | Audio/角色口型 | 完整 bytes 回傳；非 token/句段串流；Qwen 忽略 prosody 參數 |
| body intent | MinimalWebBodyAdapter → WebSocketBodyTransport | renderer 暫態狀態 | Cubism dist 或 body placeholder | 真 renderer 外部資產需配置；本次未畫面驗證 |
| device state | MQTT/HA adapters → projector/registry/world | device/world repositories | room controller（demo/test） | Gateway main 無此 subscription |
| distributed job | nodes/router/jobs → TCP worker | job/lease/epoch 元件 | run_job consumer（tests） | 正式 model path 未經 router |

## 信任與恢復

工具輸出、網頁內容、記憶文字應是資料。目前 continuation 使用文字 `trusted runtime observation`，但網頁/子程序輸出仍可含不可信內容。這是資料來源與指令角色混合的風險，不是已證實的攻擊。

SQLite 持久化是存在的；session token、active_turns、WorkingMemory、agent step counter 在記憶體。AgentRun.latest 只找最近 run，沒有在啟動时掃描 RUNNING/WAITING_TOOL 並重建完整訊息鏈。資料留存不能等同 crash recovery。

設定有兩個 owner：config.py JSON settings（CLI/doctor 等）與 gateway.main 的環境變數/檔案存在判斷。不能把 SiroSettings 的 privacy/budget 值當成 Gateway 已套用的設定。
