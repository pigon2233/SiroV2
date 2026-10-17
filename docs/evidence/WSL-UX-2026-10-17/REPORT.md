# D64 桌寵、語音及停止修復驗收

日期：2026-10-17。範圍是使用者回報的麥克風／朗讀不可用、聊天遮擋角色、縮放／拖曳缺口與長回答無法停止。沿 T12 桌面體驗子任務及 D64 契約修復。結論為 **LOCAL_VERIFIED_WITH_MANUAL_LIMITS**；真人收音、聽感及實體滑鼠操作尚未驗，不把短問候成功當完整體驗通過。

## 已交付及根因

| 回報 | 已確認原因與修正 | 證據界限 |
|---|---|---|
| 麥克風打不開 | 原生 GI 的 audio/video 布林 property 被當函式；改正後僅 audio-only 明確允許。新增可見麥克風開關，沿原 kill switch | 真 WebKit 開一條 audio track 後立即 stop，未讀取／錄製環境樣本 |
| 錄音不能送出 | 缺 GStreamer uritranscodebin；補官方 Bad Plug-ins。預設 MP4 雖宣告支援仍解碼失敗，產品明確優先 WebM Opus | 真 MediaRecorder→decode→PCM WAV，但使用已知合成音源 |
| 沒有語音辨識 | 本機原先未配置 STT；新增顯式本機 Whisper small、CPU int8、offline adapter，45 秒辨識 timeout／30 秒輸入界限 | 真 SDK／HTTP 成功；中文已有誤字，沒有品質或延遲 SLO 通過聲明 |
| 語音播放不出來 | WebKit WebsitePolicies 預設 ALLOW_WITHOUT_SOUND；在既有可信 loopback WebView 建構時設 ALLOW | 真 speech HTTP、原播放函式、Pulse sink input、ended；無真人聽驗 |
| 聊天遮擋／無法縮放／只能點移動 | 改分離側欄、控制列留角色下方；原生有界 60%–150% 縮放；同源角色 pointer drag 跨門檻送 native move | 真 Chromium pointer 事件及 GTK/Haru 幾何通過；實體鼠標移動未驗 |
| 長回答無法停止 | HTTP 等 headers 前沒有取消 watcher；UI 尚未取得 turn_id 的提交、晚到輸出也有競態 | 新反例／相鄰回歸及真 Ollama 串流按停止通過 |

保留同一 WebView／DOM／session／renderer／audio owner，沒有第二套播放器；角色縮放不縮小聊天文字。sandbox、loopback／Origin、camera deny、權限與 kill switches 保持。停止同時終止錄音、未提交轉錄、模型串流及播放器；取消 ACK 只表示受理，terminal 或 canonical snapshot 加舊提交收束才確認停止。超過 5 秒仍未確認會保持可理解的未確認狀態及提交阻擋，不自動重送。

模型預設 512 輸出預算、D63 的截斷／缺終止失敗判定及工具釋出邊界不變。本輪找到了具體取消缺陷，沒有證據顯示所有長回答均來自無限自動重試，也沒有以放大上限掩蓋問題。

## 最終來源與實際入口

最終執行副本 ID 見 [RESULTS.json](RESULTS.json) 的 `code_identity.source_id`，短碼 `218c21940570`。Windows 原碼仍在 E 槽；執行副本、專用 Python 環境、模型／資料位於 E 槽 Ubuntu VHD。此為可核對的本機副本，沒有宣稱簽署正式 release。

副本 locked sync、compileall、Cargo build 均 exit0。371 份非文件來源的 Windows bytes 與副本 manifest 再核對一致，包含完整 src closure；文件在驗收後更新，故不宣稱副本內 STATUS 已同步。共用原 venv 未被改指向副本。

先用 SQLite backup API 做一致私有備份及保存舊本機設定，只記錄備份成功與路徑 metadata，未讀取對話；未把 DB、key、私人錄音、私人畫面或原音加入 Git。安裝 wrapper／選單後實際經 Windows `Start-SIRO.cmd` 開啟，檢查 PASS 並保留執行：

- `/health/ready` 為 healthy；model=`ollama:qwen3:4b-instruct`、audio=`local:faster-whisper-small`、tts=`local:kokoro-82m-zf-xiaobei`。
- 唯一指定副本 gjs host，PID 記於機讀結果；來源副本內沒有 `.siro-data`。
- minimal doctor 的 gateway available；舊 config.json、wpctl、Docker unavailable 如實保留，不能以 minimal exit0 宣稱這些能力完成。

## 自動與真實整合結果

| 類別 | 實跑結果 | 範圍 |
|---|---|---|
| 最終副本相鄰測試 | **327 PASS／1 warning／21.01s／exit0** | 命令完整列於 RESULTS；含未修改的 5 秒啟動 gate、HTTP／gateway／語音／桌面／取消 |
| 前端與 session 回歸 | **381 PASS／1 warning／54.28s／exit0** | 所有 test_frontend 與 session 測試；與上一組重疊，不加總 |
| 新反例 | HTTP 4 FAIL／3 PASS→7 PASS；UI 停止 8 FAIL／2 PASS→10 PASS；mic 先4 FAIL→PASS，另 start-error 先 FAIL→修復；STT 14 PASS | mock／合成 socket／owned process／原頁面函式分開，沒有稱為真人 |
| 相關靜態 | Ruff check／format／mypy PASS | 受影響 Python 及新測試；另 Bash／JS 語法檢查通過；未跑本輪全 scripts/check |
| 真模型／Haru | **PASS**，ready0.808s，短問候 completed、0 工具 | 臨時合成資料，無私人歷史；Chromium 真服務與本機模型 |
| 真模型停止 | **cancelled／0.072s／0 工具** | 請求從1數到500，收到第一段文字後點停止；5秒內確認且後續顯示文字穩定、提示已停止 |
| 真原生角色 | ready／alpha／sandbox true、snapshots3、唯一 canvas | GTK/WebKit／真 Haru；整合後 native 正常關閉，backend stop143及PID清理 |
| 桌面 UX | 60%／100%／150% 下角色、聊天與控制列矩形分離且可見；唯一 iframe | 真 GTK／Haru＋Chromium；實體 Windows 拖曳 NOT_RUN |
| 真播放 | speech plan200→speech200 audio/wav→原播放器 ended、UI全文完成、Pulse sink input 被觀察 | 合成「測試」；真人聽感 NOT_VERIFIED |
| 真裝置可開 | audio-only 許可，1 track，立即 ended | 未讀音訊樣本，不是收音品質驗收；getSettings sampleRate=0 如實保留 |
| 原錄音流程合成閉環 | MediaRecorder→WAV→真 Whisper HTTP200→stub submit 一次；tracks ended、controller detached、server joined、worker不忙 | 不開實體麥克風、不接喇叭、不呼叫 LLM、不保存錄製音檔 |
| 本機 ASR | CPU int8／9.094s 冷辨識，無 runtime download | 合成2.432s中文；預期「本機」實得「本集」，品質門檻未驗 |

兩組 pytest 的 warning 均為既有 Starlette TestClient/httpx deprecation，沒有為此更換依賴。真停止數值是這一次合成請求的觀測值，不是百分位 SLO、GPU 取消 ACK 或所有工作類型均可在相同時間終止的證明。

## 依賴、失敗與測試修正紀錄

新增官方 faster-whisper 1.2.1（MIT）、固定 Systran/faster-whisper-small revision（MIT），來源／hash／完整模型清單見 RESULTS 及 [DEPENDENCIES](../../DEPENDENCIES.md)。模型只從顯式本機路徑載入；原音只在記憶體與 worker stdin，單一 worker、有界輸出，取消／timeout terminate→kill→join。未配置仍 disabled，原 Groq route 保留、無 cloud fallback 或新 key。

首次真 ASR 因 PyAV19 移除 metadata_errors 失敗；核實官方介面後將 PyAV 限 `>=16.1,<17`、lock16.1.0，真辨識才通過。uv.lock 現103 packages；沒有修補第三方 SDK source。官方 Ubuntu Bad Plug-ins 補 uritranscodebin，額外 Pulse／GStreamer tools 為診斷用途；沒有另開音訊 server、關閉 sandbox 或把安裝工具誤當播放驗收。

最初 gateway disconnect watcher 讓快速 mock 辨識的 cleanup 卡住；中斷並保留失敗輸出，改以 recognition_finished event 收束後，原案例及14個本機 STT案例通過。前端另重現 MediaRecorder.start 拋錯會漏停 tracks，先增失敗案例才補清理。MP4 合成 decode 仍失敗，未列為通過；產品優先 WebM Opus，該實際路徑通過。

舊語音 fragment fixtures 接入同一前景控制 factory，區分 service 與 TTS status，下一回合加入明確新 submit；限流 fixture 檢查 retry notice 撤除並允許新停止狀態，原語音／零重播安全斷言保留。共用 Node harness 改 stdin，解 Linux 單 argv 128KiB 上限，不縮頁面、不減案例。真瀏覽器測試首次缺 chromium executable；指向本機已安裝的真 Playwright Chromium 後4案例通過，沒有以 stub 取代。初輪381組合失敗留在本機日誌，不冒稱首跑即通過。

D63 的既有 protocol fixture 唯一修改已另記 D63：完整模型成功前不釋出工具；其原錯誤分類／partial文字／無fallback斷言保留。舊 WSL-SETUP 報告保持歷史原貌，不把當時 audio disabled 或261測試覆寫成此輪結果。

## 已跑命令與重現

以下是本機實際執行入口；`.siro-data/wsl-setup` 是保留在本機、未加入 Git 的隔離驗收腳本與合成輸出，不是產品入口。可攜的回歸測試位於 `tests/contract/test_http_stream_cancel_phases.py`、`tests/integration/test_frontend_stop_race.py`、`test_frontend_microphone.py`、`test_local_whisper.py` 與既有相鄰測試；兩組完整 pytest argv 已收入 RESULTS。

```powershell
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/check_frontend_stop.py green
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/refresh_ext4.py
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/check_ext4.py
wsl -d Ubuntu -- env SIRO_OLLAMA_MODEL=qwen3:4b-instruct bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/verify_integrated.py
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/desktop_ux_qa.py
wsl -d Ubuntu -- /home/pepepig/.local/share/siro/voice-validation-py312/bin/python .siro-data/wsl-setup/voice-input-native-probe.py
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/check_final_entry.py
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/finalize_ux_evidence.py
git diff --check
```

原生整合探針需先關閉正式桌寵視窗，避免同 DBus/application ID 互相接管；探針使用隔離合成資料及臨時 port，不自動停止使用者服務。`check_final_entry.py` 則在正常入口啟動後檢查。語音探針另有 `voice-native-capture-probe.py`、`voice-native-recorder-probe.py`、`voice-api-playback-probe.py`，其實跑結果已按範圍收錄 RESULTS。不要把新準備 snapshot 的成功當整合完成；本報告以最終指定 source_id 的後續測試為準。

## 尚未驗收與接續

真人麥克風音量／語音辨識品質、真人聽感、實體 Windows 直接拖曳／縮放手感、語意／首音 SLO、完整 scripts/check／remote CI、24h與其他硬體、正式發布均未驗。原個人 Qwen 聲線缺參考素材，仍使用 Kokoro 備用；Haru 步行／坐下／自由漫遊未在本次補齊。

下一步按 [WSL_SETUP](../../WSL_SETUP.md) 由使用者試一句語音、聽回覆及拖曳，將真人結果另附於 T12／語音品質驗收。限定本輪缺陷 local 修復通過；其餘產品 gates 保持，未 commit／push。
