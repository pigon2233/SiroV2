# T10-UI-01-DETAIL：單任務詳情

日期：2026-10-18（Asia/Taipei）。結果：**DONE / LOCAL_VERIFIED（限定本切片；下列證據修補後）**。T10-UI-01整體仍PARTIAL。

## Independent verification follow-up — 證據修補

接獲PARTIAL結果後先把roadmap降為PARTIAL，**沒有修改production code**。舊receipt把server-only fixture的預設NOT_RUN誤放在整體browser欄位，與報告矛盾；該舊標籤不能當作瀏覽器驗收成功證據。下列新執行取代舊browser結論，不以解釋舊metadata代替重跑。

- 重跑真CUA／隔離main＋SQLite＋Rust，保存[逐步紀錄](browser-reverify/steps.json)、8份完整AX與8張原始JPEG：proposed、detail、reload、back、forward、missing snapshot、原任務快照恢復、明確批准後completed。每步保留required／absent斷言、UTC時間與artifact路徑；保存後再次從檔案重驗全部斷言及JPEG格式，8 PASS。
- 所有detail／reload／history／missing動作完成後，backend read仍0；明確批准一次後read1。當前HTML與實際host source hash一致；server child／temp／tab已清理。模型／renderer為原fixture明示邊界，不把真瀏覽器當真Live2D。
- [product-receipt.json](product-receipt.json)現在明確記錄browser_acceptance=PASS、CUA方法、8步路徑與source binding；server_fixture_drives_browser=false只是分工事實。原raw server receipt仍在忽略的verification目錄，不再冒充public browser verdict。
- [rollback package](rollback/README.md)提供完整BASELINE_COMMIT、D69 dirty before／DETAIL after快照、標準SHA256SUMS與方向明確的rollback.patch／reapply.patch。對**目前checkout**正常`git apply --check rollback/rollback.patch` PASS；verify.py僅在temp真正撤回／重套並逐byte比較，checkout不寫。drift／tamper負例均拒絕，來源保持。原task-only.patch是加功能方向，對已套用checkout forward檢查失敗屬預期，不再作為可直接套用的rollback指令。
- 新增REGRESSION_BASELINE的本task條目；本輪導航／detail／goal suite **107 PASS／7.24s／0 skip／0 xfail**。原480與150屬上一輪，這次未重跑、不冒稱新結果。rollback verifier lint／format／mypy PASS。

限制保持：真active child動態取消與正式部署rollback **NOT VERIFIED**；完整full check／owner跨機／聲線／GPU／真Live2D／soak未執行。只恢復本detail切片的DONE／LOCAL_VERIFIED，獨立最終判決待審查者重驗。


## Selected task／Why selected

依roadmap目前順序，D61修復已DONE，下一個尚未完成且依賴齊全的產品項目是T10-UI-01。原RT-001–015皆scoped DONE；RI-003–006仍有各自擴張／發布門檻，不能因PARTIAL便跳過其依賴。T10記憶搜尋D69已在上一輪完成，因此本輪只選原介面規劃已列的「任務詳情」切片。沒有新增RT編號或重排架構。

Discrepancy：roadmap未同步上一輪D69／STATUS進度，故補記；歷史DEFER不覆蓋10-06 scoped DONE。既有工作區包含D68桌寵隱私與D69搜尋等未提交修改，均保留；本卡diff以本輪開始時的HTML為基準，不能用git checkout HEAD回退整檔。

## Before coding／Actual runtime path

既有showPage只接受單層#/tasks，renderGoalTasks已呈現validated session snapshot的狀態／來源／revision／budget與控制；nested詳情尚不存在。實際caller：boot/hashchange/popstate → showPage → renderGoalTasks；手動查詢／批准 → goalTaskRequest → Gateway authenticated goal APIs → GoalTaskService／SQLite，工具沿既有signed scoped Rust read。資料由既有schema014保存，本卡不變更任何後端。

風險為導航與poll callback重繪競爭、過期控制／錯任務、deep link自動執行、刪除或unknown狀態誤示。採同一renderer／snapshot／changeGoalTask，不建立第二poller／writer。MUST NOT CHANGE：Core、Gateway、SQL／state／config／wire、grant／授權、provider／TTS／Live2D、desktop／WSL與其他先前工作。

## Implementation

- 新增#/tasks/<canonical UUID>，保留所有原九頁路由與導覽；標題／焦點／返回清單及瀏覽器歷史有效。
- 詳情只顯示所選任務，建立表單hidden＋inert，其他任務不在DOM中。清單增加「查看任務詳情」。內容與控制仍由既有renderGoalTasks／changeGoalTask產生。
- 直接載入／重載先要求手動查保存狀態；導航不發送新request、不批准、不恢復或重播。readback成功才呈現snapshot；斷線／foreground／unknown沿原fence移除卡片。
- 新的前端snapshot marker只區別「未查」和「查過但此ID不在最多20筆快照」；缺ID不宣稱刪除、不跨session查詢、不把URL變成action。
- 無public API／protocol／state／config格式變更、無新增依賴、無architecture deviation。

## Tests run／Regression results

| 檢查 | 結果／範圍 |
|---|---|
| 新專項test_frontend_task_detail.py | 11 PASS，2.32s；實際HTML內production script＋真body階層，合成DOM／socket／HTTP。涵蓋單任務、back/forward、direct load、missing snapshot、disconnect／foreground／unknown、revision-bound批准及取消、無效route、pending GET切換selection。沒有skip／xfail |
| 原前端與相關後端 | 480 PASS，3既有dependency warnings，27.82s；`pytest -q tests/integration/test_frontend*.py tests/integration/test_goal_task_api.py tests/integration/test_goal_task_loop.py tests/integration/test_memory_search_api.py`。含上列11，不相加 |
| 桌寵／語音／記憶相容 | 150 PASS，3既有dependency warnings，27.36s；`pytest -q tests/integration/test_desktop*.py tests/integration/test_local_whisper.py tests/integration/test_selected_voice_profile.py tests/integration/test_memory_ingress.py tests/integration/test_memory_organization.py tests/contract/test_http_stream_cancel_phases.py tests/contract/test_ollama_completion.py` |
| 靜態檢查 | 新test Ruff、format、mypy PASS；實際inline script `node --check` PASS；git diff --check PASS |
| 新artifact敏感掃描 | 原detect-secrets對新報告／receipt／patch／測試掃描，0 findings；此為限定檔案檢查，不冒稱全樹secret gate已跑 |
| source-only rollback | 相對本輪開始HTML的精確patch，在自有temporary workspace reverse後bytes等於原D69檔，再apply等於本輪結果；合成latest-data sentinel保持。不是正式部署rollback |

原版新測試8 FAIL／3 PASS。初次實作11例中3 FAIL：synthetic DOM未反映href、缺ID文案斷言過廣、取消fixture未保留既有approved_at。保留原失敗log；最終使用標準anchor.href（舊合成DOM亦支援），新navigation fixture補真DOM的href attribute reflection，固定fixture保留原批准時間。初次相關套件33 FAIL／447 PASS是原測試DOM缺setAttribute導致render被捕為failed；改標準屬性用法後所有原assert保持、480 PASS。首次回歸命令誤用不存在的test_goal_task_service.py，exit4／零tests；改用實際test_goal_task_loop.py後執行。未改既有tests或降低gate。

## Real integration（與mock分開）

重用既有product-probe，隔離copy當前source、真gateway.main／Core／SQLite／Rust child／隨機loopback。renderer明示synthetic placeholder；沒有真provider、TTS、私人資料或其他電腦連線。

CUA實際點擊：建立notes.md→待批准且真read=0→開詳情，建立表單消失→reload仍詳情且無批准→重啟main→reload／手動query同ID仍proposed、revision1、read=0→詳情按批准一次→completed、revision7、steps1、真read=1；顯示來源行2／行4、原檔SHA與批准時間。返回list→browser back詳情→forward list，read仍1，沒有重播。截圖：[detail.png](detail.png)。

原server-only receipt的NOT_RUN標籤曾造成矛盾，不能單獨證明CUA PASS；最新結論與可保存重驗的browser紀錄以本文最上方follow-up及目前product-receipt.json為準。先前截圖detail.png作歷史參考，本次原始JPEG證據位於browser-reverify。

## Acceptance criteria

| criterion | 判定／evidence |
|---|---|
| UUID獨立detail且只見所選任務 | PASS；新專項多任務隔離、真CUA表單移除與標題／來源／控制 |
| back／forward／direct／reload | PASS；navigation新測試＋真CUA重載、返回及browser歷史 |
| 未查／缺ID／斷線／unknown不復活舊控制 | PASS；新專項及原goal race／mutation suites。缺ID只稱當前bounded snapshot未提供 |
| 來源／revision／批准／取消與restart保持 | PASS；真main/Rust/SQLite重啟零read、手動一次read，原API／loop／負向fixtures；詳情取消為合成transport測試，未對真active child另行動態取消 |
| 導航零request／副作用，不增加owner | PASS；新測試calls/socket/timer斷言、原導航／語音停止回歸；真browser導航後Rust read仍1 |

## Remaining issues／limits

本切片無已確認未解缺陷。詳情沿目前session最多20筆列表快照，無分頁或跨session任意歷史查詢。整體T10仍有設定用語、完整可及性／真人體驗，T12追加素材與自由活動及原語音／設備／發布gate保持。未跑本輪完整scripts/check、真provider／GPU／B聲線人耳／真Live2D／WSLg實體IME／power loss／長期soak／正式部署rollback；這些不列PASS。

本輪所有代碼驗證在功能修改後完成；不推送、不部署、不重啟使用者8000或另一台電腦。不以本卡DONE代表整體SIRO完成。

## Files changed／Rollback

本卡修改：static/index.html、DECISIONS D70、runtime roadmap、TASKS、STATUS、INTERFACE_REDESIGN_PLAN；新增test_frontend_task_detail.py與本證據。desktop/host.js與先前D69測試／報告是本輪開始已有工作，不屬本卡。

回退使用方向明確的[rollback package](rollback/README.md)撤本卡HTML增量及相應新測試／文件；保留D68／D69與最新DB／task_json／journal，不做資料降級或restore。source-only reverse/reapply已實測。完成後停止，未開始下一卡。
