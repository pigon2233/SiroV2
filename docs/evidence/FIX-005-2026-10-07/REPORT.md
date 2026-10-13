# FIX-005 — 有界朗讀驗收紀錄（2026-10-08最後驗收）

2026-10-07 開始、2026-10-08 續作；Asia/Taipei。基準 commit `c1d2d41b2afc8844ff46f328043f7d2e8bf3cabe`，有未提交變更。**Status：PARTIAL / IN_PROGRESS，不能標 DONE。** A 完成判定／版本快取、B final 後分句播放已有合成與真機功能證據；速度驗收不合格，真人首尾與語意聽驗尚未執行。

最終 CUDA SDPA source 的合成回歸與精確 source 回退已補驗，hash 見 [rollback.json](rollback.json)。**最後版本真GPU／native browser功能重驗已PASS；速度與人工語意門檻未解除**。最後結果與早期eager baseline／中斷SDPA probe分開。原始失敗、baseline 與中斷 JSON 均保留。

## 已完成的局部修復

A：Qwen 以 optional `completion_protocol: 2` 宣告完成資訊。新版成功必須有正常 EOS、未達上限、有效 token 數、單次 observer，以及非空音訊；無法確認時不回成功音訊、不寫成功快取。只在 owned talker instance 觀察原 generate 結果、原樣交回 SDK，finally 還原；不修改 site-packages。既有未宣告 protocol 的 injected worker 保留相容，明示無效 protocol 不得降級。

`completion-v2` 快取獨立於舊 WAV namespace，綁模型檔案、reference 聲線、library／生成設定、分段版本及實際 attention profile。完整 metadata、WAV 與雜湊通過才命中，單檔原子提交。舊快取保留，不當作未驗證的 fallback。CUDA 採已量測 SDPA、CPU 保留 eager；不同 attention 不互讀快取。

B：新增同 Origin／Bearer 的 `POST /v1/audio/speech/plan`，重用既有朗讀準備與 segmenter，不執行推論。每段最多 80 字、最多 128 段／8,000 可朗讀字／1,200 秒；超額明示拒絕，不暗中截尾。前端保留 canonical 文字與 code-block 規則，依序播放、最多預取一段，實際末段 ended 後才顯示全文完成；可停止、重聽，失敗顯示全文未完成。保留單一 generation／controller、取消與舊結果 fence、原聲線與既有單次 speech API。

C 未實作：目前先等 final 文字，沒有已提交 final-answer 句子契約，不能宣稱逐音塊串流、模型生成同時說話或提前朗讀未提交內容。沒有改 Core／Identity／Memory／工具授權、DB schema、模型、reference 素材或增加第二個音訊 owner。

## 修前反例與合成回歸

以下 FAIL 是 expected-behavior 測試對缺陷的反例；PASS 是修後結果。fixture 與資料均為合成，不能代替原聲線／實體喇叭聽驗。

| 證據 | 結果與意義 |
|---|---|
| [before-plan.log](before-plan.log) | 9 FAIL；產品原先沒有有界 plan 路由、長文完整覆蓋與明示拒絕 |
| [before-adapter.log](before-adapter.log) | 16 FAIL／2 PASS／14 deselected；新版缺失、觸頂、未知等 completion 不能當成功音訊 |
| [before-worker.log](before-worker.log) | 23 FAIL／1 PASS；EOS、完整性、版本隔離／原子快取與 observer 還原反例 |
| [queue-red.log](queue-red.log) | 2 FAIL；原 caller 尚無 plan／順序播放路徑 |
| [before-completion-edges.log](before-completion-edges.log) | 6 FAIL；分段空白遺失及明示 null protocol 繞過新版驗證 |
| [before-malformed-completion.log](before-malformed-completion.log) | 4 FAIL／1 PASS；完整 metadata 仍不能把空音訊或帶 error 的回應變成功 |
| [before-empty-worker-audio.log](before-empty-worker-audio.log)、[before-empty-cache-audio.log](before-empty-cache-audio.log) | 各 1 FAIL；正常 EOS 仍可能解碼零 samples，44-byte 空 WAV 不能成功快取／重用 |
| [completion-final.log](completion-final.log) | SDPA 調整前 92 PASS／2 warnings，8.24 秒；保留歷史結果 |
| [completion-final-sdpa.log](completion-final-sdpa.log) | 最後 source 94 PASS／2 warnings，10.14 秒；plan、worker、adapter、completion 邊界、原 owned lifecycle，以及 CUDA SDPA／CPU eager 與實際 attention 快取隔離 |
| [frontend-final.log](frontend-final.log) | 93 PASS，7.12 秒；順序／進度／完整覆蓋、資源限制、取消／失敗／晚到、session／control 回歸 |
| [full-suite-final.log](full-suite-final.log) | 最後 source 整體 671 PASS／5 real_provider deselected／3 warnings，113.00 秒；未選取不算通過 |
| [full-suite-resume.log](full-suite-resume.log) | SDPA 調整前 669 PASS／5 real_provider deselected／3 warnings，124.59 秒；保留歷史結果 |
| [full-suite.log](full-suite.log)、[interrupted-cases-rerun.log](interrupted-cases-rerun.log) | 首輪被中斷，沒有完整通過結論；受中斷的一個 main 與兩個 memory cases 另跑 3 PASS，4.67 秒，再由完整 suite 覆蓋 |
| [lint.log](lint.log) | 先前 Ruff PASS、265 files 格式 PASS、mypy 114 source files PASS；保留原範圍 |

[final-lint.log](final-lint.log)：最後Ruff check PASS、265 files格式PASS、mypy 203 files（src與tests）PASS，三個命令均exit0。舊lint.log的114 files範圍保留作歷史。

回歸使用專案 Python 3.14 與 Node 合成 harness；實際 GPU 推論在獨立 Qwen Python 環境。沒有把合成 Audio／WAV 或 mocked SDK 寫成真聲線成功。

## 真 Qwen 與原生瀏覽器：eager baseline 功能通過、速度未通過

重現程式：[verify_real_voice.py](verify_real_voice.py)。原始安全結果：[real-voice-baseline.json](real-voice-baseline.json)。`--run-real` 使用原模型／reference 聲線、本機 CUDA:0、獨立 temporary cache 與 ephemeral Uvicorn，actual index.html、Chromium native Audio；子程序 `HF_HUB_OFFLINE=1`／`TRANSFORMERS_OFFLINE=1`。沒有 ASR、雲端音訊外送或私人對話重播。

硬體為 NVIDIA GeForce RTX 3050 Laptop GPU，probe ready 記錄 `cuda:0`。後續 [benchmark-inference-results.json](benchmark-inference-results.json) 實際記錄 qwen-tts 0.1.1、Torch 2.12.0+cu130、Transformers 4.57.3、SoundFile 0.14.0，使用 eager attention／bfloat16／non_streaming_mode、max_new_tokens 512；沒有升級 SDK、換聲線或模型。JSON 未附獨立 Qwen Python patch-version 輸出，不能把此欄推定已驗。

以下僅是 eager baseline 的功能結果，不是最後 SDPA source 的結果：157 字合成故事切成 56／60／41 字三段，保留末句「故事到這裡，平安結束了。」。三段各回正常 EOS（160／185／111 tokens，均低於 512），逐段產生真正 WAV。native playing／ended 依序完成，第一段開始時僅一段已生成，最多一段預取；末段 ended 後才顯示 3/3 全文完成。這證明生成終止與播放 lifecycle，**不能證明人耳聽到正確首尾、語意完整或聲音自然**；`human_listening: NOT_RUN`。

| baseline 測量 | 實際結果 | 測量邊界 |
|---|---|---|
| 22 字 cold short | 31.195 秒，音訊 5.44 秒，RTF 5.734 | 含 worker 初始化與載入，不能當暖生成 |
| 同句 cache hit | 0.003664 秒 | 獨立命中樣本，不混作暖推論效能 |
| 故事第 1 段 warm／uncached | 30.337 秒，音訊 12.72 秒，RTF 2.385 | 模型已載入，非快取 |
| 故事第 2 段 warm／uncached | 36.196 秒，音訊 14.72 秒，RTF 2.459 | 模型已載入，非快取 |
| 故事第 3 段 warm／uncached | 21.221 秒，音訊 8.8 秒，RTF 2.411 | 模型已載入，非快取 |
| 首段開始播放 | 等待 30.472 秒 | 合成 completed terminal 至 native playing |
| 段間等待 | 23.289 秒、6.387 秒 | 前段 ended 至後段 playing |

**速度 FAIL。** 暖生成仍慢於實際播放速度（RTF 約 2.4），一段預取無法遮住等待；首段明顯未達既有 ≤1 秒體驗目標。樣本為一個 cold、一次 cache hit、三個暖非快取段；不是 p95／p99 或長期 SLO。未降低門檻，不將有序播完稱作流暢。後續只針對已量測推論瓶頸做局部 benchmark／修復，保留原聲線、完整性、單 owner 與有界隊列。

取消功能 PASS：確認 fresh job 正在 owned Qwen exchange 等待後取消 HTTP／斷線，worker 在 close 前被 reap（return code -9），沒有回音訊、沒有新 native Audio，清理後另觀察 1 秒。這不是實體喇叭 p95 停音量測。browser、body、control、server、listener、render、owned process、temporary tokens／cache 均清理後才記錄 probe PASS，JS errors 0。JSON 的 PASS 僅代表這些功能檢查，不解除速度與人工驗收 gate。

## CPU thread 診斷：REJECT 設定變更

[benchmark_inference.py](benchmark_inference.py) 與 [benchmark-inference-results.json](benchmark-inference-results.json) 比較同一已載入模型的 thread 數；固定合成 22 字短句與 seed 20261008，不呼叫 cache API，8／1／4 threads 各先 warmup 一次、正式量測兩次，interop threads 維持 16。每次均正常 EOS、63 tokens、4.96 秒音訊，所有 9 次的 audio SHA256 相同；因此沒有把字數／隨機生成長度差異當效能收益。

| CPU threads | 正式生成時間範圍 | RTF 範圍 |
|---|---|---|
| 原設定 8 | 12.655–12.891 秒 | 2.551–2.599 |
| 候選 1 | 12.655–12.732 秒 | 2.551–2.567 |
| 候選 4 | 12.567–12.758 秒 | 2.534–2.572 |

**REJECT thread 設定變更。** 各組時間重疊，RTF 仍約 2.53–2.60，沒有解決慢於播放的問題；每組僅兩次正式樣本，不宣稱微小差異具統計意義。生成時間主要在 talker（約 12.29–12.62 秒），其外約 0.25–0.27 秒。沒有改 production thread 數或為此新增設定／抽象。這份 JSON 的 PASS 是診斷成功，不是速度門檻通過。

診斷只比較 warm generation，沒有桌面 native playback、真人聽驗或 p95 統計。當時 worker SHA256 為 `7fef382492daad2d70a81c5417dca3b4e02cbdee644c19f7055ff3a3eb82aaa8`，模型／voice references 已釋放，程序退出回收 CUDA context。這是後續 SDPA 修正前的受控診斷，不是最終 production worker 的驗收 hash。

## CUDA SDPA 局部診斷：採用設定、速度仍未達標

[benchmark-sdpa-results.json](benchmark-sdpa-results.json) 使用同一 22 字合成句、seed 20261008、原 model／reference、library、bfloat16、512 上限與不使用 cache 的量測方式；先 warmup 一次，再正式量測兩次。實際 model／talker／code predictor／speech tokenizer 四層均確認為 `sdpa`。沒有新依賴、換 backend／聲線或提升生成上限。

| profile | 正式生成時間 | 正常 EOS／音訊 |
|---|---|---|
| eager／原 8 threads | 12.891／12.655 秒 | 63 tokens，4.96 秒音訊 |
| SDPA／原 8 threads | 8.158／8.133 秒 | 59 tokens，4.64 秒音訊；RTF 1.758／1.753 |

**採用 CUDA SDPA；CPU 保留 eager。** 有觀察到較短生成時間，仍慢於播放速度且不達 1 秒首音目標。SDPA 的數值計算差異使 token 數、音訊時長及 audio SHA256 改變；相同 seed 不能據此宣稱內容逐位元相同、語意已聽驗或聲線自然度不變。SDPA 正式樣本的 audio SHA256 為 `17605893fdcce93db0c0d88ca96ada2de00c20aa0ed77b1669c0434ef3952f4e`。各 profile 僅兩個正式暖樣本，不是 p95／p99 或全篇瀏覽器效能驗收；JSON PASS 代表診斷完成與 EOS 正常，不是產品速度通過。

production 的實際 attention 選擇同時進入 cache fingerprint；最後合成測試驗 CUDA／CPU 分支與 profile 隔離，source 精確回退已重跑。對應 [D35](../../DECISIONS.md) 的局部修正，沒有擴張 Core 或音訊所有權。SDPA benchmark 在原 Gateway drain、一致備份後隔離執行，finally 恢復服務 health／authenticated plan 通過，見 [sdpa-benchmark-service-restore.json](sdpa-benchmark-service-restore.json)。

## 最後 source 真 GPU／瀏覽器重驗：功能 PASS、體驗 PARTIAL

[real-voice-sdpa-interrupted.json](real-voice-sdpa-interrupted.json) 是被中斷的前次 SDPA probe，只有部分段落結果；**不是 PASS，不算三段全文／最後取消／cleanup 完成**。中斷後已用 native launcher 恢復原服務，health PASS，未匯出私人環境，見 [interruption-recovery.json](interruption-recovery.json)。

最後重驗 **功能 PASS，速度仍未達標**。安全結果：[real-voice-final.json](real-voice-final.json)；本機恢復：[final-local-service-restore.json](final-local-service-restore.json)。同一原模型／reference，CUDA SDPA、完整實際index及native Chromium Audio；157字故事3段，末句仍在canonical plan。起訖四production SHA全相同，worker hash亦與最後rollback相同。每段正常EOS／未達512上限；此輪三段160／165／122tokens。首段開播時只生成1/3段、最多一段預取，順序playing／ended，最後ended才3/3完成，JS errors0。

| 最後SDPA真機測量 | 實際結果 |
|---|---|
| cold短句（含載入） | 24.582s，audio 5.68s |
| 同句cache hit（不作暖生成） | 0.005001s |
| 故事第1段warm uncached | 22.327s，audio 12.72s，RTF 1.755 |
| 故事第2段warm uncached | 22.927s，audio 13.12s，RTF 1.748 |
| 故事第3段warm uncached | 16.945s，audio 9.68s，RTF 1.750 |
| completed terminal→首段native playing | 22.446s（eager示例30.472s） |
| 段間等待 | 10.053s／3.719s（eager示例23.289／6.387s） |

這是兩次示例的觀測比較，非等長／bitwise輸出的嚴格效能統計；前述固定seed診斷另保留。首段與間隙已下降，但warm RTF仍約1.75，無法用單段預取遮住等待；不能宣稱1秒SLO、無縫或高品質語音完成。樣本量不足以宣稱p95／p99。

fresh未快取的生成請求確認正在worker等回應後取消，worker close前reap（-9）、無回音訊或新Audio；後續觀察1秒。browser／body／control／server／listener／render／owned process／tokens／temporary cache全部清理後才PASS。supervisor也已恢復8026，health與authenticated plan PASS；未修改／還原private DB或原reference，舊快取保留。末段生成音檔留在ignored本機資料供聽驗，**human_listening: NOT_RUN**，尚未證真人聽到完整首尾／自然聲線；卡片保持PARTIAL。

## 隔離 source 回退與本機服務恢復

[verify_rollback.py](verify_rollback.py) 的 allowlist 副本不帶原 `.siro-data`、DB、`.env`、模型或私人 WAV。最後 SDPA source 的 7 個 before-source 原檔與 4 個新增測試精確 reverse／reapply；FIX-003／004 共 12 個 baseline hashes 全吻合。回退後 [164 PASS](rollback-pre005.log)，13.34 秒；重套後 [281 PASS](rollback-reapplied005.log)，18.17 秒。socket fixtures 本次可執行，未因權限跳過。來源前後 hashes 不變，temporary 副本已清理；[rollback.json](rollback.json) 及 [source.patch](source.patch) 保留。

最後 source patch SHA256：`f3ae57f230c7a9b7c806179dcfd99be94dbf05c3d4f7bd2eea2cb05f4b4382c5`；worker SHA256：`70941acaaf16906aaa8852e4eb13e099e66c348ca8cd0df95daad0ce43d4d12c`，其餘 production／tests hashes 見 `rollback.json`。**這是包含 SDPA 修正的隔離 source 相容回退，不是 deployed-service／GPU 回退成功證據。** 實際回退需停止播放、取消／reap 預取、drain 後只撤本卡；保留 DB、journal、原聲線、舊／新版 cache，以及 FIX-003／004。必要時退為明示長文限制的短句 API，不把已知舊缺陷當安全完整語音版本。

[local-service-restore.json](local-service-restore.json) 記錄真機測試前 active turn 已 completed，一致備份至 `.siro-data/backups/pre-fix005-20261008-094821/siro.db`，graceful pause 原 Gateway 並確認原 worker 停止；finally 恢復本機 8026，health 與 authenticated plan 通過。沒有把環境密鑰存到證據或磁碟，沒有匯出私人 DB 內容；reference 只由本機 worker 依原用途使用，未修改、拷貝到證據或外送。原快取與使用者既有未追蹤 WAV 保留。

8026 已恢復載入本次 candidate source，屬本機驗收服務更新，不等同全產品發布或所有 promotion gates 解除。沒有執行 DB 還原、migration 降版或生產資料回退演練。

第二輪 thread 診斷亦完成 drain／一致備份／finally restore；[thread-benchmark-service-restore.json](thread-benchmark-service-restore.json) 記錄無 active turns、獨立備份 `.siro-data/backups/pre-fix005-20261008-095333/siro.db`，probe exit 0，恢復後 health／authenticated plan 通過；沒有匯出私人內容或保存環境密鑰。

## 尚未完成與下一個驗收動作

CPU thread benchmark 已否決該變更；CUDA SDPA 有局部效益而採用，最後合成回歸與 source 回退已通過。最後真Qwen的cold／warm miss／cache hit、native first play／段間隔、取消、完整性與cleanup／服務恢復已收齊，以上以完整最後probe為準，未沿用中斷結果。下一個窄步驟是驗證現有SDK／tokenizer有沒有可安全取消且正常提交completion的音訊chunk介面，針對已量測talker瓶頸做實證；沒有受支持介面前不侵入Core、不把non_streaming旗標當串流成果。另需對本次合成首尾作真人聽驗。正常 EOS 不代替首尾人工聽驗；速度目標、全套性能統計、實體聽覺取消、長 soak／遠端 CI／跨平台驗收仍未完成。

FIX-005 保持 PARTIAL / IN_PROGRESS。C 未實作；FIX-002 搜尋、FIX-006 理解、自由活動桌寵與自主技能未被本卡驗收解除，也沒有因此重做原 RT 成果或改 roadmap 編號。
