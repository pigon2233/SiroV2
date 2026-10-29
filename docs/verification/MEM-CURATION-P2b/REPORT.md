# MEM-CURATION-P2b：收緊記憶整理判斷並量測

日期：2026-10-29。狀態：LOCAL_VERIFIED（合成案例）/ 仍為 dry-run，未改任何記憶 / NOT PUSHED。
計畫：[CONSOLE-REDESIGN-PLAN](../../collaboration/CONSOLE-REDESIGN-PLAN.md) §5 D1、§8。

## 改了什麼

`src/siro/core/memory_curation.py` 判斷提示由 v1（P2a）改為 v2，紀錄多一個 `prompt` 欄位：

- 判斷規則照 Mem0 `mem0/configs/prompts.py` 的 `DEFAULT_UPDATE_MEMORY_PROMPT`：同義就是 NOOP（Mem0 的 NONE），
  同主題但多了或變了細節就是 UPDATE，互相矛盾就是 DELETE，並翻譯了 Mem0 的披薩／板球／工程師例子。
- 重要度照 Generative Agents（arXiv 2304.03442 §4.1）的錨點：1 分是刷牙、鋪床，10 分是分手、考上大學。
- SIRO 專屬規則（依使用者「大量毫無價值的記憶」）：主題重疊的「我自己查過…」研究筆記選 UPDATE；
  研究筆記重要度通常 1–3。**這兩點是設計決定，不是外部來源。**

## 量測方法

- `cases.json`：30 個合成案例，涵蓋同義重複、補細節、矛盾、全新、字面相似但無關、研究筆記同題／新題、瑣事、
  多筆相近記憶。每個案例列出可接受的操作與必須引用的既有記憶編號。不含私人資料。
- `evaluate.py`：v1 與 v2 各跑每題 3 次，模型為本機 `gemma4:e4b`（Ollama，temperature 1，所以每次結果可能不同）。
- 原始輸出：`evaluation-gemma4-e4b.json`、`evaluation-gemma4-e4b.log`。

## 結果（90 次判斷／版本）

| 指標 | v1 | v2 |
| --- | --- | --- |
| 正確（操作可接受且引用正確） | 73 | **89** |
| 該新增卻被丟掉（可接受只有 ADD，卻判 NOOP／DELETE） | 0 | 0 |
| 不該刪卻判 DELETE | 0 | 0 |
| 判斷不出來（UNKNOWN） | 0 | 1 |
| 研究筆記重要度分布 | 3–9（多數 7–8） | 1–3（多數 2） |

v1 的 17 個錯誤：同義重複判成 UPDATE（9 次）、NOOP 沒引用編號（5 次）、同主題研究筆記判成 ADD（3 次）、
瑣事判成 ADD（2 次，與前項部分重疊）。v2 唯一錯誤是 `many-neighbors-2` 一次輸出無法解析，已記為 UNKNOWN，
沒有被猜成操作。

`evaluate.py` 內 `lost_new` 欄的定義較寬（可接受集合含 ADD 就算），會把 `trivial-2` 判 NOOP 也算進去；
上表「該新增卻被丟掉」用的是嚴格定義（可接受集合只有 ADD），由同一份原始資料重算。

## 限制（照實記錄）

- 案例和 v2 提示是同一人寫的，研究筆記規則與案例題型相近，**有過度貼合風險**；30 題樣本小。
- 研究筆記重要度下降主要是因為提示直接寫了「通常 1–3」，不能當作模型自己判斷變準的證據。
- 只測 `gemma4:e4b`。相近記憶仍用字元雙字組相似度，沒有向量檢索。
- 正式服務要重啟後才會改用 v2；在此之前監控頁看到的仍是 v1 的判斷。

## 下一步

P2c 才會真的套用判斷（UPDATE 合併、DELETE 設 `valid_to`、NOOP 不寫入），需要先用真實資料讓使用者看 v2 的試跑結果，
並保留 revision 讓每筆變更都能還原。
