# Runtime 產品入口

2026-10-07 更新。RT-013、RT-015、RT-011 summary 已由原 DEFER 轉為可使用的有界切片；詳見 [交付證據](../evidence/runtime-product-2026-10-06/REPORT.md)。這不代表所有 provider、硬體或長期自主行為已驗收。

## 啟動

在 SiroV2 目錄執行 `scripts/start-runtime-product`。它選用 candidate、準備 Rust binary，載入 `.env.local` 中四個模型連線欄位（shell 設定優先，不印出 key），沿用 shell 的語音設定；選支援的 GPT-OSS 時校驗 pinned tokenizer。預設網址 http://127.0.0.1:8000。已有服務占用時不會強制停掉它；可設定 `SIRO_GATEWAY_PORT=8026` 使用其他入口。

正式入口沒有模型或已準備的 Live2D 時會明確停止，不再默默用固定離線回覆代替。Native budget 目前有已驗證 profile 的模型是 Groq `openai/gpt-oss-20b`；其他設定會在入口說明尚未支援的預算設定，不會接受後每次聊天失敗。其他模型需自行明確配置既有 guard，入口不自動關閉。

本機已有 SDK 時會準備單一 Haru 角色。保留呼吸／待機動作和指向互動；表情由 SIRO 情緒統一控制，重新載入保留最新表情。暫不提供未驗證的多角色切換。SDK 及角色資產仍在本機，未納入 Git。語音播放可獨立開關；不以隨機 SDK 音效或假嘴型冒充 TTS 同步。

## 日常對話與電腦協助

首頁以角色和對話為主，記憶／電腦協助在下方，技術資訊在進階設定。可以直接問候，或請她查系統資訊、列檔、啟動程式；`computer.execute` 經原授權與工具紀錄路徑，使用本機一般帳號可存取的路徑。指定工作目錄只是額外的受限讀檔入口，不是整台電腦能力的上限。工具結果保留；模型整理失敗時不會為了重試回覆而重做已完成工具。

「記住：…」由 SIRO 自動記錄來源並保存在本機，無需自行提供來源編號。可從共同記憶面板更正／刪除；正常關閉聊天不會清空資料庫。雲端對話不會自動取得本機限定的記憶／偏好內容，因此已保存不代表目前雲端模型可讀。最近完成對話的有界續作與永久記憶分開處理。

已設定的雲端對話會明示路由，cloud 開關可拒絕新雲端回覆並取消進行中的工作。播放語音預設關閉，可獨立開啟。

## 我的工作目錄（RT-013）

控制頁顯示可讀取的目錄。預設為 `SIRO_DATA_DIR/workspace`（SIRO_DATA_DIR 未設則 `.siro-data/workspace`）。把要分享的 UTF-8 文字檔放入該處，按「列出檔案」或輸入相對檔名後按「讀取檔案」。讀取上限 8 KiB；不會以一般命令工具繞過此入口的越界拒絕。

`SIRO_WORKSPACE_DIR` 可在啟動前指定其他工作目錄。模型可經既有授權／journal 路徑使用 filesystem.read/list；畫面上的明確 owner 讀取經相同 service、signed grant 與 Rust scope，無需模型。兩者都受 tools kill switch 控制。這是讀檔入口的限制，不是對既有 computer.execute 提供整台電腦 sandbox。

## 閒置記憶整理（RT-015）

先說「記住：我喜歡無糖茶」。閒置約 15 秒後，由單一工作每 5 秒檢查，整理最近最多 100 筆有效的 owner episodic 記憶；每輪最多 5 秒。可用「現在整理」觸發，前景仍優先；100 次觸發合併成一個待辦訊號。

畫面按相同文字歸組，顯示來源／版本；長內容顯示摘錄。可更正／刪除原始記憶，舊整理結果立即在下次讀取時失效，下一輪重建。不自動合併矛盾、不產新 committed facts、不改人格、不發通知、不使用 cloud。

整理是可丟棄 view，重啟重新建立，沒有新的 background durable queue 或待重播效果。「暫停整理」只影響本次啟動；要持續停用，啟動環境設定 `SIRO_MEMORY_ORGANIZATION_ENABLED=0`。原始記憶／revisions 不受停用影響。

## 長對話續作（RT-011 summary）

啟用後最多帶入同 session/privacy 最近 24 組完成對話。舊的長 assistant 回覆採本機摘錄；請求超限時，對更早已完成區段作一次摘錄，再經原 byte/native budget 檢查。摘要附版本、來源位置與 SHA-256，保留原始 journal；不另呼叫 LLM，不新增外送或永久記憶。

所有 user 目標、system／授權、未完成 pairs、最新觀察保留。摘要會省略中段並明示省略，並非完整語意摘要；不保證無限長歷史或所有細節都在 context。若仍超限則明確失敗，不偷偷裁掉目標／pending pair。

更正／刪除記憶會取消採舊 context 的在途回覆；摘要模式下，新請求不恢復該 mutation 之前的舊 run（保守的全域失效）。原始對話留存不等於仍被摘要使用，也不等於記憶刪除會抹除原始聊天與備份。

## 回滾

先正常停止／drain Gateway，再以需要的開關重啟：`SIRO_WORKSPACE_ENABLED=0`、`SIRO_MEMORY_ORGANIZATION_ENABLED=0`、`SIRO_CONTEXT_SUMMARY_ENABLED=0`。不移除 DB、journal、原始記憶或既有 budget／privacy guard。Rust-owned process 與背景 task 在 shutdown 清理；啟動失敗明報，不偷偷降級至更弱的檔案 backend。
