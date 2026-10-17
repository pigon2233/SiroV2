# Windows 的 SIRO 啟動方式

本機採 E 槽 Ubuntu／WSL2。Windows 原始碼留在目前資料夾，執行副本、Python環境、角色、模型、語音和資料庫放在 `E:\WSL\Ubuntu` 的虛擬磁碟內。

## 日常使用

雙擊專案根目錄的 `Start-SIRO.cmd`，或從 Windows 開始選單開啟 Ubuntu 提供的「SIRO 桌寵」。關閉角色只會關閉桌寵視窗，後端仍保留資料；重新開啟會接回同一個服務。角色上的「聊聊」可開文字輸入，「控制台」可開完整操作畫面。

在 WSLg 桌寵輸入繁體中文時，使用 Ubuntu 的 IBus Chewing 注音（預設大千鍵盤），而非 Windows 工作列的微軟注音。點「聊聊」後點輸入框，直接按注音鍵並選字；Enter 選字期間不會送出訊息，組字完成後 Enter 才送出。桌寵入口會啟動／選用 Chewing；若顯示缺少引擎，在 Ubuntu 執行 `sudo apt install ibus ibus-chewing x11-xkb-utils`，再重開桌寵。此設定只供 WSL 桌寵使用，不改 Windows 輸入法。

目前選用本機 `qwen3:4b-instruct`，不需要API key；角色為官方Haru。朗讀已套用使用者選定的 B「甜柔、親切」原創動漫角色聲，以固定合成參考音檔供本機 Qwen Base 產生新台詞。首次載入約需10–20秒；新句仍需合成，同句可用已核對的快取，不把快取速度當新句速度。D64新增本機 Whisper small 語音辨識，CPU執行，原音不外送。

角色下方的「麥克風：關」只切換允許使用，不會開始錄音。開啟後按「開始說話」，在原生權限對話選「允許這次」，說完按「停止並送出」；最長30秒自動結束。「朗讀：開」會播放後續回覆，也可在聊天面板重聽上一則全文。「停止」會停錄音／辨識／回覆／播放；正在停止時稍候確認，若顯示未確認不要重送操作。本機辨識冷啟可能數秒，中文仍可能誤字。

「聊聊」使用獨立側欄；按住角色拖動，點一下可開對話。`－`／`＋`縮放角色，百分比按鈕還原；對話文字不隨角色縮小。Haru沒有完整腿部動作，步行、坐下與自由漫遊另行交付。

## 檔案與更動

Windows資料夾是編輯來源。Ubuntu執行副本會核對來源hash，**不會自動套用之後的Windows修改**。改完程式需重新準備與驗證副本，不能只重開舊桌寵就當新程式已載入。

本機命令位於 `~/.local/bin/siro-companion`，實際來源／環境與資產位置由 `~/.local/share/siro/local-runtime.json` 記錄。資料與log獨立存於 `~/.local/share/siro/data`／`logs`；勿刪除這些目錄來處理啟動問題。Ollama模型在 `~/.local/share/ollama/models`，未加入Git。

## 診斷

在PowerShell執行：

```powershell
wsl -d Ubuntu -- systemctl --user status ollama.service --no-pager
wsl -d Ubuntu -- bash -lc "~/.local/bin/siro-companion --doctor"
```

本機Ollama只綁 `127.0.0.1:11434`，雲端功能停用。SIRO網址預設 `http://127.0.0.1:8000/`；未經授權不要將服務改綁外網。若port已被其他SIRO服務占用，先確認其資料目錄和來源，再正常停止；不要直接廣泛終止同名程序。

SDK／角色採使用者本聊天明確同意的官方授權，個人接受紀錄與assets manifest留在Ubuntu本機，不放進Git。實際通過項目、未驗功能與已知限制以 [STATUS](STATUS.md) 及本輪證據報告為準；本文件不宣稱整個專案或正式發布完成。

現有 doctor 是 minimal 診斷；舊 config.json、wpctl、Docker 可能顯示 unavailable。本機入口採 wrapper 的明確環境設定；文字對話與角色已另做真整合。Docker容器broker、Linux系統音控與真人音訊未驗，不能以 minimal doctor exit0 當這些功能已完成。
