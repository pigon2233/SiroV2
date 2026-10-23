# T18/T30 本輪實作決策

2026-10-20，既有契約缺陷修復，不新增公開網路API或schema。
原6項PASS；新增8項合成反例7 FAIL／1 PASS。

T18：run key 必須綁原identity；candidate source必須獨立，驗證於start前；
trait引用的三個獨立來源必須實際存在events，同一transaction核對再寫projection。
Relationship本已有unknown-source拒絕，保留原行為與回歸。
T30：重複trace UUID不可視為獨立成功；巢狀dict/list/tuple統一遞迴脫敏；
候選狀態固定candidate（DB本已有CHECK）；保存同workflow採明確ON CONFLICT(workflow_hash)
DO NOTHING，保留第一份審閱資料，不覆寫既有候選，不吞其他constraint錯誤。
不宣稱這些修復已解決語義參數化、跨scope學習或產品自動蒐集。

產品檢視：新增獨立唯讀CLI，讀既有DB中的T18 run與T30 candidate metadata，
不migrate、不寫入、不輸出原文／fixture／source IDs、不enable/install。
命令提供有界列表，私人原文檢視仍走現有受控記憶API；不用CLI繞過授權。
Gateway/static被其他工作占用，不能接管；聊天接線／前景控制／設定開關留明確整合gate。
共享DECISIONS/STATUS由整合者根據本檔與REPORT更新。

新增兩項T18反例：直接commit可跨run identity寫入；全域candidate key會令另一identity的同來源候選被誤去重。
修復：commit transaction先驗run owner；新output在原key未占用時沿用舊格式；只有跨identity衝突時才使用identity-scoped key；
相同identity讀取舊key仍可去重，無schema migration、不重寫既有output。
此修復不代表已提供多使用者產品模式，只維持資料結構應有隔離。
