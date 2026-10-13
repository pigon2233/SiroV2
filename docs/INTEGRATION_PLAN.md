# SIRO 產品整合計劃

> 智能體層的結構性缺口與重建順序見 `docs/AGENT_ARCHITECTURE_AUDIT_2026-09-30.md`。

狀態日期：2026-09-27。這份計劃以「使用者能完成一條真實流程」為完成單位，不再以元件測試數量代替產品狀態。

## I01 文字 Companion 閉環

輸入框 → authenticated gateway → persistent identity/memory → ConversationEngine → Groq/Ollama/offline backend
→ WebSocket delta/terminal → 對話畫面。取消必須進入同一代 generation fence；provider 不可用時需顯示錯誤或
明示 offline backend，不能無回應。驗收以真瀏覽器輸入並看到回答、重啟後 identity/對話資料仍存在為準。

## I02 角色反應閉環

Conversation delta/terminal → body speech/emotion/cancel intent → `/ws/body` → renderer。先以 protocol renderer
證明消息，再將 Cubism 頁接入；角色離線不阻塞文字。驗收需看到回答時角色狀態變化，取消時停止當代動作。

情緒、偏好與長期關係的決策層依 `docs/RESEARCH_EMOTION_ARCHITECTURE.md` 的 E01–E07 驗收；只有 renderer 表情不算完成。

## I03 語音閉環

mic → VAD/STT → I01 → TTS → playback/lip-sync；沿用 T16 generation fence 與 AEC。驗收是真人說話得到可聽
回答，20 次打斷不復活舊音。缺 provider 時保留文字模式並明示原因。

目前控制頁已接上手動開始／停止錄音、瀏覽器單聲道 WAV 編碼、認證轉錄 API、Groq Whisper、既有文字 turn 與
本機 Kokoro 82M CPU TTS/Live2D 播放。服務端以 microphone kill switch、來源檢查、短效 token 與 10 MiB 上限保護；待 owner
使用真麥克風完成同頁走查後由 VERIFYING 改為 DONE。

## I04 電腦操作閉環

對話產生受限 tool proposal → UI 顯示範圍與風險 → owner grant → Rust Runtime／browser driver → readback →
對話結果。第一個切片只允許 scoped browser navigate/read；未授權不得執行。

第一個切片已於 2026-09-29 完成真瀏覽器驗收：對話中的明示 URL 形成 pending proposal，tools kill switch
關閉或未按單次授權時不執行；授權後以該 URL 的 origin 建立 scoped Playwright session，將 title、頁面文字與
screen version 回傳控制頁。後續切片再接表單與其他電腦能力，不擴張本次 grant。

2026-09-30 修正方向：關鍵字／應用程式 alias 只能作為底層 resolver，不得作為自然語言規劃器或通用控制的
完成證據。I04 改採 OpenClaw／Codex 類型的 agent loop：模型收到動態 tool catalog，產生結構化 tool call；
policy 驗證並在需要時建立單次 grant；executor 回傳 observation；模型依 observation 選擇下一步，直到目標
完成或明確失敗。`ConversationEngine` 已保留 tool calls，IntegratedCompanion 會把模型選出的 capability 與參數
直接送入 persistent proposal orchestrator；授權執行後，observation 會回到模型，最多連續 8 步。I04 仍維持
IN-PROGRESS，因為可持續的 GUI/browser session、取消執行中的子程序、權限 profile 與 sudo broker 尚未完成。

2026-09-30 第二階段：新增 migration 011 與 SQLite-backed proposal orchestrator。Tool call 的 capability、arguments、
arguments hash、風險、狀態、observation 與 error 會跨程序保存；批准時重新驗證 arguments hash，並以原子狀態轉移
限制 pending → approved/denied → running → completed/failed。Gateway 已改用此 orchestrator，移除程序內臨時
proposal 字典。

2026-09-30 第三階段：IntegratedCompanion 已接上模型工具目錄、持久 proposal 與 observation continuation；
新增通用 `computer.execute` argv 工具，具有 120 秒上限、64 KiB stdout/stderr 上限、detach 模式與
secret 環境變數清除。真 Groq 驗證中，模型自行提議 `printf agent-loop-ok`，未授權時保持 pending，
授權後取得 returncode 0/stdout，並依 observation 完成最終回答。正式 Gateway 已停用關鍵字捷徑；
該捷徑僅保留給舊合約測試。

## I05 設備與發布閉環

把 simulator trace 接入 System/Devices UI；真 HA/ESP32 到位後跑 A18。I01–I04 通過後才執行 T35 24-hour
soak，不再把獨立元件 gate 稱為 v1.0 產品完成。
