# FIX-005 — 首段工作量縮短，2026-10-16

狀態：**CPU VERIFIED / GPU 與人工聽驗尚未執行；FIX-005 保持 PARTIAL**。

## 原因與最小變更

既有 planner 會將首句與後句併到80字，雖然已有單worker、有界分段及最多一段預取，首播仍需先生成很長的第一段。只把第一段獨立限制在24字，優先完整句、其次至少8字後的逗號等停頓或英文空格，其餘仍按原方式最多80字。canonical內容逐字保留，原先128段／8,000字／1,200秒、認證及唯一Audio owner不變。

plan與worker fingerprint的分段版本同步更新為`sentence-v2-first24-rest80`。保留原模型、`qwen3-siro-anime-daughter-v1.wav`、SDPA／eager選擇、512 codec cap、EOS完整性、原子cache與owned取消／reap；舊cache保留且不混讀。沒有新增warmup、自動預生成或第二GPU worker。

本機官方qwen-tts0.1.1的`inference/qwen3_tts_model.py:513`明說`non_streaming_mode=False`只模擬文字輸入，沒有真正streaming generation；沒有翻此旗標或改第三方SDK。這次仍等待final文字與第一段完整WAV，不能稱逐音塊串流。

## 執行證據

- [red-plan.log](red-plan.log)：新首段反例在修改前5 FAIL／9 PASS；並非測試尚未執行。
- [focused-final.log](focused-final.log)：148 PASS／2既有dependency warnings，7.48s，未skip。涵蓋authenticated plan、canonical完整覆蓋與尾句、句／逗號／英文／硬切、plan-worker版本相符、EOS／失敗與cache、worker request identity／取消／close／reap、前端預取與取消、既有audio pipeline。
- [lint-final.log](lint-final.log)：3個變更Python檔的Ruff check／format與mypy PASS。
- [plan-comparison.json](plan-comparison.json)：原157字合成故事首段56→16字，仍3段；4,760字合成長文首段76→19字，63→64段；8,000字無標點案例79→24字，仍102段。每例canonical文字與SHA一致。
- [rollback.json](rollback.json)及[source.patch](source.patch)：只在臨時隔離副本對本卡3個source/test檔做精確reverse／reapply，前後bytes相符；不是服務或GPU部署回滾。

重現CPU比較：

```bash
.venv/bin/python docs/evidence/FIX-005-first-segment-2026-10-16/verify_plans.py
.venv/bin/pytest -q tests/integration/test_speech_plan.py tests/integration/test_speech_completion_edges.py tests/test_qwen_worker_completion.py tests/integration/test_qwen_lifecycle.py tests/integration/test_frontend_speech_queue.py tests/integration/test_frontend_speech_cancel.py tests/test_audio_pipeline.py
```

## 下一個真機驗證入口（本報告時點未執行）

先由產品owner協調單GPU，確認現有Qwen worker已停止及reap；本subtask沒有操作8000或啟GPU。沿用既有真聲線／原生Chromium完整probe，指定新輸出目錄，避免覆寫歷史結果：

```bash
.venv/bin/python docs/evidence/FIX-005-2026-10-07/verify_real_voice.py --run-real --output /home/jasonliao/文件/Siro/SiroV2/.siro-data/verification/FIX-005-first24-2026-10-16 --timeout 1200
```

該probe分列cold載入、cache hit、故事warm未快取、native first playing／ended／段間隔、fresh取消與reap、source起訖hash。生成的聲音只留本機ignored目錄；測試使用合成文字，不讀私人聊天，不外送音訊。實際執行者須保存最後結果，不能把此命令當作已通過。

## 限制與回退

本輪只證明首段工作量減少，不證明延遲數字、自然度、首尾語意或1秒目標。冷載入時間與整體RTF沒有由此改進；較短首段可能使後續間隙更明顯。短句、強制無標點切分與分段語調仍需人耳驗收；額外獨立首段可能多出一段，總128段上限不放寬。

回退時先停止／取消正在播放與預取，等待owned worker退出，再只撤本卡[source.patch](source.patch)及D35的2026-10-16補充。保留原reference、DB、歷史與新舊cache；不能倒回其他並行工作或整個dirty tree。服務、GUI、真GPU與人耳驗收結果由主代理另行記錄；本報告不能放行FIX-005 DONE。
