# Windows 的 SIRO 啟動方式

本機採 E 槽 Ubuntu／WSL2。Windows 原始碼留在目前資料夾，執行副本、Python環境、角色、模型、語音和資料庫放在 `E:\WSL\Ubuntu` 的虛擬磁碟內。

## 日常使用

在 Windows 雙擊專案根目錄的 `Start-SIRO-VRM-Win.cmd`。這是唯一的日常入口：後端在這套 Ubuntu／WSL 裡啟動，桌寵是 Windows 上的 Electron 視窗。系統匣是唯一的系統入口，工作列不會多一顆按鈕；按「暫藏」之後從系統匣點回來。完全離開用 `Start-SIRO-VRM-Win.cmd /stop`，或雙擊 `Stop-SIRO-Win.cmd`（它只轉呼叫 `/stop`）。

成功啟動時不會留下命令列視窗，也不會另外開啟瀏覽器。後端沒起來時才會跳出說明。`/backend` 只開後端；`/candidate` 預覽候選 VRM，後端還在跑時會拒絕，避免蓋掉正式模型。ESP32 的 MQTT broker 與 OTA 轉送只在這台電腦已經放好設定時才安靜啟動。

角色上的「聊聊」可開文字輸入，「控制台」可開完整操作畫面。氣泡的「看看」會開到監控頁裡的活動紀錄。輸入中文用 Windows 的輸入法。

## 舊的 GTK 桌寵

`scripts/legacy/Start-SIRO.cmd` 與 `scripts/legacy/Start-SIRO-VRM.cmd` 是以前的 WSLg／GTK 入口，不是現在的桌寵。那個視窗輸入繁體中文時，使用 Ubuntu 的 IBus Chewing 注音（預設大千鍵盤），而非 Windows 工作列的微軟注音。點「聊聊」後點輸入框，直接按注音鍵並選字；Enter 選字期間不會送出訊息，組字完成後 Enter 才送出。若顯示缺少引擎，在 Ubuntu 執行 `sudo apt install ibus ibus-chewing x11-xkb-utils`，再重開那個舊桌寵。此設定只供舊的 WSL 桌寵使用，不改 Windows 輸入法。

## 模型與語音

目前選用本機 `qwen3:4b-instruct`，不需要 API key。Windows 桌寵使用已登記的 VRM；官方 Haru 只留在舊的 GTK 入口。朗讀已套用使用者選定的 B「甜柔、親切」原創動漫角色聲，以固定合成參考音檔供本機 Qwen Base 產生新台詞。首次載入約需10–20秒；新句仍需合成，同句可用已核對的快取，不把快取速度當新句速度。D64新增本機 Whisper small 語音辨識，CPU執行，原音不外送。

角色下方的「麥克風：關」只切換允許使用，不會開始錄音。開啟後按「開始說話」，在原生權限對話選「允許這次」，說完按「停止並送出」；最長30秒自動結束。「朗讀：開」會播放後續回覆，也可在聊天面板重聽上一則全文。「停止」會停錄音／辨識／回覆／播放；正在停止時稍候確認，若顯示未確認不要重送操作。本機辨識冷啟可能數秒，中文仍可能誤字。

「聊聊」使用獨立側欄；按住角色拖動，點一下可開對話。`－`／`＋`縮放角色，百分比按鈕還原；對話文字不隨角色縮小。Haru沒有完整腿部動作，步行、坐下與自由漫遊另行交付。

## 檔案與更動

Windows資料夾是編輯來源。Ubuntu執行副本會核對來源hash，**不會自動套用之後的Windows修改**。改完程式需重新準備與驗證副本，不能只重開舊桌寵就當新程式已載入。

Windows 入口優先使用專案裡的 `scripts/start-companion`（只開後端）。本機若另有 `~/.local/bin/siro-companion-vrm`，只在專案這份啟動失敗且連接埠還沒被佔用時才退回去用它。實際來源／環境與資產位置仍可能記在 `~/.local/share/siro/local-runtime.json`。資料與 log 獨立存於 `~/.local/share/siro/data`／`logs`；勿刪除這些目錄來處理啟動問題。後端啟動紀錄在 `/tmp/siro-vrm.log`。Ollama 模型在 `~/.local/share/ollama/models`，未加入 Git。

## 診斷

在PowerShell執行：

```powershell
wsl -d Ubuntu -- systemctl --user status ollama.service --no-pager
wsl -d Ubuntu -- bash -lc "~/.local/bin/siro-companion --doctor"
```

本機Ollama只綁 `127.0.0.1:11434`，雲端功能停用。SIRO網址預設 `http://127.0.0.1:8000/`；未經授權不要將服務改綁外網。若port已被其他SIRO服務占用，先確認其資料目錄和來源，再正常停止；不要直接廣泛終止同名程序。

SDK／角色採使用者本聊天明確同意的官方授權，個人接受紀錄與assets manifest留在Ubuntu本機，不放進Git。實際通過項目、未驗功能與已知限制以 [STATUS](STATUS.md) 及本輪證據報告為準；本文件不宣稱整個專案或正式發布完成。

現有 doctor 是 minimal 診斷；舊 config.json、wpctl、Docker 可能顯示 unavailable。本機入口採 wrapper 的明確環境設定；文字對話與角色已另做真整合。Docker容器broker、Linux系統音控與真人音訊未驗，不能以 minimal doctor exit0 當這些功能已完成。
