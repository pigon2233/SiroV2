# T16 驗收證據

日期：2026-09-25｜結果：L1 PASS，speaker L3 PASS，headset NOT TESTED

speech onset 會清除 playback 並取消 player/TTS/LLM；generation fence 拒絕 cancel/reconnect 後遲到的 audio。100 次 completion/cancel 競爭與 reconnect 舊音不復活測試通過。STT/TTS/device faults 均保留文字模式。`docs/AUDIO_SUPPORT.md` 明列 headset、speaker、half-duplex 與 text 支援狀態。

A08 的至少 20 次真人打斷已在實體 speaker 模式完成。第二輪報告雖因下拉選單未調整而
記成 `headset`，owner 隨即確認實際輸出是喇叭；證據同時保存所選標籤與實際硬體更正。
實體 headset 尚未測試且不宣稱已驗；owner 決定不以此阻擋後續 task。

## 2026-09-25 speaker field run 1

Owner 以任意真人發聲執行 20 次（VAD 不要求關鍵字）。瀏覽器回報 speaker 模式下
`echoCancellation=true`、`noiseSuppression=true`、`autoGainControl=true`。原始 v1 報告的
`successful_interrupts` 曾錯把 missed 納入；逐筆修正後為 12 次有效成功、7 次 missed、1 次
人工標記 false positive；測試後 owner 回報另有多次未標記誤觸發，因此整輪無效且未通過
20 次門檻。原始裝置識別碼不進 Git；去識別摘要見
`field-report-2026-09-25-run1.json`。報告的 response time 包含人類反應時間，不視為 VAD onset
或 cancel latency SLO 證據。

第二輪 harness 對麥克風訊號使用 1 kHz high-pass，並在每次播放開始後先量測一秒回音
基線，以該次 p95 的 1.8 倍作動態門檻；只有畫面提示發聲後才接受 onset。

## 2026-09-25 speaker field run 2

Owner 使用任意真人發聲累積 20 次有效成功，0 次人工標記 false positive；瀏覽器回報
AEC、noise suppression、auto gain control 均啟用。報告選單誤留在 `headset`，實際硬體由
owner 確認為 speaker。另有 7 次 missed，經檢查為
前一 trial 的 timeout 可跨次誤判新 trial；此缺陷只能增加 missed，不能產生成功偵測，因此
20 次成功成立。harness 已以 trial ID 隔離 timer。去識別摘要見
`field-report-2026-09-25-run2.json`。實體 headset 仍待驗。
