# MEM-03-B：離線候選契約（產品未啟用）

本子任務實作主MEM03必需的內容篩選與候選組裝；只產生短暫私有物件，無DB writer、
模型、網路、scheduler或產品caller。MEM02與主MEM03完整gate保持不變。

## 決策與語義

先尊重「不要記」與既有RT014 explicit ingress，再拒絕敏感／secret線索、引用／假設／玩笑、
更正、第三人與指令注入。只辨識有界單句第一人稱偏好（含不喜歡）、使用者明確確認共同事件、
第一人稱待辦。英文僅涵蓋對應單句語法。不理解或多句／多意圖一律不產候選，不猜指代。
原句＋字元span保留，不把「我」改成SIRO，不補事實；共同事件僅user_report，不能證明工具成功。
這是保守規則基線，不宣稱通用語意理解或完整DLP；不認得的敏感用語仍可能漏判，所以即使
被選中也不可自動持久化、外送或升格fact。正式保存須另有已批准分類／審核與寫入邊界。

## 來源與生命週期

唯一來源入口為UUID＋typed scope→既有MemorySourceGate，強制LOCAL_ONLY目的路由。
不接受caller文字／模型輸出來替換DB。產生後再次revalidate，再交付候選；review時可再次
revalidate並重新由原句計算候選，拒絕改文字、類別、span、期限等偽造物件。
無法把Policy與來源鎖到未來任意寫入；未來採用仍必須在寫入邊界原子重驗。

候選使用既有MemoryStatus.CANDIDATE，但不是已寫入的Memory。固定review_required、
is_owner_fact=false、verified_tool_completion=false、authorizes_memory_write=false。
候選24小時失效，取與來源TTL較早者；這是in-memory審閱物件的期限，不改既有event保存期，
不是持久Memory retention政策。沒有background owner，不以這裡的取消傳遞替代未來cancel/join。
metadata／repr不含原句或source全文；text／source只供可信內部審閱caller，不可直接asdict。

規則版本與內容／來源hash綁穩定candidate UUID，重試不加強人格或轉成新證據。
無Memory／FTS／事件／outbox寫入；source layer的query_only仍有效。真入口尚未提供owner
marker及Policy adapter，現行舊事件仍拒絕，不回填人物身分。
