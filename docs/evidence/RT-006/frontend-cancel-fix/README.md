# RT-006 frontend cancellation repair — 2026-10-01

## Verdict / corrections

RT-006維持 **PARTIAL**。原implementation report「Frontend取消fetch」是假前提：舊onclick只POST turn cancel，speech fetch無signal；terminal清currentTurn後還會播放。原README已更正，原独立REPORT/腳本/log保持歷史不修改。reference SHA/WAV通過不能替代人工音色相容性，沒有自行縮小acceptance。

## Changes / runtime path

只改presentation/static/index.html及新test_frontend_speech_cancel.py，另改roadmap/DECISIONS D18/STATUS/證據。每筆playTts使用AbortController和固定generation；stopTts同步abort request、pause播放器、清事件、revoke blob URL。取消onclick無論currentTurn存在與否先stopTts；若有turn仍保留原POST。新輸入/turn/speech也停舊speech。晚到fetch/blob/error/play promise不建立或復活舊audio、不覆寫新status。取消後遲到completed terminal不啟動speech；下一turn恢復可播放。

不改HTTP/backend/worker/config/state/音色/資產，不重設計global TTS broker。既有candidate HTTP disconnect→render cancellation/reap目前由實際button abort触發。legacy UI同樣有正確播放器取消，但legacy worker故障行為仍原有相容路徑。

## Automated verification

- `.venv/bin/pytest -q tests/integration/test_frontend_speech_cancel.py tests/integration/test_qwen_lifecycle.py tests/integration/test_gateway_terminal_fence.py`：25 passed，2.41s，exit0，task-final.log。
- frontend新增6 case直接擷取實際stopTts/playTts/onclick/onmessage，在Node執行；不是Python重寫：無currentTurn的pending fetch、有turn POST、late blob、新speech/late error、已開始play與晚到play promise、cancel後late terminal/下一turn。
- mock fetch/Audio僅為可控故障port；實際DOM/browser/GPU另驗。Node測試沒有硬體聽覺判斷。
- 全套最終257 passed/5 skipped，90.63s，exit0（真GPU人工頁面同時運行），見full-suite-final.log；ruff PASS、mypy171files PASS，见各log。5 skipped model/speech opt-in不算真providerPASS。
- repair.patch/source-digests保存本輪精確差異，reverse check通過；不是部署rollback。

## Actual browser / local GPU verification

本機原8000未運行；啟動隔離candidate Gateway：`.siro-data/rt006-manual-ui`獨立DB/cache，links只讀既有Qwen環境/model/reference，offline model、無key/外送，掛既有Cubism dist。PID存同目錄gateway.pid。留服務與browser供owner人工驗收，不把測試資料混入原.siro-data/siro.db。

在實際in-app browser以UI送出合成文字，確認「語音生成中…」，按既有取消按鈕後「TTS 待命」。server記錄speech client disconnected，原ASGI取消路徑触發。再送「請再測試聲音。」真Qwen生成/HTTP200，快取重播時實際狀態「SIRO 正在說話」，按取消後「TTS 待命」。無browser error/warn。由UI state只能證明播放器事件及停止接線，不能冒稱owner聽到聲音或聲線人工比對完成。

gui-cancel.jpg/gui-playback-cancel.jpg是取消後畫面；gui-character.jpg可見真Cubism角色畫面，非僅iframe mount。未確認真口型時鐘/完整gesture回歸；不以單張畫面代替完整人工畫面驗收。截圖只含合成文字與隔離snapshot，不含私有對話/key。

## Remaining acceptance

| Item | Status |
|---|---|
| UI pending speech request取消接線 | PASS（actual source Node + 實際UI狀態與ASGI斷線觀察） |
| UI播放cancel / late output fence | PASS（actual source Node + 真頁面播放器狀態） |
| 字符畫面可顯示 | PASS（真Cubism screenshot） |
| owner人工v1聲線/聽覺立即停止/畫面相容確認 | NOT VERIFIED；已請owner在已開啟頁面回報 |
| backend request/reap/single owner/格式 | 原獨立測試PASS，修後相關suite重新執行；本輪沒有改backend |
| deployment rollback / long GPU soak | NOT VERIFIED |

在人工作業收到結果前roadmap維持PARTIAL，未開始RT-007。

## Manual procedure

開 `http://127.0.0.1:8000/`，輸入「測試聲音」：
1. 聽一次，和原v1 reference聲線比較（reference路徑未改）。
2. 再播一次按「取消目前回覆」：確認耳朵聽到立刻停止，等待幾秒不自行復活。
3. 新送一次能正常播放；上方角色顯示與原表現相容。

請owner回報聲線正常/不同/聽不到，停止是否即時，以及畫面是否正常；記錄實際觀察後才能處理人工gate，不能從無回覆推定PASS。

## Rollback / service lifetime

先取消pending speech/停止播放，close candidate worker並停manual Gateway，再核對source-digests、reverse-check/reverse apply本輪repair.patch；只回退本輪UI/test，不動原RT006/backend或其他dirty工作。rollback後UI取消缺口恢復，仍PARTIAL。未部署回退。manual Gateway可依.siro-data/rt006-manual-ui/gateway.pid送TERM正常shutdown；不要掃描/廣泛kill使用者程序。
