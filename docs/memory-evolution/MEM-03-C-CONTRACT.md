# MEM-03-C：持久候選與明確審閱契約

沿用MemoryStatus.CANDIDATE、memory_sources、memory_revisions及FTS；schema17只加review
metadata及無原文action ledger，不建第二MemoryStore。候選不進正常recall／FTS，approve才commit；
仍是owner statement的episodic記錄，不變成工具readback或客觀semantic fact。

## 權限與交易

MemoryReviewPolicy.lease(scope,operation)是可信裝配提供的既有Policy授權／撤權序列化port，
不是新Policy engine，不從來源旗標或模型payload取得permit。預設無操作／無類型權限。
adapter必須將policy修改與in-flight lease序列化，lease持有到SQLite transaction結束；
核對owner actor／authenticated／scope／revision／expiry／allowed kind。沒有真adapter不能
啟用正式writer；本卡只有注入lease的L1，不能宣稱真auth已驗。allow_preparation只是來源讀權，
不是Memory寫入權，stage／review需要獨立授權。
lease必須也涵蓋相關SourcePolicy變更；SourcePolicy.current在lease內讀取時不得再取同一把
非重入lock造成deadlock。測試adapter使用同lock序列化修改、直接讀不可變view；正式裝配要另驗。

stage經A/B取得原句；writer lock後同一SQL transaction再次inspect event／scope／TTL／撤銷／
hash及草稿語義。approve另重驗舊source Policy fingerprint／期限／原句重建；採用邊界再查DB，
不是只依呼叫前snapshot。Policy不在SQLite，沒有跨系統共同交易；lease adapter是必要信任邊界。
reject／withdraw可移除失效待審項，Memory標deleted並留revision。編輯需先有新可信owner event，
原子撤回舊candidate並stage新candidate，回新ID及replaces連結，不接受任意caller字串替換來源。
拒絕／撤回／批准後，舊source依A既有invalidated規則不能重新自動回填。

批准保存期由可信permit明示（None表示到owner刪除），仍受原source TTL；pending最多24h。
期限不代表SQLite revisions／舊頁／備份已物理purge。retention與purge UI仍待完整產品交付。

## 審閱與取消

scope內list只返回metadata；preview需READ lease及來源／Policy重驗，text repr=False，禁止將
含source／text的物件直接asdict寫log／外送。狀態變更帶expected revision，CAS過期不能復活。
action UUID綁完整命令hash，重試同命令返回state_at_commit，不冒稱是現在狀態；換參數拒絕。
同scope＋READ權限可lookup，action ledger與Memory在同一transaction，不留原文。

開始DB寫入後，取消必須shield＋join worker，之後才離開Policy lease；仍向caller傳遞取消。
caller以action UUID查結果，不能因timeout／取消盲目重送。DB異常報unknown，不假稱沒發生。
這不替代未來background single-owner／batch／foreground cancel-join驗收。

## 相容性與啟用

只新增migration017，舊checksums不改；新建／16→17／重啟／FK／rollback要驗。
合成舊manifest的max_schema15／16必須拒絕17；不改發布門檻或遷移私人DB，未盤點live release manifest。
MEM02 27/30及主MEM03語義／UI／owner opt-in gate保留，L1通過不構成正式啟用。
