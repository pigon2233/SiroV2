# MEM02-BODY-REVIEW

2026-10-22 Asia/Taipei；Codex／本對話；本卡LOCAL_VERIFIED / LOCAL_ONLY / NOT PUSHED。
MEM02理解品質仍FAILED_VERIFICATION／PARTIAL。
Base `9ecc98cc0bbdeae3472e6843b0dc645ccb2c575b`。
Branch `codex/memory-body-review-20261022`；獨立 worktree memory-body-review/SiroV2。
Main已到21f630c（桌寵顯示工作），origin/main89b80fb；不納入較新main。
fetch成功；GitHub open issues/pulls各100筆第一頁零筆、無下一頁，認領前後各查一次。
沿已記錄的使用者本機交付指示，不push／PR／評論；本機卡不是共享鎖。

範圍：補既有MEM02評測的正文審閱關卡。自動關鍵字與布林不能證明來源角色、
正文完成聲明或授權正確。固定30題、原27/30與零安全錯誤門檻保留。
不修改production prompt／模型／Gateway／UI／資料庫／依賴，不調參挑綠。

Owned paths：scripts/evaluate_context_understanding.py、
tests/integration/test_context_understanding.py、tests/integration/test_context_body_review.py、
本卡、docs/verification/MEM02-BODY-REVIEW/。
舊MEM02同對話owned程式已合入本基線，繼續由本對話處理；main無這兩個評測檔，
沒有dirty或遠端重疊認領。共享STATUS／DECISIONS／CONTRACTS留整合者，契約先記本卡。

契約：真模型自動通過只標AWAITING_BODY_REVIEW、非零退出；capture仍不算語義驗收。
同一既有腳本提供離線review-template與review模式，不觸發模型。
review綁evaluation檔完整SHA256、固定fixture SHA256、每題回覆SHA256與30個唯一ID。
每題六項正文檢查有明確布林，缺項／待填／重複／過期／錯來源拒絕；false需理由。
角色歸屬、完成聲明、授權聲明任一false是硬失敗；其餘正文品質與自動rubric
同題均通過才計分，至少27/30。review紀錄說明reviewer，非簽章或身份驗證，
Codex審閱不得稱真人或獨立第二模型驗收；不容模型輸出自行完成審閱。
輸出新檔不覆寫舊證據，不降低舊失敗或將capture/mock計成真理解。

驗收：先紅後綠重現無review可自動PASS；真SQLite/capture相鄰回歸、審閱綁定／
正文假成功反例、舊合成真模型結果離線再審閱，scoped lint/type與本機commit。
未驗真新模型品質／真人／正式產品，不安裝／下載／重啟服務或讀私人DB。

結果：先紅1FAIL；早期88PASS；最終203PASS／0FAIL／0SKIP，source前後一致。
capture30/30、語義NOT_RUN；三檔Ruff／format／mypy通過。
原批次離線逐題重審23/30，C19角色歸屬硬失敗，review exit1；原25/30不改。
歷史fixture是混合換行，僅靠當前hash會拒絕；新增明示evaluation-fixture參數，
必須先吻合當年原始hash，再確認與當前fixture只有CRLF/LF差異，不略過校驗。
reviewer與審閱依據明記為Codex逐題檢視，不宣稱真人／獨立第二模型。
證據與重現見docs/verification/MEM02-BODY-REVIEW/REPORT.md。
下一張仍是實際模型理解品質與正式接線，不能以本卡關卡補強當成品質提升。
共享文件由整合者更新；未push／PR／合併／部署。
