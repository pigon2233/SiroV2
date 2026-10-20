# MEM-03-A：已保存來源的唯讀接納契約

只供候選生成前讀來源，不抽取語義、不判內容可保存、不寫Memory／候選、不啟用服務。
MEM02仍25/30未過27；本子任務不是MEM03產品或原目標完成。

## 信任與人物綁定

Core只收UUID、scope、目的route，不能用caller payload替換DB。Policy port由可信應用裝配，
供既有Policy／設定的唯讀view：scope、actor、owner_authenticated、revision、decision、
allow_preparation（預設false）、allowed_routes（預設local）。不是第二Policy engine，不簽grant。
只有owner actor／owner person、精確scope、ALLOW、明確啟用及允許route才查DB，ASK不自動批准。
來源文字裡的JSON／模型allowed宣稱不能設定view。此層不認證WebSocket，也不保護整份已被
可信本機程式任意改寫的DB；真auth／policy adapter待Gateway owner接線。
source／subject marker是可信producer契約，並非DB對歷史作者的獨立身份證明；若其他入口可
寫入同namespace的UserTextEvent，整合者必須先收緊入口ACL或建立可靠attestation，不能直接啟用候選。

自動owner UserTextEvent的subject_id表示可信入口確認的人物scope，不是句子談論對象。
只接已保存source=siro.presentation且subject_id=owner的事件；缺失明確拒絕、不回填。
現行IntegratedCompanion未填subject_id，所以舊資料不會自動被當owner；RT014明確記住功能不改。
Identity按conversations.session_id既有綁定；原event.turn_id不冒稱等於Core後建turn ID。

## 捕捉與重驗

同一SQLite交易查核event schema／table-envelope一致性、conversation identity／session、
person／producer／privacy ceiling、時間／TTL、MEM01 revocation及deleted/superseded/revised memory。
單筆沿既有64KiB event上限；查詢在SQLiteStore worker thread，無資料寫入，仍沿BEGIN IMMEDIATE取鎖。
hash綁完整原event row與session identity，不只文字。讀前／後Policy view須一致，snapshot含revision
及完整view hash；即使revision漏增也偵測view變更。revalidate帶實際route，重讀Policy／DB，
比對完整event與hash。snapshot可隨後失效；未來producer採用前仍須原子DB及當前Policy重驗，
此層不宣稱跨Policy／SQLite／網路有共同交易鎖，也不執行候選採用。

## 輸出限制

拒絕無原文，snapshot repr／metadata不含原文；source只供可信內部caller。
不得把PreparedSource或SourceDecision直接asdict後送UI／log／LLM；需要診斷時只用metadata()。
固定content_review_required=true、authorizes_memory_write=false、authorizes_external_disclosure=false、
is_owner_fact=false。可讀不等於非敏感／可保存／已證實；Secret偵測與語義型別是主MEM03後續gate。
既有event可能已保存敏感文字，本層不增加保存／log／outbox，不宣稱整體收集政策已修好。
取消傳遞、timeout／Policy／DB錯誤fail closed、不重試，無LLM／executor／第二背景owner。
取消不會強制終止SQLiteStore既有to_thread中的SQL，但此讀取callback開query_only，無資料寫入；
不以這項取消測試宣稱完成了未來背景producer的前景搶占／join驗收。
