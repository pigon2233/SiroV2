# MEM-01 — 可撤銷來源與衍生記憶

2026-10-20 Asia/Taipei；DONE／LOCAL_VERIFIED（本卡本機儲存契約）；LOCAL_ONLY／NOT PUSHED。
未完成MEM02–06，不宣稱已交付自動記憶或主動發話。

## 問題、實作與使用範圍

原記憶刪除已沿memory_derivations清除，但更正不會撤銷既有子記憶。
本輪先重現此失敗，並驗證缺少來源snapshot/adopt方法（首輪3FAIL：1既有缺陷＋2缺少入口）。

- 原correct入口現在在同一transaction遞迴將descendants設superseded、新增revision、移除FTS。
  不覆寫歷史文字；delete保持原deleted語意。修復直接作用於現有MemoryService/管理API使用的repository。
- capture_sources擷取typed source bindings：identity/person、parent UUID/revision/hash、event集合、
  captured_at、generator version、policy revision與privacy route；上限32個唯一parent／100個唯一event。
- add_derived在原SQLite writer transaction重驗scope、版本、內容／原event hash、event集合、
  source status、privacy、有效時間、policy revision與父子有效期；來源變更時不留下child/metadata/edges。
  candidate parent不能產生committed child。新child不能形成cycle；lineage深度上限32。
- revoke_source保存event停用tombstone，原子失效所有引用記憶與descendants；重複撤銷回false。
  原event保留作audit，並不是physical purge。重啟／索引重建不重新公開失效記憶。
- 原remember拒絕revoked event；舊T18非綁定consolidator拒絕撤銷來源及曾被刪除／superseded／
  修改過的memory來源，避免以新文字回填已撤銷知識。此保守拒絕可能連同同event的其他候選一起擋下；
  要使用更正後來源應走有parent revision的add_derived，不繞過檢查。
- 檢索檢查derived lineage與撤銷；trusted_lan route同樣不能帶出local_only來源。
  revisions仍可供owner audit，不因來源失效隱藏歷史；facts與browse不回傳失效derived。

這是可信服務使用的library API，不是模型／網頁可自行呼叫的授權API；沒有新增Gateway endpoint或producer。
既有直接remember仍供明確owner操作，不被拿來自動抽取；source snapshot也不是寫入授權。

## schema與相容性

新增016_memory_derivation_bindings.sql，舊001–015位元與checksum未改：
可空edge source_hash、child生成metadata、event撤銷表及查詢索引。
舊edge保留，不捏造歷史hash；更正／刪除仍保守遞迴失效。
真schema15→16升級保留既有記憶／edge/checksum；真schema16 DB拒絕max_schema15的已簽release，
active pointer未產生，DB bytes未改。沒有提高舊manifest上限、沒有部署或操作私人DB。
D76及CONTRACTS本輪附錄在實作前建立；共享STATUS由整合者依本報告納入。

## 可重現驗證

Base：4b901ac3a21f327a984fa9c7d0e8f8b42c60417a。
Branch：codex/memory-mem01-20261020；worktree：E:/coding/股票策略機器學習/SiroV2-mem01-20261020。
使用既有WSL ext4 Python3.14.4／pytest9.1.1；沒有新增依賴、同步venv、下載或重啟使用中服務。
原checkout的語音／Gateway／HTML等8個dirty檔保持，無移交、無複製。

以下從本worktree執行；重現時output須改為新目錄：

```sh
export PATH=/home/pepepig/.local/bin:$PATH
export UV_NO_SYNC=1 UV_OFFLINE=1 UV_PROJECT_ENVIRONMENT=/home/pepepig/.local/share/siro/venv
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/pepepig/.local/share/siro/venv/bin/python \
 scripts/run_acceptance.py tests/integration/test_memory_derivation_bindings.py \
 tests/integration/test_memory_v2.py tests/integration/test_memory_ingress.py \
 tests/integration/test_memory_organization.py tests/integration/test_memory_learning_guards.py \
 tests/integration/test_consolidation.py tests/integration/test_procedural_candidates.py \
 tests/integration/test_sqlite_store.py tests/integration/test_sqlite_restore_validation.py \
 tests/integration/test_operational_cli.py tests/integration/test_release_manager.py \
 tests/integration/test_context_summary.py tests/contract/test_boundaries.py \
 --level L1 --git-executable git.exe --output /tmp/siro-mem01-20261020-02
```

結果：107 PASS／0 SKIP／7既有warnings，43.10s，退出0；regression-receipt.json保存原結果。
此批包含當時22個新專項及85個既有回歸。之後只新增一項actual-schema release gate測試，未改production。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/pepepig/.local/share/siro/venv/bin/python \
 scripts/run_acceptance.py tests/integration/test_memory_derivation_bindings.py \
 --level L1 --git-executable git.exe --output /tmp/siro-mem01-gate-20261020-01
```

結果：最終專項23 PASS／0 SKIP，3.96s，退出0；gate-receipt.json。
23與107有22項重疊，不加總成130；共108個不同案例通過，沒有一次單一108項整批執行。
兩份receipt為base＋dirty來源、執行前後hash相同；測試後只新增證據／計畫進度文字。

檢查：四個Python檔Ruff check/format、mypy PASS；export_schemas --check PASS；
相同四檔detect-secrets＋check_secrets PASS；git diff/staged diff --check PASS。
核心邊界測試通過，沒有Core引用UI／MQTT／OS driver或新增block event loop的I/O。

## 負例與修正紀錄

- 更正後舊descendant仍可檢索的反例已由FAIL轉PASS。
- snapshot內event清單可被替換的反例已由FAIL轉PASS，現在與實際parent event集合再核對。
- 舊consolidator以新文字回填deleted parent的反例已由FAIL轉PASS。
- 開發中曾把visibility filter誤用到revision audit，造成6項回歸FAIL；已移除該篩選並保留audit API。
- 首輪擴大套件103PASS／2FAIL：scripts/start的uv不在WSL PATH；獨立重跑確證uv: command not found。
  指定既有uv PATH／ext4 env、UV_NO_SYNC/UV_OFFLINE後原測試通過；沒有改5秒readiness門檻或測試斷言。
- 格式／型別檢查中的Row Any與import問題已修正，最終檢查通過。

以上均為合成fixture、真SQLite／ASGI／受控子程序；receipt的L1宣告不替代provider／真人L3。
沒有full scripts/check、雲端CI、正式服務soak／真模型／真設備／部署回退演練。

## 限制與回退

policy_revision的當前值由可信caller提供；本卡沒有建立第二Policy owner或替代外部permission交易，
正式撤權入口／設定接線仍需MEM03/05與Gateway owner。capture/adopt/source revoke這三者未暴露新網路端點。
原context extractive summary是可丟棄request view，不寫進這個DB；沒有另造持久摘要庫。
T18 traits／relationships的歷史projection撤銷及輸入批次fingerprint仍屬MEM05，並未由本卡宣布完成。
既有無binding的root memory預設時間檢索語意保持；新衍生採用與lineage檢查才強制來源時效。

schema16資料不得直接以舊library執行；回退先停新producer，使用相容schema16的版本／關閉新功能。
不能revert原始碼後繞過release gate，也不能還原舊私人DB抹掉後續記憶。新schema從未部署正式DB。
source revoke不可逆，誤撤銷需新owner事件／新來源，不能移除tombstone當「重試」。
本輪沒有自動啟用背景學習、沒有更改私人資料政策，也沒有對外傳送內容。
下一張：MEM-02上下文組裝與固定評測，先讀本輪來源綁定接口，不重建RT010/011。
完整commit SHA由最終回覆與git log提供，LOCAL_ONLY／NOT PUSHED。
