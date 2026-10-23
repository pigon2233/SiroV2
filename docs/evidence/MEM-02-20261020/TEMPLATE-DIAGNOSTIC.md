# MEM-02：實際模型版本與模板診斷

2026-10-20，base 983012d86dd50419f8bc9dc5cfb5ee3f6d28e27b。
只做合成診斷，未修改模型registry、服務設定、產品程式、fixture或驗收門檻。
MEM-02仍PARTIAL；正式最新結果仍25/30、自動門檻27/30，人工正文檢查仍有缺口。

## 修正的模型判斷

`/api/show` 的GGUF metadata顯示現用qwen3:4b-instruct為Instruct／2507，license連結指向
[Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)。
官方說明此版本只支援non-thinking，不需要enable_thinking=False，也不會產生推理區塊。
因此先前think:true沒有分離推理輸出，不足以診斷為故障；原始Qwen3混合推理版的關閉
推理結尾不適用於這個模型。這修正本輪起始假設，沒有把假設當已證實bug修進產品。

另裝qwen3:4b的metadata為Thinking／2507，指向
[Qwen3-4B-Thinking-2507](https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507)。
兩者FROM blob SHA不同，不能當成同權重的思考模式切換。模型tag名稱本身不足以識別版本。
metadata只是本機檔案自述，沒有重新下載官方權重或完成位元等同性驗證。
完整metadata與blob hash見model-variant-metadata.json。

現用Jinja template和官方Instruct-2507 template文字不相等：多了reasoning_content、
last_query_index處理，完整diff包在template-diagnostic-manifest.json的JSON字串內。
這是需留意的來源差異，不直接證明目前請求被錯誤序列化；沒有自動覆寫模板。

## 12次固定請求診斷

從原固定fixture選C02／C19／C22／C28，每題只capture一次真正Core組裝的request，
沿用原hard_checks；三arm使用相同messages（hash留證）、同模型、seed42、
temperature0.7／top_k20／top_p0.8／2048 output tokens。無expected或rubric送給模型。

| arm | 方法 | 自動rubric |
| --- | --- | --- |
| chat | /api/chat，think:false | 2/4 |
| raw | /api/generate raw:true，明確ChatML角色與換行 | 2/4 |
| raw_nonthinking | raw再加原始Qwen3的空think結尾 | 1/4 |

三arm皆未修復C02含糊刪除指代、C22尚未執行測試卻多問結果；加結尾讓C28假設情境退步。
人工補充：C19 chat回答「你喜歡」，兩個raw arm答「我喜歡」，自動rubric三個皆放行；
再次證明關鍵字與模型自報欄位不能取代正文歸屬檢查。C28 raw_nonthinking正文有疑問句
卻needs_clarification:false，也被原rubric拒絕。完整原答見template-control-diagnostic.json。

固定seed也不保證跨API／cache／GPU kernel的位元可重現；C19的差異不作因果結論。
此小樣本不是30題驗收，也未涵蓋tools或長對話序列化。raw serializer刻意拒絕tool history，
只供診斷，不可替換正式adapter（沒有產品取消／budget／工具協定等完整契約）。

## 重現與檢查

在本worktree，使用既有WSL ext4 Python／httpx，不新增依賴或模型：

```text
wsl --cd /mnt/e/coding/股票策略機器學習/SiroV2-mem02-20261020 env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/pepepig/.local/share/siro/venv/bin/python docs/evidence/MEM-02-20261020/template_diagnostic.py /tmp/NEW-template-diagnostic.json
```

輸出路徑須不存在；本次原輸出/tmp/siro-mem02-template-control-20261020.json，12次皆stop完成、
沒有獨立thinking欄位。Ruff該腳本PASS；git diff --check PASS。未改產品程式，未重跑產品回歸。
腳本／fixture／評測器與結果SHA256留在manifest；合成SQLite使用TemporaryDirectory並清理。

結論：拒絕補空think結尾作為修復方向。繼續原上下文歸屬／衝突與自動記憶計畫，保留理解
品質gate；不將本診斷或已有來源層組件當成整個記憶功能已完成。LOCAL_ONLY／NOT PUSHED。
