# RI-006 / D55 — 有來源的唯讀改善提案

開始：2026-10-13；最終產品／回歸驗收：2026-10-14（Asia/Taipei）。Public parent `0abbbc48ceebba91138f0cbc68bffbe1aecdb399`。只有4個既有production檔案＋2個新測試；原132份Python測試、D41 SQL/shape、TTS D54、schema/locks/權限/發布保留。無live8026、私人DB/對話/WAV/key/config/model/GPU或正式deploy。

## Outcome

電腦協助新增「改善建議」與手動查詢。沿原D41 latest同session/route/freshness事實，僅支持failed + HTTPStatusError →固定調查提案。附source UUID、已知/未知、調查範圍、測試、相容與回退；根因 UNKNOWN — NEEDS INVESTIGATION，分類 DEFER，無patch/預期源碼修改。這是調查／審閱切片，不是自動修復或整體自主進化完成。

Core evolution只組合內容；IntegratedCompanion沿已啟動repo，不呼叫ensure_core、初始化、migration或reconcile；Gateway只認證/參數驗證/傳輸/no-store，actual main使用新callback。HTTP每GET重讀canonical來源，無cache/新schema/scheduler/owner。UI按鈕只GET，無自動poll/export/approve；owned5s timeout＋AbortController/generation，refresh/新turn/assistant_started/連線交接/unload撤除舊view、拒late response/json。字串只textContent、完整固定欄位/UUID/identity/bytes/authorization shape檢查。

HTTPStatusError不是HTTP碼、provider定位或根因；派送旗標也不能證明效果已完成。派送過必須另行回讀，不重做。調查確立最小真實差異後才沿原PatchProposal/D43/人工review，發布仍受RI-005。

## Evidence and tests

- `backend-red-final.log`: 修正新fixture的async decorator/required privacy後，未實作來源 **22 FAIL / 0.96s**；初始16fail/6fixtureerrors不能冒稱22個產品反例。
- `backend-final.log`: **24 PASS / 1.06s**（2 existing warnings）。同session/route、latest unsupported masks old、901s/future、source更正/刪除、invalid/unknown/cancelled/no rawcanaries、unavailable無initialize/read、disabled-after-startup、auth/方法/失敗no-store、DB dump一致及no model/Verifier/subprocess/rawreadback。
- `frontend-red.log`: 原頁 **71 FAIL / 2.54s**（無panel）；新test fixture已先對齊D41 root_cause=UNKNOWN與schema_version1，沒有修改原測試。
- `focused.log`: 初輪 **113 PASS / 6.42s**。`regression.log`: 初輪new+D41/TTS/patch保护 **202 PASS / 14.02s**。
- `clean-check-first-failure.log`: 完整check確實失敗：**3 FAIL / 1,795 PASS / 5 original opt-in SKIP / 7 warnings / 224.26s**。不能用前述focused PASS冒稱全通過。
- `fragment-regression.log`: 原3failure與相關71新前端/24後端/能力/語音 **142 PASS / 7.07s**，3既有warnings，原測試保持。最終完整check **EXIT0 / 499.591s**，**1,798 PASS / 5 original opt-in SKIP / 7 existing warnings / 211.70s**，見`clean-check-result.json`與`clean-check.log`。
- Ruff src/tests PASS；mypy **253 source files PASS**；最終full script含Rust6/fmt/build/clippy、格式/Ruff/mypy、pytest、schema、原scanner與strictgate。True public Git checkout/fetch包含FETCH_HEAD，只overlay精確6檔，沒有scan main private tree。cloud exact-head另記，不拿local代證。

## Actual product acceptance

`browser-final-result.json`、`owned-http-final-result.json`與`readonly-proposal-final.png`：真正main/D50 composition，在自有temp SQLite、random loopback46707、offline/no model/TTS requests。In-app browser點開電腦協助→手動查詢，實際source `3f9e232a-4f6d-4aac-b198-64fbbb0deb66`，UNKNOWN/固定驗證計畫/零privatecanary；fixture只更正error為ReadTimeout，重查明示no evidence且舊卡空。修前guard的第一次browser觀察也保留，最終圖片和JSON綁最終6檔的source hash。沒有使用Live2D/model資產，本probe不是它們的驗收。

最終自有child SIGTERM exit-15，actual Application shutdown complete、joined、temp removed，tab已close。第一個probe parent exit143、無graceful log，原因UNKNOWN：保留HARNESS_INTERRUPTED結果，已確認child/listener不存在、人工清理該自有temp，不算graceful PASS。只在probe的Popen加入start_new_session後兩次新probe正常收尾；不修改production取消/owner，不把harness問題當產品root cause。

## Review findings and repairs before release

| Finding | Classification / source | Confirmed root cause | Local repair / evidence |
|---|---|---|---|
| Producer例外500／錯方法405缺no-store | MINOR_FIX LOW / MISSING_INTEGRATION, TEST_GAP；independent RI006 candidate review | header只加在成功/HTTPException，route405與callback非HTTP錯誤繞過 | endpoint-specific pure ASGI header（其餘HTTP/WS原await，不建task），安全503且不echo diagnostic；新增case先1RED→24backendPASS |
| 新hook讓原inventory/speech fragments依賴proposal module | MINOR_FIX LOW / IMPLEMENTATION_BUG, REGRESSION（未發布candidate） | existing standalone fragments執行時未載入clear function | 只guard existing-fragment optional activity hook；原tests保持、新fullpage仍執行全部invalidate，3原FAIL→142PASS |

獨立reader已確認不重写D41/不rawreadback、不得ensure_core、singleclass不猜根因；找到no-store上述實證。reviewer後續turn與frontendagent遇帳戶quota，不能宣稱獨立final approval；root完成實作與source/actual regression/final lifecycle審查。CodebaseMemory無callable工具、graph/reindex NOT_RUN；用rg、source、真測試及hash。

## Architecture / roadmap / freeze

Overall health YELLOW。改善：來源到產品caller接通、導出提案可撤回、前端取消與no-store盲區補齊；沒有provider/tool/device互滲、循環依賴、新owner/updater/scheduler/schema或runtime compatibility bypass。原既有inventory/speech的新增coupling已在candidate驗收局部解除。Core policy、D41、D54、PatchProposal、RI005保持。

Debt：一個受支持類別與人工編寫計畫；查詢時快照不是即時全局監控，不自動感測來源更正；未知根因需安全定位後才有修復。它不建立立即FIX或虛構patch。異常轉安全503仍為失敗，不能算有提案成功。未測真provider問題／speech latency、人耳體驗、所有OS。

RI-006 PARTIAL：D55唯讀singleclass caller切片VERIFIED後可KEEP後續安全定位；不擴任意生成／執行／發布。RI005仍PARTIAL/BLOCKED_BY_RELEASE_INTEGRATION（old/unmanaged writer absence、immutable exactbytes、人工連續handoff）；RT011/013/015 scopedDONE與FIX002/005/006品質gates保持，不ranking/重編。Freeze tests/evidence GREEN、proposal/Core/Gateway/UI YELLOW，liveDB/migration/permissions/release RED。無新增最終scoped blocker；既有release/productgates不解除。

下一三已有scope（非ranking）：RI005 exact captured package/import window（先OS prototype與RED）；RI005 approved maintenance→runtime handoff/adoption證據；RI006可靠safe component/reason evidence→最小調查/真patch提案。Old unknownwriter absence不能靠PID/新lease/BEGIN偽證；沒有實證支援新抽象或RT cancel/merge。

## Compatibility and rollback

Optional callback/additive GET/panel，既有HTTP/WS/tools/provider/identity/DB不變。Legacy/restoreoff/unstarted是unavailable，GET不啟動store；原D41只facts，保持shape及900s邊界。Raw legacy PatchVerifier仍只是trusted check，沒有被本view執行。

`rollback-final-result.json`：自有temp逐檔reverse至parent（4existing production）/刪新增2tests，再reapply精確hash，原132tests全bytes相同，D41/TTS不變，temp removed。實際回退先取消提案view/停止該source的新工作，逆此6檔或該commit的source scope；保journal/memory/ledger/DB/歷史，不執行資料restore、不重新啟用已知危險舊路徑。

## Publication

提交、remote exact head與新Actions狀態於驗收後追加；Git push不是正式runtime deployment。首次local full FAIL保留，只有最終相同source6的完整成功與cloud結果才解除本卡verification gate。

Final local gate: PASS；精確final6 SHA見clean-check-result與rollback-final-result。完整check含public tokenizer扫描，未更改原secretgate或排除規則。原132Python testfiles不變，增加95cases；Ruff320/mypy253/schema/Rust與原checksPASS。Frontend raw RED全log留本機，提交summary與原HEAD/newtesthash可重現，不把summary當raw log。
