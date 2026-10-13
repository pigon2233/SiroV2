# Migration plan

## 2026-10-13 — RI-005 D52 signed source launch / readiness VERIFIED

D52沒有DB/schema/config/grant migration；明確operator opt-in可逆，同schema source接線是增量。只改既有ReleaseManager/read-schema fact、productlauncher與Gateway composition/ready；新增4份tests。complete manifest/CLI stage-rollback、D49/D50/D51、Core人格/記憶/權限/模型/語音/UI/SQL/deps保留。

必要migration由schema_migration_required拒；origin/schemaepoch在existingD50owner內beforeprovider/initialize重查。Rollback仍D48code-only保持最新資料，不隱含restore；true1→2→1已驗同schema資料保留。

273baseline中270不改；exact7 source-only disposable reverse/reapply PASS，保所有資料與Git歷史。D48 schema helper抽出前後AST相同；D51 backup/CLI四檔與D50 owner/operations source保持。

RI-005整體仍 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**：舊／非受管writer停止、parent驗簽後sameUID換包、maintenance→exec CLOEXEC空窗與人工批准handoff未解除。D52只證同schema／D52-compatible src package，任意deps/ABI/migration/其他OS/powerloss/正式deployment未證。FIX-002/005/006產品gates、RT-011/013/015原scopedDONE不變。

沒有重啟live8026／讀privateDB/chat/WAV/key/config/models/GPU或正式deploy；全部程序/DB/HTTP為self-owned合成fixture，只讀health，無provider/TTS請求或效果重播。

[實際驗收、限制與回退](../evidence/RI-005-launcher-2026-10-13/REPORT.md)。

## 2026-10-13 — D51 / FIX-015 backup cancellation VERIFIED

本輪是兩個既有production方法區域的incremental修復，無DB/schema/config/grant migration。只改SQLiteStore既有backup方法與CLI `_backup` wrapper，新增兩份專項tests；operations、D49 restore body/SQL、D50 owner/Gateway/原tests、Core/權限/providers/voice/UI/launcher/deps不變。

每次backup只有一份ownedexecutorFuture/context/cancel flag；原ZIP TemporaryDirectory在await真正完成後cleanup，不新增adapter或永久fallback。成功既有API保持，舊不安全cancel行為明確撤銷。

269/271既有baseline bytes保持，exact4 source-only temporary reverse/reapply PASS；保留所有資料與Git歷史，source rollback不授權再用舊危險取消路徑。

RI-005整體仍 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**：first-adoption舊／非受管writer停止、真正signed launcher/version/readiness與人工批准handoff仍待各自驗收。FIX-002有用搜尋、FIX-005語音速度／人耳、FIX-006理解產品gate保持；RT-011/013/015原scopedDONE及編號不改。

沒有操作live8026、私人DB/chat/WAV/key/config/models/GPU或正式部署。所有DB/OS probes是自有合成資料；pause/fault injection明示，不能冒充真人產品或power-loss驗收。

[驗收、分類、限制與回退](../evidence/FIX-015-2026-10-13/REPORT.md)。

> 2026-10-01 狀態說明：下列「尚未實作／僅設計」為 Phase 2 原始設計時點。當前逐卡完成與修正狀態以 RUNTIME_EVOLUTION_ROADMAP.md 及對應 evidence 為準。
僅設計；使用者本輪授權 Phase 2，尚未執行任何 RT task。

| 階段 | 任務 | 退出條件 | 回退界線 |
|---|---|---|---|
| G0 基線可信 | RT-001 | migration invariant 核對、main composition smoke、真服務未驗明列；已知 pytest fail 解決 | 只回退測試/驗證修改 |
| G1 工具迴圈正確 | RT-002–003 | 原生訊息 + 同批工具結果完整；legacy 同時通過 | 新 run 回 legacy，舊 candidate drain |
| G2 執行與語音有界 | RT-004–007 | process cancellation/output、Qwen cleanup、catalog availability 通過 | backend/profile 關閉；不重送 unresolved action |
| G3 任務可恢復 | RT-008 | journal/crash/reconciliation pass | 留新 schema 關 feature；不能用舊 run parser 接中途工作 |
| G4 日常任務能力 | RT-009–013 | provider/session/context/browser + Rust read-only backend 各自驗證 | 每項獨立關閉；來源與 session 不合併 |
| G5 記憶與排程接入 | RT-014–015 | source-backed memory、預設關閉 proactive scheduler、公平取消 | 停止新增候選/排程；既有 revisions 保留 |

每張卡先用 audit 指向的 source 重現或明確縮小問題；若 evidence 不成立，標 KEEP—NO CHANGE REQUIRED，不硬做預設方案。實作時發現 public contract 改動，先更新 docs/DECISIONS.md 和相應契約再改 code。

## 每張卡操作程序

1. 確认依賴、git diff、source drift；保留全部既有修改。記錄 baseline 与新卡精確范围。
2. 以合成 fixture 補主路徑/故障案例；不能只測 wrapper 並假設 main 已接。
3. 做單一 subsystem 增量；先 candidate，再舊/新 profile 對照。
4. 驗證 docs/ACCEPTANCE 受影響情境、ruff/mypy 與相鄰 integration；Rust 有改才追加 Rust checks。
5. 保存 docs/evidence/RT-xxx/ 的指令、exit code、source digest、profile、mock/real 層級、差異與 rollback rehearsal。
6. 通過才標 DONE；外部條件不足用 BLOCKED-EXTERNAL；不得因 synthetic pass 宣稱硬體通過。

## 故障注入矩陣

| 故障 | 必須觀察 |
|---|---|
| assistant 回兩個 calls，其中一個失敗/拒絕 | 兩個 observations 後才下一 model round；一次 final |
| provider 在 text/tool emission 前/後斷線 | 前可 bounded retry；後不重發工具意圖 |
| cancel 與 tool completion 同時發生 | epoch fence 決定唯一 terminal；late output 不出 UI |
| child 無限 stdout/stderr 或派生 child | bounded memory、無 pipe deadlock、只清理 owned group |
| worker startup/render timeout | reap、下一 render 正確配對、單 worker |
| crash 在 side effect 後 observation commit 前 | unknown + readback，不直接重做 |
| restore 舊 schema / old frontend | 相容明確 PASS 或 blocked；不靜默變資料 |
| browser session A/B | 不交叉 page/state；disconnect/TTL 清理 |

## 升級門檻與停止條件

G1–G3 的 runtime 基礎版本需：所有受影響 automated gates 通過、一次真選用 provider 工具閉環、一次可視 Live2D/文字回歸、RTX3050 Qwen lifecycle 驗證及 rollback rehearsal。未完成真測時只能稱測試候選版本。

發現 state corruption、取消後仍 dispatch、未知副作用被重送、private data 混入 evidence 或未授權 cloud fallback：停止擴展、保留現場與去識別證據，回退新 run profile。不是刪資料或重寫整個 subsystem。

G4/G5 不必等待 ESP32/HA/第二主機；這些能力保留 LATER，另做外部驗收計畫。24h soak 是產品發布 gate，不能被這份遷移計畫取代。
