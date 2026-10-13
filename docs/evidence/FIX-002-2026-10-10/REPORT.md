# FIX-002 — Browser diagnostic / readable-page repair

日期：2026-10-10。整卡目前 **PARTIAL**：局部診斷、partial read與teardown callback已修復驗收；useful public search仍未通過，間歇cleanup逾時根因UNKNOWN。不把fixture PASS稱為產品搜尋已完成。

## 已確認問題與最小修復

修前真Chromium A/B fixtures證明：跨站image/script被擋會導致整頁ScopeViolation；iframe有時沒有partial標記；button／iframe-top越界導向被擋後，舊driver有回報舊頁或chrome-error observation的路徑。未授權B命中始終0，不宣稱已發生外洩。原使用者Bing incident的raw arguments/profile/blocked resource未知，根因仍 **UNKNOWN — NEEDS INVESTIGATION**。

本卡保留全部origin限制／批准／原參數hash。browser專用typed reason由orchestrator可信映回原error=ScopeViolation／FAILED；optional observation只加固定reason，native、legacy、journal同一安全投影，普通例外不變。不傳str(exception)或被拒URL。主frame／redirect拒絕在navigate及observe檢查，context-destruction也保留原因。所有越界圖片、script、iframe仍abort；可讀主頁透過既有BrowserObservation／兩種wrapper回optional partial/subresource_denied。UI四種browser操作均用textContent標部分載入，未知reason不降成完整。

partial僅表示本次觀察已見被擋資源；DOMContentLoaded並非所有late requests完成。iframe-top可在首次合法A快照後發生，後續observe會拒絕。不加networkidle等待、不新增browser abstraction／schema／worker／registry。

## 真實與合成驗收分開

- [修前A/B](browser-scope-before.json)、[最後A/B](browser-scope-after.json)、[觀察邊界](browser-scope-verification.md)：10真Chrome fixtures，檢查PASS，B命中0，source起訖一致，owned瀏覽器／server cleanup全true。
- [新傳遞契約修前](contract-before.log)14FAIL／7PASS；修後21PASS。前者包括API尚不存在，不能冒充當次Bing根因重現。
- [UI修前](frontend-renderer-before.log)9FAIL／3PASS；修後12PASS。實際renderer函式[真Chrome18情境](ui-verification.json)全部PASS，pageerror0、network requests0，未知／惡意reason、HTML text、舊payload與部分載入均覆蓋。這是component renderer，非完整產品／provider驗收。
- [本卡fixture初次失敗](initial-fixture-failure.log)：ExecutionContext fixture位置參數錯誤，1FAIL／11PASS；只修測試fixture，未放寬production門檻。probe最初對舊DTO的錯誤假設與UI初次provider evaluator過寬紀錄也保留。
- driver/catalog/session/native取消／TTL／cap／origin reset／stale screen：[specialized.log](specialized.log)57PASS；補destroyed-context與兩種真main stateless profile後[final-contract-driver.log](final-contract-driver.log)35PASS。這些有重疊，不相加。
- 第一完整回歸：[full-suite.log](full-suite.log)763PASS／5 real_provider未選／3既有warnings，111.96s。這是在新增cleanup切片之前，不能覆蓋最後新增source；最後[完整回歸](final-full-suite.log)767PASS／5 real_provider未選／3既有warnings，111.45s。

## 公開搜尋尚未可用

[Bing](public-search-acceptance.json)：真configured provider→candidate IntegratedCompanion→catalog/proposal/resolve→一次真browser dispatch→native paired continuation，兩model rounds、exact hash、單terminal、cleanup PASS。Bing只回頁首，不含query結果；延後1／3秒仍相同。native_chain_gate=true，useful search與automatic研究gate=false。初次evaluator把native wiring當整體PASS過寬，原[log](public-search-initial-evaluation.log)保留，後續明確修正。

[DuckDuckGo](public-search-duckduckgo.json)：同一真鏈路，只批准独立乾淨公開URL；網站回human challenge，沒有query結果。模型承認無法確認，但提出不當「繞過驗證」建議；沒有實際bypass dispatch。這是FIX-006理解／誠實限制後續的真provider反例，不包裝成成功。只保留公開內容，未讀私人chat／DB／WAV，不改允許origin／反驗證政策。

DuckDuckGo BrowserSessions.close另出現ExecutionCleanupError。一次獨立無模型[cleanup probe](before-teardown-guard/public-browser-cleanup.json)再次在4.001s逾時，navigation1.617s，Chrome已退出而一個自身Playwright child仍存活；僅按已記錄PID＋start-time緊急收束自有child，最後descendants=[]，不殺其他程序、不延長正式deadline。初輪未保存PID，該輪殘留狀態UNKNOWN；不得把後一輪cleanup成功套用前一輪。[分步observer對照](public-browser-cleanup-diagnosis.json)current close0.059s／stop0.016s，before snapshot close0.034s／stop0.602s均正常，未證實是本卡regression。具體阻塞步驟仍UNKNOWN。

## 保存、契約與回退

[baseline](baseline.json)記錄本卡前dirty來源；只改6個production檔＋4個新tests。[preservation](preservation.json)覆蓋221個source/test/script/config/lock檔，既有RI-002及voice/session dirty修復保留。未接觸私人資料，未重啟8026；source修改需之後啟動載入，不稱已部署。

[D37](../../DECISIONS.md)、[CONTRACTS](../../CONTRACTS.md)在實作前記錄窄幅partial／typed reason契約。[impact](impact.json)為current source/AST；當前chat沒有可呼叫Codebase Memory工具，未繞過既有owner lease或把舊graph稱為最新。

[repair.patch](repair.patch)基於exact pre-card source，不是HEAD；[rollback](rollback.json)在temp copy反向／重套與SHA比對PASS。沒有DB restore／effect replay，未做運行服務部署回退。最終含teardown切片共10檔，已重建並再次反向／重套SHA驗證。

實際命令與limits見[checks.json](checks.json)；format/lint/mypy210／schemas PASS。未做聲音／GPU／真人Live2D／設備／24h／遠端CI／正式發布。

介面核對：[Playwright Request](https://playwright.dev/python/docs/api/class-request)、[Route](https://playwright.dev/python/docs/api/class-route)；cleanup調查参考[APIRequestContext.dispose](https://playwright.dev/python/docs/api/class-apirequestcontext#api-request-context-dispose)與[Page.unroute_all](https://playwright.dev/python/docs/api/class-page#page-unroute-all)，尚未把候選方案當已修復。

## 已驗的teardown局部修復；尚未驗完的public可靠性

本機慢HTTP response＋真route.fetch，原driver close/cancel都被SDK直接輸出TargetClosedError：[before](pending-cleanup-before.log)2FAIL，沒有程序殘留且cleanup本身約0.06s；不能把這個失敗當成公網4s timeout重現。依D37只加driver-owned closing旗標，關閉開始後新route abort、既有callback的Playwright Error只在teardown期間正常收斂；live errors仍傳出，route仍掛到browser真正close，無scope空窗／新owner／改deadline。

[after](pending-cleanup-after.log)2真Chrome PASS／2.16s，close與cancel均约0.067s，SDK listener0／asyncio error0／pending route0／own live child0。兩額外protocol fixtures驗live Error不隱藏、closing請求只有abort。最終[無模型public cleanup](public-browser-cleanup.json)0.069s，零殘留／無emergency signal，仍captcha；一次PASS不證明原間歇故障消失。原兩次失敗、後續正常observer及其時間／source資料全部保留。

搜尋仍BLOCKED_BY_FIX：FIX-002；本機唯讀／桌寵及獨立已確認安全FIX可繼續。沒有因gate未過而改allowlist／驗收標準或硬加search abstraction。

最後format／lint／mypy210／schemas／scoped secret scan0 findings／git diff --check PASS；既有8026 health/root均HTTP200，唯讀確認、未重啟。
