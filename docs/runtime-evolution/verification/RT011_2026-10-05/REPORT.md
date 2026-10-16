# RT-011 Independent Verification — 2026-10-05

**VERIFIED_WITH_MINOR_ISSUES**，限定 roadmap 明確授權的 budget 切片與 D28 configured reference-token policy；summary 仍 DEFER。建議保留這個限定的 DONE。未觀測到本輪相關 regression；不宣稱 Groq 內部 framing 的全輸入通用上界或完整摘要功能完成。本輪未修改 production code、原 tests、roadmap、STATUS、私人 DB 或8000服務。

## 1. Identify target

重新讀 roadmap 所有 RT 狀態與completion date，最新 DONE 是 RT-011（2026-10-05），其native completion補記優先於歷史PARTIAL。RT-012仍PLANNED，不開發下一卡。RT-011卡內明確SPLIT：budget完成，summary延後。

## 2. Reconstruct intent

讀完整task的Objective/Problem/audit/scope/acceptance/compatibility/tests/rollback，核對context compression matrix/F08、ARCHITECTURE_REVIEW的SPLIT、CONTRACTS、D27/D28、REGRESSION_BASELINE。原byte-only报告保留PARTIAL歷史，不以它的tests替代native gate。

目標：量測並阻止configured over-limit request，保持goal/system authorization/pending tool pairs及journal；不truncate、不改facts。完成增量要求pinned官方tokenizer/template、selected provider/model/window、requested output reserve；unknown/missing/tampered/unsupported shape fail closed。Rollback需下一次drained startup關native及byte兩switch才回pre-budget path；不刪DB/journal。原summary timeout/source-correction項屬DEFER摘要子工作，沒有冒充已測。

## 3. Actual implementation / caller / consumer

gateway.main保存selected_provider，先構建既有FailoverModel，再在最外層包ContextBudgetModel。因此budget在任何provider/attempt前。candidate缺省byte65536、native1；legacy維持舊路徑。SIRO_CONTEXT_MAX_BYTES=0只關byte；native0只關native；startup固定，不途中讀env。

byte guard計算完整ModelRequest compact UTF-8 JSON，包括prompt/messages/tools/schema/arguments/results/output設定；這是logical bytes，不是wire bytes/tokens/RSS。request over-limit拋ContextBudgetExceeded，沒有改寫input。

Groq openai/gpt-oss-20b且hostname api.groq.com選GPTOSSBudget，綁同selected adapter.request_payload（dispatch亦使用此builder）。五資產SHA256核對；pinnedtemplate + tokenizers BPE計input，input+requested output+256對startup window。window只能減小；existing ModelRequest output ceiling仍保持。Token counting進asyncio.to_thread，cancel前後都有dispatch fence。unknown profile/missing資產使用UnavailableTokenBudget，沒有猜byte/token比例fallback。

unsupported multi-call/late-system/Harmony-marker等形狀明確失敗，沒有偷偷省略pending call。允許的payload只在HF template normalization副本將arguments text解析dict，原wire input保持。Core/Integrated消費stream/error，原SQLite journal保留完整goal/system/tool pair及超限結果。

未見detached implementation、stub、TODO/NotImplemented替代核心gate。舊legacy或operator雙switch-off是explicit rollback；不存在另一層budget後再绕過。未新增summary/memory writer。Tokenizers資產只在setup script顯式下載，runtime不網路下載。

## 4. Scope discipline

scope.json：16個completion source/config/test hashes全吻合。只在temporary copy先reverse completion.patch，再reverse原byte implementation.patch；兩次exit0，pre-completion及pre-task hashes全吻合。未回退actual working tree；不把既有dirtytree全部算本卡。

增量涉及adapter serializer extraction、gateway caller、新native context/profile/setup、tokenizers/Jinja2依賴與lock/cacheignore，超原暫定filelist有D28記錄且為native驗收必要。六個舊synthetic fixtures加explicit native0，未刪 assertions/新增skip；專項native tests另測真adapter和supported policy。

沒有mass rename/move、Core refactor、port/HTTPWS requiredfields/state schema/migration/identity/affect算法/long-term memory format/模型權重變更。新的startupenv及publicassetprovisioning為明確增量。pending/failedrun readback、metadata與sessionrestore依舊production consumers。

## 5. Actual tests and quality

related.log：**206 passed、0 skipped/xfail、3 dependency warnings，67.87s，exit0**。含byte/nativebudget、sessionrestore、Integrated、journal、providerretry/failover/adapters、batch、Gateway/main/terminal、executionlifecycle/boundedexecutor。

independent.log：另 **1 passed**。真pinnednativeguard + 外層ContextBudgetModel + two-backendFailoverModel；byteoff、nativewindow1拒絕，兩backend都零invocations，rawgoal/authorization/pendingcall/result與input完全不變。

ruff.log PASS；mypy.log **181 files PASS**。asset-integrity.json：五資產hash全PASS。沒有重跑fullsuite；411passed/5skipped及兩Groqprobe是implementation歷史evidence，未標成本輪PASS。

Tests實際跑production wrapper/GPTOSS/tokenizer/adapter/main/Core/SQLite/ASGI。邊界-1/0/+1、outputreserve、missing/tamperedasset、unknownprofile、unsupportedshape、nativeon-byteoff、envstartupflip、countingcancel都有覆蓋。巨大400000字元synthetictool result只執行一次，continuation provider不再呼叫，完整pair仍在SQLitereadback；executor/model合成，不是真OS效果。

部分nativeboundary基準由productioncount_input產生；這驗證gate一致性，不是獨立tokenoracle。implementation保存的四HF AutoTokenizer對照是歷史證據，本輪.venv無transformers，未重跑/未安裝它；不能稱本輪獨立HF一致驗證PASS。本輪已檢查official資產hash並執行actualtokenization與dispatchguard。

Dedicatedtests位於tests，沒有skip/xfail；verification獨立test顯式執行。取消test用thread events與timeouts確認eventloop仍能回應；不代表thread立即停止或peakRSS有界。未做長期flake/soak統計。

## 6. Relevant regression baseline

| Baseline | Status | Evidence / limits |
|---|---|---|
| conversation/streaming + provider port | PASS | native/byte main、old adapters/Integrated/Gateway；真provider/browser NOT VERIFIED |
| toolcalls / pendingpair / goal與source | PASS | huge result journal、unchangedrequest、independenttwoattemptfence、batch/lifecycle |
| fallback/retry / privacy / metadata | PASS | guardoutsidefailover、providerretrycontracts/main、backendreadback不變 |
| session/restart/journal | PASS | restore/runjournal suites；不刪history/unknown不replay |
| cancellation/timeouts / terminal | PASS | countingcancel、execution/Gatewayfence；非硬體音訊驗收 |
| config/legacy/rollback switch behavior | PASS | startupenvfreeze、legacy、native0/byte0分開；實際deployedrollback NOT VERIFIED |
| 真Groqframing通用上界 / realprovider E2E / GPU/GUI/powerloss/soak | NOT VERIFIED | 本輪不讀key/不呼叫付費provider，不重跑歷史probe |

## 7. Acceptance criteria

| Criterion | Status | Evidence / exact scope |
|---|---|---|
| 不送超限request | PASS（configured byte/reference policy） | byte/nativeboundary、main零transportcall、independent零兩backend；Groq內部所有輸入framing上界NOT VERIFIED |
| 目標/授權/pending完整 | PASS | unchangedModelRequest/nativepayload、副本normalization、hugetoolSQLite完整pair；unsupportedshape明確reject不剪裁 |
| 摘要不寫人格facts | PASS（budget切片不寫facts的invariant） | 沒有summary/memorywriter/schema變更；summary本身未實作、DEFER，不宣稱摘要功能驗收PASS |

## 8. Issues / severity / fixes / roadmap

沒有新已確認production缺陷或regression。**P3 evidence/measurement limitation**：reference/template與Groqserver不是完全相同framing；歷史两probe的+4/-6差異被256覆蓋，但兩sample不能證明通用上界。D28/CONTRACTS/報告已如實限定referencepolicy，無hiddenfallback；不可把這項PASS寫成「真provider絕不overwindow」的普遍保證。

Required fixes：限定budget切片無新增productionblocker。若要把「不送超限」擴為Groq實際所有framing保證，須取得server同款serializer/tokenoracle或可靠上界，否則該擴張criterion應PARTIAL/NOT VERIFIED。

Optional improvements：獨立HF reference cases納標準可重現環境；更大/複雜schemas與tooltranscripts的server差異量測；countingthread/resource成本；freshinstall/wheel外目錄setup及drained部署rollback。這些不是本輪偷開summary/RT-012的授權。

**建議保留DONE，限定budget/referencepolicy，summary仍DEFER。Final verdict：VERIFIED_WITH_MINOR_ISSUES。** 原byte-only PARTIAL、初次fail與historicalprobe logs保留，不改寫。

## Official source cross-check

本輪瀏覽primarysources，Groq文件的context131072/output65536與profile吻合；這不證明servertemplate與reference相同。[Groq model specification](https://console.groq.com/docs/model/openai/gpt-oss-20b)。固定revision存在於官方OpenAI model repository：[Pinned assets](https://huggingface.co/openai/gpt-oss-20b/tree/6cee5e81ee83917806bbde320786a8fb61efebee)。
