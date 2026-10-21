# MEM-GATE-IMPORT 驗收與交接

2026-10-22 Asia/Taipei。此卡修復上一輪記憶整合唯一的 selected-v3 失敗，
不把選定回歸通過當成整體產品、T18／T30 或正式發布完成。
工作分支 `codex/memory-runtime-integration-20261022`，base
`20157b9d9512c24cd2a2c51fc37c74471b7d4ba6`；未納入 main 後續 desktop 工作。

## 修改與因果證據

Gateway 匯入 TTS 時會先載入 numpy、soundfile、misaki／jieba，早於資料占用檢查。
三套件只在 Kokoro 語音產生路徑需要，現在延到原 `asyncio.to_thread` 的 render worker。
數值算法、模型／G2P／voice 快取、輸出、例外與取消語義維持原樣，沒有改 Gateway、
ownership、timeout、schema 或依賴。首次語音仍須支付載入成本；沒有量測真語音品質。

新增 import 攔截負例，修改實作前：3 failed / 1 passed / 4 deselected，23.78s。
numpy、soundfile、misaki 三組證實 busy 路徑會碰到不需要的套件；原 Kokoro 組通過。
修復後整份 TTS 邊界：8 passed，27.21s，包含合成 WAV、重複 render 快取、
G2P 載入執行緒、SDK 例外型別、取消後 worker 可結束。模型與 G2P 為合成 stub；
不冒稱真模型／音訊／硬體驗收。

相同環境各一次 `python -X importtime` 的 Gateway 模組匯入：前6.763929s、後4.635719s。
這只是兩個單次觀測，非冷啟動 p95、SLO，亦不能解釋所有歷史啟動失敗。
解除本卡 gate 的依據是下列未改的五秒真子程序測試通過，而非這兩筆較短量測。

## 重現與結果

使用 task 專用 WSL ext4 venv／target，沿用既有快取，未安裝或下載依賴／模型。
從本工作區的 `.venv/bin/python` 啟動，確保 trusted skill sandbox 可見執行檔。
命令前綴：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src`。

```text
.venv/bin/python -m pytest -q -p no:cacheprovider tests/integration/test_tts_import_boundary.py
.venv/bin/ruff format --check src/siro/services/audio/tts.py tests/integration/test_tts_import_boundary.py
.venv/bin/ruff check src/siro/services/audio/tts.py tests/integration/test_tts_import_boundary.py
.venv/bin/mypy src/siro/services/audio/tts.py tests/integration/test_tts_import_boundary.py --cache-dir /tmp/siro-mem-gate-mypy-20261022
.venv/bin/python scripts/run_acceptance.py <final-receipt.json 的全部 targets> --output <工作區外新目錄> --level L1 --git-executable git.exe
```

Ruff格式／lint、兩檔 mypy與 `git diff --check` 均通過。
最終 selected 回歸是上一輪全部 targets 加 `tests/test_audio_pipeline.py`，
1263 passed / 0 failed / 0 errors / 0 skipped，5 warnings，pytest 311.19s，harness 315.837s。
原 `test_actual_gateway_process_blocks_competitors_until_shutdown` 的 `timeout=5` 未改；
它在此次整批回歸通過，未靠重跑挑綠或延長限制。
含真隔離 Gateway 子程序／合成SQLite資料，以及 mocked provider、工具與技能 worker 測試。
宣告 L1 不是 harness 核實的硬體／服務證據等級；詳見 receipt 的 limitations。

測試期間未編輯原始碼／文件，source_before == source_after；content SHA256：
`0c93df96cb48899c1052478f8844dbcb10f453905ccd4a49fd937f6941c88af2`。
測後只增補本報告、receipt與交接卡；未再更改 Python。
原始 logs 與前後 importtime 留在工作區外
`E:/coding/Worktrees/memory-runtime-integration/MEM-GATE-*-20261022*`，
此處只留無私密原始輸出的 receipt與摘要。

## 尚待整合

上一輪完整套件2949 pass／48 fail／19 skip及全域 lint/type問題仍保留歷史紀錄；
本輪未重跑完整全套，不能宣稱 `scripts/check` 或最新版 main 已通過。
共享 STATUS／DECISIONS／roadmap 由整合 owner接收，本卡不覆寫。

下一步依 `docs/memory-evolution/RT-HERMES-INTEGRATION.md`，序列整合最新 main，
先處理 MEM-02 理解品質（既有25/30仍未達27/30）與正式裝配，
再接 MEM-03 真 Auth／Policy／審閱／清除；背景保存、主動提醒與 T30 成功 trace feed
仍未完成。本輪沒有私人 DB、服務、模型設定或 Gateway／UI 產品碼變動。
回退僅撤本卡 import 調整；不需要資料回退。LOCAL_ONLY / NOT PUSHED / 未PR／合併／部署。
