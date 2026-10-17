# D66 / 使用者選定 B 聲線的實際接入

日期2026-10-17。使用者選B後依「繼續」完成本機接入，**已經Windows `Start-SIRO.cmd` 重開，正式服務現在使用B的固定參考聲線**。原D65是三檔試聽；本輪包含新文字推論、取消、原生播放與日常入口，未把原試聽當整合完成。

## 交付與來源

以D65的B原創合成音檔（8秒）及其合成台詞作reference，採[官方 Voice Design then Clone](https://github.com/QwenLM/Qwen3-TTS#voice-design-then-clone)流程。官方[0.6B Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base) Apache-2.0、固定revision與完整模型檔案metadata見 [RESULTS](RESULTS.json)。主權重1,829,344,272bytes，tokenizer682,293,092bytes；所有上游LFS SHA256／Git blob核對成功，tokenizer只在exact hash相同時復用。素材、SDK、資料都留E槽Ubuntu VHD，不加入Git。

新增 `SIRO_QWEN_VOICE_PROFILE`，只讀有界本機JSON：version1／voice_id／reference_wav／reference_text。拒未知欄位、無效ID、相對／不存在reference、空或過長／控制字元台詞、壞JSON與超16KiB。明確選定而缺資產時拒啟動，不把Kokoro冒稱B。無配置時原分支保持；參考台詞沿所選reference，不沿用舊硬編碼「爸爸，你回來啦」的不同音檔台詞。

profile ID `siro-sweet-b-v1`有獨立cache目錄，仍沿原完整model／reference／text／SDK／generation／completion指紋。選定profile即啟用既有owned Qwen worker，包含legacy模式；HTTP disconnect／parent stop、timeout、worker close／restart及過期輸出fence保持，單一renderer/audio owner不變。模型載入明確local-files-only／offline，沒有外部TTS、原音上傳或新key。

## 真實驗證

| 項目 | 實跑結果 | 界限 |
|---|---|---|
| 新台詞Base clone | 「今天也要開開心心喔！我會陪你一起完成。」3.68s／24kHz PCM16、peak0.3555、saturation0 | 新台詞主觀相似度／動漫感仍待真人，不把數值當MOS |
| cold與cache | cold18.848s；同句cache0.003s | cache不是新句推論或首音SLO |
| 真推論取消 | 0.093s；old worker reaped、owner cleared；取消後可重啟、最後close | 合成測試，不是100次真人barge-in |
| 真HTTP／原播放器／native | speech plan200→speech200 WAV→WebKit ended／全文朗讀完成，Pulse sink input觀察到，sandbox true、server與worker關閉 | 隔離合成台詞、真人聽感未替代 |
| 最終副本整合 | PASS，ready1.018s，Ollama短問候completed、Haru1canvas；tts route正確B | 合成DB，不讀私人對話 |
| 真模型停止 | 長文cancelled／0.076s／0工具，晚到文字不增加 | 不是TTS推論首音延遲量測 |
| 正式8000服務 | healthy、指定新副本唯一gjs；授權speech HTTP新句PASS，含載入12.44s、3.68s檔案、saturation0 | 未建立對話turn／未開mic／未自行播喇叭；worker留warm供使用者 |

原生播放probe的新模型cold等待預算獨立設為60秒，不冒稱通過首音SLO，也沒有放寬產品原5秒啟動gate。模型4B Ollama、Whisper、Haru及Origin／token／kill switches不變。

## 測試與失敗紀錄

新增profile測試先因類別尚未實作出現ImportError（有實跑RED），實作後14案通過；覆蓋profile嚴格輸入、正確reference_text／cache／owned lifecycle及缺件不fallback。選單既有案例加profile路徑含空白的真Gio保留斷言，不移除原secret／quoting斷言。來源相關初跑 **158 PASS／28.09s**，最終profile／選單 **53 PASS／10.27s**，與後續副本有重疊不加總。

最終副本 `80c1ebe93ae2` locked sync／compileall／Cargo build exit0；372份非文件來源與manifest再核對一致。最終相關 **431 PASS／1既有Starlette warning／26.54s／exit0**，包含原未改5秒gate、Qwen lifecycle／worker completion、provider／gateway／桌面／mic／停止回歸。Ruff check／format／mypy五個受影響Python檔案均PASS；初次Ruff指出新fixture中文標點，修正合成fixture後通過。未跑全scripts/check／remoteCI。

初輪副本 **426 PASS／5 FAIL**：舊import-boundary subprocess故意清空環境、要求stderr乾淨；uv先前在external PYTHONPYCACHEPREFIX預編譯dependency，所以該subprocess首次現場編譯Jieba，輸出原有SyntaxWarnings。保留完整fail log及warning，在同venv正常canonical site-packages執行compileall後，再跑原431項通過。沒有改第三方source、warning filter、test stderr要求或skip。完整修復命令／輸出包含在RESULTS。

日常入口第一次檢查早於新服務ready，得到ConnectionRefused；之後正常ready／route／unique gjs檢查PASS。這次早檢查沒有列為成功，也沒有因此放寬原啟動gate。

## 部署、資料與重現

先以SQLite backup API及私有設定一致備份至Ubuntu私有目錄，僅將metadata寫證據，不讀／匯出私人對話。只正常TERM指定舊source的唯一gjs；切換時原backend PID檔已不存在，沒有廣泛kill同名程序。更新本機wrapper／選單選定profile，再從Windows入口啟動。實際PID及source完整ID見RESULTS；native留給使用者操作，語音worker經正式合成檢查後留warm。

本機保留的ignored驗收腳本與完整pytest argv見RESULTS，可攜回歸位於新 `test_selected_voice_profile.py`、既有Qwen lifecycle／worker completion／speech與桌面入口測試。

```powershell
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/prepare_selected_voice.py
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/stage_selected_voice.py
wsl -d Ubuntu -- env OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/verify_selected_voice.py
wsl -d Ubuntu -- env OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/selected-voice-playback-probe.py
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/refresh_ext4.py
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/prepare_canonical_bytecode.py
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/check_ext4.py
wsl -d Ubuntu -- env SIRO_OLLAMA_MODEL=qwen3:4b-instruct bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/verify_selected_integrated.py
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/check_selected_live_voice.py
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/check_final_entry.py
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/publish_selected_voice.py
git diff --check
```

模型／原生整合需先正常關閉正式native視窗，避免同DBus application ID互相接管；正式8000檢查在日常入口啟動後執行。驗收後文件更新不冒稱副本內STATUS已更新。新台詞clone品質／真設備破音、首音SLO、長時間負載、全CI、其他硬體及正式發布仍未驗；沒有commit／push。
