# D61 — MQTT／model／SQLite／Rust 局部韌性修復

日期：2026-10-16（Asia/Taipei）。任務：FIX-022／023／024／025。
**DONE / LOCAL_VERIFIED**：最終隔離Git候選完整 `scripts/check` **EXIT0／545.074s**，
**2129 Python PASS／5原opt-in SKIP／7warnings／253.93s**，24 Rust tests、fmt/build/clippy、
Ruff337／mypy267、schema、原scanner／strict secret gate全PASS。真硬體／真provider／遠端CI／發布沒有執行。

## 核對結論

沒有照單重構。使用者六項指控依目前 source／caller／契約核對，完整分類與四張修復卡見
[FIX_REGISTER](../../runtime-evolution/FIX_REGISTER.md)。

| 議題 | 結論 |
|---|---|
| MQTT ACK與記憶體 | 真helper缺口已修；原名稱為CommandTracker。wire成功為applied，不是simulator accepted。原D60 probe已先guard拒絕ACK，不假稱已有實體事故 |
| 模型解析 | 壞JSON／Unicode改固定安全分類；另修真HTTP可重現的Ollama error envelope偽finished。原Conversation已捕Exception，不是整個event loop崩潰 |
| SQLite | WAL、NORMAL、busy_timeout5000原本就有，不重加。修的是connection生命週期，不改schema或pragma值 |
| isolated Python | D43/D46明確只認證Linux x86_64/system3.14。missing runtime有typed refusal，無未隔離fallback；不以sys.executable突破allowlist，平台擴展仍未認證 |
| failover | 一次本地有界重試與每request額外cloud budget是原RT-009契約，非共享扣計數bug；failover.py逐byte保持 |
| Rust | 原list已reap／run已wait，修其他Execute與活group ownership；cap+1沿原output_limit拒絕，不新增成功partial／truncated wire欄位 |

## 實作與相容性

- FIX-022：`mqtt.py` 新增可選ACK status，unknown回None；pending拒絕為FAILED，只有ACK可readback確認，
  late ACK不降級／復活。RAM預設1024，issue清terminal／expired，滿active拒新，顯式prune，無新清理owner。
  probe傳實際status；applied後的duplicate繼續等state，duplicate-only失敗，矛盾unsupported／expired保守退出。
  舊一參數僅trusted caller相容；D60 ISO／epoch、同秒矛盾防護、single publish／無重送均保留。
- FIX-023：三個adapter局部decoder／error envelope與owned stream收尾，`ProviderResponseInvalid(ValueError)`
  固定安全文案且不留raw decoder exception chain；不把protocol錯誤列transport retry，不擴cloud egress。
  Core／ports／原tool intent fence／completion政策與failover.py不改。
- FIX-024：sqlite.py五處以closing包原transaction context，配置失敗close，close亦失敗時保primary＋安全note。
  原writerlock、commit／rollback、PRAGMAs、backup／restore所有權不變。transaction結果須在callback內完成讀取，
  不將仍依賴連線的cursor當跨thread／跨transaction資源。
- FIX-025：既有Execute opportunistic reap；仍活owned group保留stop handle，單PID查詢失敗不阻擋無關操作。
  capture前驗cap+1 sentinel，bounded read失敗亦先cleanup；保留原RPC／result shape／output_limit error。
  最終獨立審查發現不可signal group的EPERM路徑仍可能假stopped，已改固定permission error並以無特權kernel反例核驗；最終24 Rust tests通過，待完整合併gate。

## 實際證據

| 範圍 | 結果／證據 |
|---|---|
| 根代理最初反例 | root-red.log：22 FAIL／2 PASS；只補新tests、未改source |
| 最終root source-only反例 | root-final-rollback-red.log：**24 FAIL／3 PASS／0.45s**；只在獨立Python process載before兩source，工作區source未反向覆蓋 |
| 原WAL／真併發 | 原before的三例均PASS；修後test_sqlite_connection_cleanup.py **11 PASS／0.43s** |
| MQTT／SQLite局部 | tracker16＋cleanup10＋probe26＋原MQTT2：**54 PASS／19.64s**；其後追加真MQTT／conversation／memory共60次寫入的第11 cleanup案例PASS |
| 先前原SQLite與epoch等相鄰 | **129 PASS／3.42s**；隨後新增的收尾／併發負例再驗 |
| Model新25＋原72 | **97 PASS／6.79s**；另原FIX-001 gate32 PASS；三source精確反例24 FAIL／1 PASS→25 PASS，見 [models報告](models/REPORT.md) |
| 固定sandbox原相鄰 | **89 PASS／14.74s**，無skip；unsupported refusal／真bwrap隔離／取消，不改sandbox source |
| Rust最終局部 | workspace24 PASS、fmt/build/clippy PASS；EPERM原分支1 FAIL→修復PASS；精確before＋最終tests **11 PASS／9 FAIL→24 PASS**，temp已清；[Rust報告](rust/REPORT.md) |
| 完整第一候選 | **EXIT1**：Python **2129 PASS／5原opt-in SKIP／3warnings／244.55s**，原23 Rust／format／mypy等通過；unchanged secret gate掃到本機ignored caches／舊untracked驗證檔。未算pipeline PASS，也不是最終Rust source |
| 最終完整候選 | **EXIT0／545.074s**，2129 PASS／5原opt-in SKIP／7warnings／253.93s；24 Rust／fmt／build／clippy、Ruff337／mypy267／schema／原secret gate全PASS；[實際log](final-full-check.log) |

第一候選使用原dirty工作區，scanner `--all-files` 包含本機ignored／untracked內容而失敗，沒有改gate／exclude或清除使用者資料。
公開紀錄 `first-candidate-full-check.log` 保留程式檢查與失敗分類；原始scanner路徑僅本地ignored `private/`保存，沒有raw secret值。
最終改用public HEAD的owned Git clone，只疊tracked修改與9個明確新檔、5個官方digest核對的public tokenizer檔，
不複製local caches／developer副本／verification hash manifests／私人資料；同一scripts/check與scanner原樣執行。
`CLEAN_CANDIDATE.json`核對323個source/test/build檔與工作區相同；根目錄build/dependency／CI／gate檔另核對base HEAD不變。
這是本機候選驗收，**不是remote Actions**。最終同一pipeline全部完成；5 skip保持原真provider opt-in，
7warnings為fresh依賴環境的既有警告，未新增skip／ignore／降低門檻。

併發案例以三個SQLiteStore（獨立writer lock、同一路徑）同時跑20筆MqttStateProjector、20輪真
ConversationEngine＋MockModel、20筆MemoryService有來源記憶，核對三表各20、最新power正確與integrity ok。
全是暫存DB／合成內容；不是live資料、語音provider／ESP32實板的負載證明。

Python API已核對[官方connection context說明](https://docs.python.org/3.14/library/sqlite3.html#how-to-use-the-connection-context-manager)：
transaction context不負責close，因此加contextlib.closing。原PRAGMA值與
[SQLite官方說明](https://sqlite.org/pragma.html#pragma_busy_timeout)一致，沒有藉調高timeout掩蓋問題。

## Review 與回退

獨立review對MQTT／SQLite目前無剩餘blocker，並以真Broker捕捉late duplicate false-negative後補4cases。
Rust第二位reviewer捕捉EPERM假stopped，root以無特權kernel反例先驗1RED，再局部一行修正並完成24 Rust及最終整條gate。
沒有假稱修正後的第三方獨立approval；不是把先前全PASS當無缺陷。
各模型／Rustsource-only反例在owned disposable copy或獨立process進行；原有測試未改以放寬gate。

回退只在停用相應caller／drain owned work後撤D61 hunks與新tests。`before/`保存本輪開始source，
`BASELINE_SHA256.json`固定其hash；**before已包含D60 MQTT時間修復與前輪UI改版，不能用git HEAD整檔覆蓋**。
Runtime只撤本輪process hunk，保留RT-013 bounded filesystem.read。無DB migration／還原、無紀錄刪除，
保留最新conversation／memory／ledger；回退會重新開啟已證缺陷，不是release批准。

## 尚未驗證的界限

- 本輪未連本機1883或控制實板；Broker皆自有random loopback，設備peer為合成。PlatformIO／燒錄／真NTP／目視LED仍待驗。
- 沒有真Ollama／OpenAI請求、外送私人內容或語音品質驗收；合成HTTP只證protocol／失敗恢復。
- 未認證macOS／ARM／system Python3.12–3.13 strict profile，不新增host fallback；不是因本卡暫停已完成RT。
- Rust沒有新idle/Health maintenance、通用subreaper/cgroup；原其他spawn/poll capture失敗分支未在本卡重新認證。
- UI、firmware、sandbox profile、failover policy以hash保留；未操作live8026、私人DB／chat／WAV／keys／models／GPU或正式發布。

Architecture維持 **YELLOW / CONDITIONAL**：本輪恢復局部不變量，沒有新增Core依賴、環、scheduler或永久adapter。
tests/evidence GREEN；修改中的runtime葉節點及一般執行權限YELLOW，live資料／migration／正式release RED。
已解除FIX-022–025的local BLOCKED_BY_FIX；不改原RT編號、ranking或其他品質／發布blockers。
自建隔離Git副本及反例Cargo／DB／Broker／子程序的收尾結果記於FINAL_RESULTS／CLEAN_CANDIDATE，原工作區資料不清理。
