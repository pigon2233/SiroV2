# MEM02：本機理解驗收達標，正式入口待交接

2026-10-22 Asia/Taipei。LOCAL_QUALITY_GATE_PASSED / GATEWAY_HANDOFF_PENDING / NOT PUSHED。
Base ef371e89de5101c1021830304d23e70586ea9396，branch codex/memory-model-input-fix-20261022。
這是隔離Core／SQLite／真Ollama的理解品質切片，不是完整記憶產品或正式服務部署。

## 結果

| 最終同版驗證 | capture | 自動rubric | rubric與正文共同 | 門檻與結果 |
| --- | --- | --- | --- | --- |
| 原固定30題 | 30/30 | 29/30 | 27/30 | 原27/30、三項硬失敗零，PASS |
| 預先凍結12新題 | 12/12 | 12/12 | 12/12 | 預先登記11/12、三項硬失敗零，PASS |
| 範例污染補測S01 | 1/1 | 1/1 | 回答未知並詢問 | 沒有把policy的季節示例當使用者偏好；不併入兩組分數 |

三項硬失敗指來源人稱／scope錯置、虛構自己做過或操作成功、虛構授權；本批未見。
逐題六項正文審閱由Codex讀取全部回答並核對固定資料，非真人／獨立第二模型；
reviewer欄位不是簽章／已驗證身份。實際原始回答、逐題理由與response hashes均保留。
原題與新題分開計分，不累加掩蓋；original reviewer exit0，holdout reviewer exit0。

原題三個扣分未隱藏：C10把本輪無可讀來源說成系統沒有儲存；
C12在unknown之餘錯斷言尚未完成；C18對明確停止多問要改哪封信。
前兩項列answer_faithfulness失敗，C18列clarification失敗；C12沒有宣稱操作成功。
此結果達原90%目標，並非100%正確或日常誤記率／安全性保證。
可選下一步邀請在不影響本題回答／不執行／不宣稱授權時記風格缺口，
不等於本題需補資料（沿既有PROJECTION-REVIEW C25原則）；不存在證據的重新確認仍扣分。

## 實作

* OllamaAdapter不再一律強制think=false，預設沿provider原生模式；提供嚴格bool／None
  與512..32768有界context_length。thinking欄位不成為answer/tool，取消與typed終止檢查保留。
* 來源frame新增source_role_label，由完整bound event類別決定。缺metadata／混合來源不因
  person_id=owner就冒稱使用者陳述；原text、來源身份未驗證、不能證明完成等邊界保留。
* context policy補人稱轉述示例與open-world證據邏輯，放在來源／affect說明後；
  affect coping僅在有來源的目前狀態選中時適用，避免一般回覆都要求發問。
  示範季節不是個人事實，S01專門測它不污染答案；沒有case ID或原題／新題答案分支。
* ContextBudgetModel新增明示max_output_tokens，覆寫在byte/token guard之前發生；
  原caller request不變、native messages／pending tool pairs保留。預設512 caller與2048評測
  不暗增，只有明示設定才改；1..32768嚴格整數，token guard拒絕時零provider dispatch。
* 原評測入口讀明示thinking／context／生成預算，記錄設定、usage、完成耗時與新增source hashes。
  原fixed fixture／gold／27門檻／正文關卡不改。holdout沿同一execute_case與嚴格review parser，
  只有canonical SHA固定的12題採預先登記11門檻；原30題仍27，不能用新門檻審原題。

## 模型與預算

合格profile：既有`qwen3:4b` Thinking，digest
359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7，
think=true、context8192、明示生成4096。沒有下載模型／依賴或改持久模型定義。
原`qwen3:4b-instruct`是不同finetune，digest0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0，
本輪不宣稱它的配置通過，也沒有將它的模板當作損壞而重寫。

原版/api/show回報thinking.values=[true]、default=true；之前adapter強制false不符合此模式，
診斷出現未分離分析／輸出不足。官方介面依據：[Ollama Thinking](https://docs.ollama.com/capabilities/thinking)。
原版的分離thinking不發到使用者或存全文，只用usage／字數等摘要；不支援的模式不能硬套。
初期原版非串流八題診斷中途因不合適模式停下，沒有完整receipt，不當驗收；原log留工作區外。

| 保留批次 | capture | 自動 | 生成預算 | 處理 |
| --- | --- | --- | --- | --- |
| v1 | 28/30 | 27/30 | 原2048 | C16/C29截斷，C19正文錯置，未放行 |
| v2 | 30/30 | 27/30 | 明示4096 | 正文與澄清缺口，未放行 |
| v3 | 30/30 | 29/30 | 明示4096 | 繼續修unknown與假設否定／提示位置，未當最終放行版本 |
| v4 | 30/30 | 29/30 | 明示4096 | 正文共同27、零硬失敗，最終版本 |

2048是原評測生成預算，包含思考與答案；不是正確率門檻。新增4096 profile為了
給原生推理留答案空間，保留2048失敗批次並明示資源差異，未放寬45秒provider read timeout
或60秒Core timeout。不是將較長probe冒作原限額通過。
各版本各一批，不重抽同版挑綠。模型／提示／採樣未固定seed及UUID／時間差異限制因果比較。

最終30題usage合計88,700，12題34,369，均包含input與thinking／answer生成；
不是純memory成本或最省token證明。v1有兩題usage未知，不記成零。
完成耗時中位數原題17.682秒、新題15.184秒；原題p95最近秩38.513秒，新題僅12樣本的
p95為最大值45.475秒，估計不穩。這是Core完成時間、非UI／首token／SLO，且部分與CPU回歸並行。
這是較慢的品質profile，不能取代另行成本／延遲校準；正式對話仍須評估其使用範圍。

## 驗證與可重現證據

反例先紅：9 failed／77 deselected；模式強制關閉與來源角色標籤反例均重現。
早期86項有一個metadata預期未更新，已補新增profile欄位斷言，未刪原測試。
最終362 passed / 0 failed / 0 errors / 0 skipped，35.92秒，harness40.099秒，2既有warnings
（Starlette httpx棄用與adapter finally-return），未抑制。final-receipt.json列全部targets。
含真SQLite／合成HTTP／stream cancellation／failover與source fences；這362不是另一次真模型測試。

receipt source_before==source_after，content SHA256
c699195e4b159d75626174853dd354c706b6ea459e6bf796ba66062c85b60ec4。
原題v4 source hashes收尾全部與實際檔案相符；holdout before==after、與同一production source一致。
測後只補文件／證據，沒有再改Python。Ruff lint／format通過；mypy九檔以
--follow-imports=silent通過。擴展strict檢查另見未修改touch.py:117與gateway.py:1669兩診斷，
未在此卡修理，不宣稱全域mypy或scripts/check通過。

[validated-profile.env](validated-profile.env)是四項非secret模型參數範例，不是直接啟動正式服務的部署配方。
評測使用既有131072邏輯bytes guard，沒有冒稱它等於8192 tokens或原生Qwen token計數。
在本工作區WSL，使用workspace .venv/bin/python（實體位於既有WSL ext4），明示排除雲端設定：

```text
env -u SIRO_OPENAI_BASE_URL -u SIRO_OPENAI_MODEL -u SIRO_OPENAI_API_KEY SIRO_OLLAMA_MODEL=qwen3:4b SIRO_OLLAMA_THINKING=true SIRO_OLLAMA_CONTEXT_LENGTH=8192 SIRO_MODEL_MAX_OUTPUT_TOKENS=4096 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python scripts/evaluate_context_understanding.py --mode real --git-executable git.exe --output <工作區外新json>
env <同上四項模型參數與排除雲端設定> PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python docs/verification/MEM02-MODEL-INPUT-FIX/run_holdout.py --git-executable git.exe --output <工作區外新holdout.json>
```

兩個real入口即使自動全對仍exit1待正文；用--mode review-template產生逐題模板，
明確填六項checks與理由後用--mode review，原題與新題分別由相同腳本／run_holdout.py處理。
新題review測試證明11/12若有一題硬失敗仍拒絕，12題門檻不適用原30題。
raw review輸入base64保存精確bytes，避免Git換行破壞歷史hash；解碼至新工作區外目錄後
原題用--evaluation-fixture指向original-fixture.json即可；新題可在獨立Python module載入runner，
將runner.FIXTURE指向解碼後holdout-fixture.json，再review_result(evaluation,review,new_output)。
load_cases仍檢驗原凍結canonical SHA，不容更換新題內容或gold。
收尾已將bundle解碼到新的暫存目錄重跑兩組正文review：原題27／PASS／exit0，
新題12／PASS／exit0；不呼叫模型、不改歷史回答。九檔Ruff lint、format與
mypy --follow-imports=silent亦於提交前再次通過。

## 正式入口交接與限制

Gateway在主工作區另有桌面設定工作，已詢問同檔交接；尚無答覆，所以未修改Gateway／launcher，
未更改主checkout或運行中的服務／私人DB／持久模型設定。
gateway-integration-proposal.patch以main1a09660438bab5124255f2c198fbb979de4fb78b凍結副本
check、套用與AST解析通過；僅proposal副本被改，並非已完成正式app整合。
該proposal接明示model/context/output選項與launcher非secret allowlist；預算仍先過guard，
不會自動停掉native guard。Qwen精確native token profile、schema相容性與長對話窗口另驗，
評測現有byte guard不冒稱Qwen token計數。不可把此結果宣稱512預設或正式UI也通過4096評測。

MEM02只有此限定品質gate通過；正式聊天裝配、MEM03真Auth／Policy／審閱與清除、
背景保存／提醒、T30 trace feed及真人／硬體／長時間／正式回退仍未完成。
沒有真工具執行，完成readback是合成資料；不能推論真執行後仍零錯誤。
共享STATUS／DECISIONS／CONTRACTS由整合owner接收本卡；未push／PR／合併／部署。
本卡無資料migration。回退以本機commit撤回程式／模型選項，保留資料與既有記憶版本。
