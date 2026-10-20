# MEM-03-A — 已保存來源接納邊界

2026-10-20 Asia/Taipei；LOCAL_VERIFIED（唯讀library組件）／NOT_WIRED／LOCAL_ONLY／NOT PUSHED。
完整記憶計畫未完成：MEM02仍25/30未過27，主MEM03候選生成、內容篩選、UI、啟用與MEM04–06待做。
此卡按PLAN獨立拆分，只驗必要來源邊界，不用子任務完成代替完整目標。

## 範圍與基線

Base983012d86dd50419f8bc9dc5cfb5ee3f6d28e27b；branch codex/memory-mem03-source-gate-20261020；
managed worktree E:/coding/Worktrees/memory-mem03-source-gate/SiroV2。乾淨基線建立獨立分支，
原MEM02工作區保留、原checkout八個語音dirty檔不改。fetch與GitHub公開issues/pulls空（無下一頁）
已核對兩次。本機認領不是共享鎖；CONTRACTS／DECISIONS與本卡契約先寫，再新增tests／code。
不改STATUS／Gateway／UI／音訊／renderer／舊Memory程式／schema／依賴／lockfile／使用中服務。

## 實作

core/memory_sources.py提供SourceScope、可信SourcePolicy port的SourcePermission唯讀view、
MemorySourceGate.prepare(UUID,scope,route)與revalidate(snapshot,actual_route)。
預設DENY／未認證／未啟用，只有owner+精確scope+ALLOW+明確allow_preparation+route才讀DB；
ASK不升格批准。讀前／後Policy一致；revision與view hash都綁snapshot，即使revision漏增也偵測變更。
view使用不可變route集合。Caller只能提供UUID，不能把event payload或內容中的allowed flags當授權。

persistence/memory_sources.py於既有SQLiteStore worker transaction讀原events與conversation identity，
驗typed UserTextEvent、table/envelope一致、producer、session/person scope、privacy ceiling、時間/TTL、
MEM01 revocation及舊事件關聯deleted/superseded/revised memory。source hash綁完整event row與session identity。
讀取callback開PRAGMA query_only，阻擋意外寫入；沿Store既有BEGIN IMMEDIATE，仍可能短暫取writer lock。
舊source缺subject_id明確UNBOUND_PERSON，不推測owner；允許來源才返回private source snapshot。
metadata()/repr不含原文；source需留可信內部，不可用asdict泛用序列化丟給log／UI／LLM。
snapshot固定needs-content-review、不是owner fact、不授權Memory寫入或外送，不是Runtime grant。
故障／timeout fail closed，不重試；caller取消傳遞，未新增背景owner、LLM或executor。

## 真實限制與未接線部分

現行IntegratedCompanion建UserTextEvent時沒有subject_id；正例使用明確人物marker的合成新格式。
所以不能宣稱已能自動讀取現有真人事件。未取得Gateway交接前不改該caller，舊資料不回填。
真正owner-auth／Policy adapter須由既有可信入口接線；tests的Policy fake不是實際Auth/Runtime整合。
本層信任Core-owned DB與已保存producer metadata，不能阻擋擁有任意DB寫入權的本機程式一致偽造整個來源。
marker不是歷史作者的獨立身份證明；若其他入口能寫同namespace的UserTextEvent，需先修入口ACL／
可靠attestation，不能直接接此gate啟用候選。不是只填source字串就完成了整個信任鏈。
Policy與DB沒有共同交易鎖；snapshot捕捉後可失效，未來生成器採用前仍需當前Policy與原子DB來源重驗。
to_thread取消不殺SQL thread；只證caller不取晚到結果且此callback無寫入，不代替producer前景join gate。
本層不判Secret／Sensitive或語義可保存內容；原event可能已有敏感文字，本卡不增加保存／log／outbox。
完整秘密收集、內容分類、保存／刪除、候選Review與產品UX仍屬主MEM03，不宣稱完成。

## 驗證

先寫新契約測試，第一次collection因新module尚不存在而ERROR；不是把它說成40個既有漏洞。
初版33 PASS，補Policy讀取競態、TTL邊界／route切換／clock、DB／二次Policy故障、
文字flags不能冒owner、不可變Policy view與意外DB寫入後，最終專項40 PASS（4.82s）。
新來源通過不寫資料：實SQLite全表iterdump hash在prepare+revalidate前後相同。
query_only故障注入實際嘗試UPDATE，得到STORE_UNAVAILABLE／無原文且全DB hash不變。
所有輸入均合成，未使用私人對話DB或真secret。

最終77 PASS／0SKIP／7既有warnings，33.39s，見regression-receipt.json；
包含本卡40項、MEM01來源閉環23、RT014 ingress7、memory v2五項、Core boundary兩項。
與先前40等重疊，不加總。既有明確記住／更正／刪除行為未改。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/pepepig/.local/share/siro/venv/bin/python \
 scripts/run_acceptance.py tests/integration/test_memory_source_gate.py \
 tests/integration/test_memory_derivation_bindings.py tests/integration/test_memory_ingress.py \
 tests/integration/test_memory_v2.py tests/contract/test_boundaries.py \
 --level L1 --git-executable git.exe --output /tmp/siro-mem03-source-regression-20261020
```

兩種runtime mutant由/tmp pytest plugin注入，不改repo source：
忽略原snapshot binding→四項負例FAIL；把unbound/guest一律補owner→三項負例FAIL，mutation-results.json。
只證測試可抓這兩種錯誤，不宣稱完整mutation coverage；不把故障注入當真實已發生漏洞。
無原文stdout／provider payload保存到receipt；mutation只存原因／exit/count，無真用戶資料。

Ruff check/format、三個新Python檔mypy（MYPYPATH=src）PASS；secret scan/check_secrets PASS；
scripts/export_schemas --check PASS。早期mypy六項是測試utility異質kwargs型別，改test-only Any標註；
未放寬production型別。Ruff一處長行已修。沒有新增依賴或忽略全域檢查。
使用現有WSL ext4 Python3.14.4／pytest9.1.1，cache在/tmp；沒有pip/uv同步或模型下載。
未執行全套scripts/check、真Policy／Gateway／provider、L3或正式部署，不能拿SQLite L1當全部L2/L3。

## 交接

本卡read-only source gate LOCAL_VERIFIED；主MEM03及原持續目標保持未完成。
下一步：依完整gate完成內容分類／候選與Review；來源caller人物marker及Policy接線需Gateway owner交接。
MEM02語義驗收與後續MEM04–06不解除。共享STATUS留整合者按本報告納入。
回退只移除本卡source gate與caller引用（目前無production caller）；不回退私人DB或舊schema。
無新migration，不能把這個回退描述為完整正式部署rollback。
所有成果本機commit，完整SHA由git log／最終回覆給出；不push／PR／merge／部署。
