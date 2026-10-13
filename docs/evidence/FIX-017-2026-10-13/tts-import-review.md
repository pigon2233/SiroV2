# FIX-017 — local import-boundary repair verification

2026-10-13（Asia/Taipei）。D54／FIX-017 card 與 source baseline 先落盤，之後先寫五個 fresh-process contract cases、捕捉 RED，再修指定 TTS leaf。此報告不代替完整 gate、rollback 或 exact-head cloud verification。

## Confirmed cause and classification

Actual cloud owner-contender 原先 exit1 且帶正確 Busy 訊息，但額外 ONNX hardware discovery diagnostic。實際 call path 為 `presentation/__init__.py:3` → `gateway.py:43` → module-top `audio/tts.py:22` → 公開已安裝 `kokoro_onnx.__init__` 的 `import onnxruntime`。Gateway main 到 owner acquisition 時，SDK import 已發生。

獨立 controlled fresh-process probe 使用 import guard 在 `kokoro_onnx` 入口拒絕，以免載入實際 ONNX／hardware／model。結果 `requested_provider_imports=["kokoro_onnx"]`、`owner_acquisition_calls=[]`；壞掉的 SDK 可完全繞過固定 Busy 回應。違反原 D50「在任何 provider/composition/SQLite 初始化前取得 owner」，是 `REQUIRED_FIX/MEDIUM`，`IMPLEMENTATION_BUG/MISSING_INTEGRATION/TEST_GAP`，不是純 stderr fixture 脆弱。

src/tests/scripts 沒有 `tts.Kokoro`、`tts.zh` monkeypatch 或直接引用 Kokoro alias 的 caller；Gateway 維持既有 `KokoroLocalTTS` API。沒有修改 caller、Gateway、owner 或原 tests。

## Minimal source change

只在 `src/siro/services/audio/tts.py` 將 annotation 的 Kokoro import 移到 TYPE_CHECKING；runtime import 移到原 `_render_sync` 的 model-is-None 分支。原 `render` 已透過 `asyncio.to_thread` 呼叫此方法。

模型／voice 路徑、voice weights、G2P、Kokoro constructor/create 參數、rate clamp、音量計算、WAV 產生、cache、exceptions、cancellation body 逐字保留。沒有 SDK factory、fallback、global loader、warning/loglevel 設定、依賴變動或新 provider API。

## Verification

新增 `tests/integration/test_tts_import_boundary.py` 五個 cases，均在全新 child interpreter 觀察，避免 test session module cache 遮住 eager import：

1. Busy main 在 controlled broken-SDK guard 下仍只到 owner rejection；零 Kokoro／ONNX import，保持固定 SystemExit 訊息。
2. Pure speech plan 和 Kokoro constructor 都不載入 optional SDK。
3. 首次 render 才在 worker thread 載入 synthetic SDK；兩次 render 保持一次 constructor、voice cache、原 create args、speed clamp、RIFF output。
4. SDK 失敗保留原 synthetic exception type/message，且出現在 render 而非 module import／constructor；零自動 fallback。
5. Cancelled render 保留原 task CancelledError semantics；受控 blocking worker 經 release 後完成，asyncio.run executor join 回收。**沒有宣稱 cancellation 硬中止第三方 native inference。**

Before 原 source 五個 cases **5 FAIL / 3.39s**（`tts-import-before.log`）；after 首次 **5 PASS / 4.13s**（`tts-import-after.log`）。只修 new test 一處行長格式後，以 final source＋final test 重跑五個 cases與 audio pipeline、speech plan/completion、既有 actual Gateway owner-contender integration：**34 PASS / 2 existing pypinyin deprecation warnings / 7.71s**（`tts-focused-final.log`）。原 owner test、timeout、stderr equality、readback/shutdown assertions 未改。

Final two-file Ruff format/lint、strict mypy、diff whitespace checks 都 exit0。沒有啟動 real voice provider／GPU／model、操作私人資料、或碰 live8026；positive SDK、G2P、取消 timing 是 controlled synthetic，Gateway HTTP/ownership case 是原 real synthetic process integration。

## Frozen scope

- 原 TTS SHA256：`26fea6450524a3e9dd26371f01d7ffa8d13b85255061a90d67e960b1715ec6e6`（root D54 baseline）。
- Final TTS SHA256：`f77457a7066960b8d7a2f42bdff99453a4201d91ebb37095f2c3eb59b1a29dc3`。
- Final new test SHA256：`33d9fc2ff784e246a04866dbd37b20c97f57ed44eedd5a626919d7be15e8267a`。

Root 接手完整 regression、精確 source-only rollback、doc/register status、commit/push與新的 cloud head gate。本 reviewer 不把 focused PASS 或原 cloud failed run 當完整 CI PASS。
