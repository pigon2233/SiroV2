# D52 真 signed source／HTTP 驗收

2026-10-13（Asia/Taipei）。本 agent 只新增 `tests/integration/test_release_source_process.py` 與本目录 `process-*`；沒有改 production source，沒有啟停 live 8026、讀私人 DB／chat／key／config／models 或正式部署。

## 有效範圍與結果

新增 **3 cases PASS／6.40s**；實際啟動 **5 個自有程序**：3 個真 Gateway lifecycle（來源 1.0.0 → 2.0.0 → code rollback 1.0.0），2 個真拒絕啟動的負向程序。Ruff lint／format、owned-file mypy 全部 PASS。這是 **Linux、既有相同 schema、精確完整 signed source 接入**，不等於整體 release/handoff 或產品使用體驗完成。

fixture 複製目前完整 `src`，排除所有 `__pycache__`／`.pyc`，建立兩份 distinct signed bundle。只有 clone Gateway 加入 test-only account locator、實際 `__file__`／fixture version／signing-key-presence boolean observation wrapper；wrapper 最後呼叫同份 clone 的原 `main`，不替代 IO、startup、HTTP 或 shutdown 結果。這些 instrumentation 都納入完整 source digest／manifest HMAC。來源校驗與運行入口是 root 的真 D52 implementation。

copied launcher 放在自己的 temp project，該 project 沒有 `.env.local`。所有 `SIRO_*` inherited env 先移除，再注入公開合成設定；Ollama model 名稱是未呼叫的 synthetic local profile，native budget／workspace／browser session／memory ingress／memory organizer／summary／retry 都明確停用。assets 是明確準備好的 synthetic public placeholder；沒有執行 Rust binary、render Live2D、送 chat 或呼叫 provider/TTS/GPU。

## 真實觀察

每次 Gateway start 前先確認整份 selected package 的 digest 等於 exact manifest；Gateway 由 copied launcher 的真正 `os.execve` 路徑執行，fresh `-I -B` Python 的 module origins 實際是：

- `manager/releases/<version>/src/siro/__init__.py`
- `manager/releases/<version>/src/siro/core/releases.py`
- `manager/releases/<version>/src/siro/services/presentation/gateway.py`

wrapper 記錄的三項 `__file__` 都與該版 selected path 完全一致。只記 signing-key 是否存在，**三次皆 false**；沒有讀取或記錄 key value。

真 loopback HTTP `/health/ready` 三次回報 `state=healthy`，且 version／source SHA 與 exact selected manifest 相符。三個 port 都由 OS ephemeral bind 選取並拒絕 8026；fixture 在啟動時不接任何既有服務的 port。來源的 Gateway `main` 沿 D50 context 執行，所有正常子程序都先 TERM，再 `wait` joined，log 有實際 `Application shutdown complete.`，沒有 Traceback／destroyed-pending-task。**三個正常 child 的退出碼是 -15，不是 0**；這與 Uvicorn 完成 drain 後重拋原 SIGTERM 相符。

每次 start／finish，root source3＋owned test file SHA 不變；整份 selected package 的 before/after digest 不變，沒有 `__pycache__`／`.pyc` 出現在 package。精確每次 digest、runtime relative `__file__`、ready response、退出碼、join、source hashes 保留於 `process-final.json`。

資料 fixture 先用實際 `SQLiteStore.initialize` 跑既有 **13** migrations。已驗表是實際 `conversations/turns/messages`、`memories`、`actions(state=completed)`，外加 synthetic custom table。每個晚寫只在先前 child **真正 joined 之後**才加入，再切下一版；code rollback 只切版本，沒有 restore 舊 backup。回退前後以及 rollback source 真啟動後，三批合成 conversation、memory、completed action ledger、custom markers 全部保持。這是存量資料保留驗收，不是模型理解或 Memory provenance 產品驗收。

兩項負向都是 actual child、exit 1、joined、temporary root 已清除：

| 情境 | 真觀察 | 不允許的替代 |
|---|---|---|
| 合法簽署，但 selected `VerifiedRelease` DTO ABI 故意不相容 | fresh selected import 後 TypeError，未呼叫 Gateway main、沒有 HTTP server；DB bytes／已保存 rows 完全不變，package 無 bytecode cache | 不可悄悄改用 host ABI／host Gateway |
| manifest 簽署後 tamper selected package | parent resolve 拒 `invalid_release_target`；故意的 tampered import marker沒有執行；沒有 HTTP server，DB bytes／rows 完全不變 | 不可忽略 hash mismatch 或降級為 legacy host 啟動 |

所有 temp root 在 PASS output **之前**明確清除；沒有 DB binary、key、錄音或私人內容写入 repo。

## Freeze 與歷史 RED

Final owned test SHA-256：`1d17acf98cc037b54bc12679ef668caf9bc32ab5db007bab7252f95cf3836c51`。實際驗收完已告知 root 凍結，不再改語意／format；root 可用這份 file 做完整回歸與 source-only exact rollback。

這張 actual supplement 的初版錯誤屬 fixture，沒有 confirmed production defect：

- `process-first.log`：1 FAIL／2 PASS，instrumentation wrapper 漏 `json` import，NameError 發生在真 main 之前。補 fixture-only explicit import 後 `process-after-fixture-json.log` 3 PASS。
- `process-before-import-fix.log`：metadata 整理時誤移除 HMAC helper 的 `hashlib` import，3 FAIL；復原 fixture import，保留失敗 log，不冒充 production RED。
- `process-before-hash-freeze.log`：補 final 每次 start/finish hash assertion之前的 intermediate 3 PASS。
- **只有 `process-final.log`／`process-final.json` 是 final 3 PASS 證據**。結果 JSON 保留 corrections、精確 source3/test pre/post SHA、每次 selected digest 與 raw log SHA。

實際執行：

```bash
.venv/bin/pytest -q -s tests/integration/test_release_source_process.py
.venv/bin/ruff check tests/integration/test_release_source_process.py
.venv/bin/ruff format --check tests/integration/test_release_source_process.py
.venv/bin/mypy tests/integration/test_release_source_process.py
```

## 仍保留的 gates

本 probe 只知道自己 Popen 建立的 child，沒有證明未知／外部 SQLite writer 不存在。根據 `adoption-review.md`，新 flock／SQLite lock／ready 皆不能停 unmanaged old writer；真 first-adoption operator 停止證據、正式批准與跨 process handoff 仍是獨立前置條件。

本輪没有 adversarial filesystem TOCTOU 排除證據、不同 schema migration/handoff、任意舊 ABI 相容、power-loss、network-FS／其他 OS或正式部署。root 的 controlled DTO／schema/mutation tests 與這份 actual same-schema source proof 必須分別報告。synthetic HMAC 是本 fixture 的明確 trust key，不能推成正式 signing-key custody 或產品批准。

沒有 production diff 由本 agent 產生，沒有需要更正的 original single-owner architecture decision，沒有新增 registry／launcher manager／lock manager。回退僅移除新 test/evidence；不改 DB、stable owner state 或 root 的實作。
