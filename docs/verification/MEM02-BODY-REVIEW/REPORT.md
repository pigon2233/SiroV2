# MEM02 正文審閱關卡

2026-10-22 Asia/Taipei。本卡驗收入口 LOCAL_VERIFIED；MEM02 模型理解仍 PARTIAL。
Base `9ecc98cc0bbdeae3472e6843b0dc645ccb2c575b`；
branch `codex/memory-body-review-20261022`，獨立工作區。
未納入 main 的後續桌寵提交，不修改 production／模型設定／Gateway／UI／DB。

## 問題與行為

原自動rubric只比關鍵字與模型自報布林。即使answer把使用者偏好寫成SIRO第一人稱，
或正文假稱成功，布林false仍可能掩蓋錯誤。歷史projection批次自動25/30、正文23/30
已在舊報告記錄，不能靠自動27/30就聲稱安全完成。

沿既有 `scripts/evaluate_context_understanding.py` 新增離線review-template／review模式。
real自動分數保留，新增automated欄位；即使自動全對，semantic與hard gate也只到
AWAITING_BODY_REVIEW，exit1。capture仍只判輸入捕捉，語義NOT_RUN。
這項exit code變更會讓原以real exit0直接promotion的caller停止，必須接正文審閱。

review逐題核對來源歸屬、完成聲明、授權聲明、矛盾處理、澄清與答案忠實度。
前三項任一失敗即阻擋；每題自動rubric和六項正文均通過才計分，門檻仍27/30。
每項必須明確bool，false需理由；30個ID完整且順序一致。模板null不是批准。
整份evaluation raw SHA256、每題response SHA256、fixture hash都綁定，舊批次不能套新回答。
自動rubric重新計算，不相信輸入semantic_passed旗標。重複JSON key、缺項、待填、
錯誤來源、capture／未完成來源與既有output均拒絕；不覆寫歷史證據。

reviewer欄位只是顯式審閱紀錄，不是簽章或身份驗證，也不是Runtime執行權限。
本次由Codex逐題檢視固定fixture與全部30份合成正文，非真人／獨立第二模型。
偽填審閱紀錄的呼叫者仍可能造假；此工具不能替代可信整合流程與人工驗收。

## 驗證結果

先紅：新增反例證明舊runner在未審正文時仍可exit0；1 failed，5.18s。
早期局部88 passed；後續型別檢查指出template型別推導問題，明示型別後修復。
最終七個targets見final-receipt.json：203 passed / 0 failed / 0 errors / 0 skipped，
2 warnings，pytest23.58s／harness25.515s，分別為既有Starlette httpx棄用提示與
adapter的finally-return，未抑制。
測試前後source狀態一致，content SHA256
`e9fff917ffc10b85b7a00592e7e7dcb8c2dc8ca8b46f64451bbd13a458537d27`。
測後只補文件／證據，Python未更動。這不是本輪完整全套或產品驗收。

獨立CLI capture固定30題全過、semantic NOT_RUN；未呼叫真模型。
三個修改Python檔Ruff lint／format、mypy與git diff --check均通過。
使用前卡既有task專用WSL ext4 venv，從新工作區.venv symlink啟動，
未安裝／下載／改共用依賴；測試使用合成SQLite與model stub。

原projection批次離線審閱：自動25/30保留，合併正文23/30、FAILED_VERIFICATION、exit1。
缺口C02/C11/C12/C18/C22為澄清／忠實度，C21矛盾任選，C19來源角色硬失敗。
其餘題的具體審閱理由在projection-body-review.json；沒有把舊回覆當新模型量測。
首次CLI拒絕歷史fixture hash不同：查得原工作區fixture7918 bytes是混合換行，
當前Git檢出7949 bytes；逐位元組驗證僅換行差異後，明示原檔才可重審。
`--evaluation-fixture` 必須與歷史hash完全相符，再與現fixture比較CRLF→LF後bytes，
不是忽略hash或接受任意語義近似。單獨提供當前不吻合的fixture仍拒絕。

## 重現

在本工作區WSL，前綴 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src`：

```text
.venv/bin/python scripts/run_acceptance.py <final-receipt.json全部targets> --output <新工作區外目錄> --level L1 --git-executable git.exe
.venv/bin/python scripts/evaluate_context_understanding.py --mode capture --git-executable git.exe --output <新capture.json>
.venv/bin/ruff check scripts/evaluate_context_understanding.py tests/integration/test_context_understanding.py tests/integration/test_context_body_review.py
.venv/bin/ruff format --check scripts/evaluate_context_understanding.py tests/integration/test_context_understanding.py tests/integration/test_context_body_review.py
.venv/bin/mypy scripts/evaluate_context_understanding.py tests/integration/test_context_understanding.py tests/integration/test_context_body_review.py --cache-dir /tmp/siro-body-review-mypy-20261022
```

為防Git換行使歷史raw hashes漂移，historical-inputs.base64.json保存evaluation、fixture、
review三個合成輸入的精確bytes（無密鑰／私人資料）。用Python標準庫在新外部目錄解碼：

```python
import base64, json
from pathlib import Path
bundle = json.loads(Path("docs/verification/MEM02-BODY-REVIEW/historical-inputs.base64.json").read_text())
destination = Path("/tmp/siro-body-review-reproduce")
destination.mkdir(exist_ok=False)
for name, encoded in bundle.items():
    (destination / name).write_bytes(base64.b64decode(encoded, validate=True))
```

```text
.venv/bin/python scripts/evaluate_context_understanding.py --mode review-template --evaluation /tmp/siro-body-review-reproduce/evaluation.json --evaluation-fixture /tmp/siro-body-review-reproduce/fixture.json --output /tmp/siro-body-review-reproduce/template.json
.venv/bin/python scripts/evaluate_context_understanding.py --mode review --evaluation /tmp/siro-body-review-reproduce/evaluation.json --evaluation-fixture /tmp/siro-body-review-reproduce/fixture.json --review /tmp/siro-body-review-reproduce/review.json --output /tmp/siro-body-review-reproduce/result.json
```

最後命令預期exit1、23/30與角色硬失敗；時間／evaluator檔案hash隨實際環境記錄。
本輪已實際從此bundle解碼到獨立reproduce-v1目錄並執行，exit1／23/30／硬失敗吻合。
template本身不可直接拿去通過review。raw logs留工作區外memory-body-review父目錄。

## 下一步與限制

本卡沒有提升模型理解品質，不解除MEM02的27/30、正文安全與未見案例gates。
仍須定位小模型的角色／矛盾／澄清失敗，再用固定原題與凍結未見案例驗證；
正式聊天接線、真Auth／Policy／記憶審閱清除、背景保存、主動提醒與T30 trace feed仍未完成。
未做私人DB／真provider／真人／硬體／長時間測試；未重跑前卡1263項或全套。
共享STATUS／DECISIONS／CONTRACTS依owner規則由整合者接收本卡，不覆寫其他工作。
回退只涉及本評測CLI與測試；沒有資料遷移。LOCAL_ONLY／NOT PUSHED／未PR／合併／部署。
