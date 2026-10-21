# MEM-03-B：離線自動記憶候選生成

2026-10-20 Asia/Taipei；base d1e7d6b2216dd7d3120dac4b355f72d7bfade587；
branch codex/memory-mem03-candidates-20261020，managed worktree
E:/coding/Worktrees/memory-mem03-candidates/SiroV2。LOCAL_VERIFIED（離線組件）／NOT_WIRED／NOT PUSHED。

## 實際行為與範圍

新增Core MemoryCandidateGenerator，必須由已保存UUID＋typed scope進MEM03-A source gate，
只有通過人物／session／identity／Policy／privacy／TTL／revocation邊界後，才在本機篩選內容。
偏好、明確使用者確認的共同事件、明確待辦可產生審閱草稿；不改第一人稱、不補事實或推理，
保留原句與精確span，source hash／policy hash／revision／generator version與穩定ID可追溯。
episode是使用者回報，不是已驗證的工具結果。candidate不會授權工具、Memory寫入或外送。

不要記與RT014 explicit remember優先分流；引用、假設、玩笑、第三人、含糊指代、更正、
多意圖、敏感／secret線索與控制注入不產候選。不理解的語法不猜。依賴純Python既有標準庫，
無模型／網路／新依賴。source layer僅LOCAL_ONLY讀取，沒有writer、scheduler、UI或產品caller。
原候選status沿MemoryStatus.CANDIDATE；草稿不是已保存Memory，24小時與來源TTL取較早者。
生成後再重驗；交付用最後一次來源檢查時間作草稿起點，時鐘前跳不交出已過期草稿。
review時重新讀來源／Policy並由原句重建，改文字／kind／span／UUID／expiry／version均拒絕。

## 驗證證據

固定64組內容fixture：20正例（10偏好、4使用者確認episode、6待辦），44負例。
初始collection ERROR是新模組尚不存在，不是64個既有漏洞。第一版內容64 PASS。
早期整合62 FAIL是測試工廠漏event type；補齊後又抓到事件type namespace誤填，依既有契約修正，
不是放寬schema。其後130 PASS。加constructor invariants後，首批receipt為276 PASS／1 FAIL：
偽造文字測試在到達重驗前被span長度檢查拒絕；改成等長偽造，確實測到重建防護。
該失敗receipt保留early-regression-receipt.json，沒有把失敗寫成通過。

人工補查混合中英案例，新增6反例全部先FAIL：Unicode word boundary把中文字當word字符，
password／token／secret／api_key緊貼中文時漏判。改用英文標記兩側的ASCII字元邊界，
NFKC與大小寫變體一起測；原64 fixture不改。143專項PASS後再補最後source validation時鐘
前跳案例，最終144專項；沒有用case ID或fixture預期分支來產生內容。

最終[receipt](final-regression-receipt.json)：**284 PASS、0 FAIL、0 SKIP**，pytest 51.21秒，
含來源準備40、MEM01 derivation23、RT014 ingress7、memory v2五項、context理解契約63與邊界2。
這些是L1合成資料＋真SQLite，Policy為注入view；不當成真Auth／provider／L3產品證據。
source before/after完全一致；已保留283 PASS的中間receipt，不與最終批次加總。

命令（既有WSL ext4 Python3.14.4／pytest9.1.1，cache在/tmp，未同步或安裝依賴）：

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src PYTEST_ADDOPTS='-o cache_dir=/tmp/siro-mem03b-regression-cache' /home/pepepig/.local/share/siro/venv/bin/python scripts/run_acceptance.py --output /tmp/siro-mem03b-timebound-regression-20261020 --level L1 --git-executable git.exe tests/integration/test_memory_candidates.py tests/integration/test_memory_source_gate.py tests/integration/test_memory_derivation_bindings.py tests/integration/test_memory_ingress.py tests/integration/test_memory_v2.py tests/integration/test_context_understanding.py tests/contract/test_boundaries.py
```

64內容正反例之外，真SQLite逐一測44個拒絕案例：產生流程前後整DB iterdump hash相同，
不是只查Memory數量。正例同樣不寫DB、metadata／repr不含文字；重試ID穩定。
scope／guest／legacy marker／模型／tool／Policy deny、撤銷／更正／TTL、取消與偽造物件已測。
Source event本身在測試開始前已存在；這只證明候選組件無新增持久化，不宣稱原事件收集已
阻擋敏感內容，也不把合成secret標記當真實credential。

兩個/tmp pytest plugin runtime mutants：繞過review來源重驗→12個負例全FAIL；停用敏感詞
screen→6個混合中英反例全FAIL，均0 collection/error/skip。mutation-results.json含plugin與targets，
不改repo source、未保留可能有原文的pytest輸出／JUnit；只證明能抓這兩種故障，不宣稱完整覆蓋。
它們在最終時間起點微調前執行；微調只影響prepare使用的同hash snapshot時間，不影響這兩個mutant。

Ruff check／format兩檔、mypy scoped兩檔PASS；schema export --check PASS（無schema變更）。
新增五檔detect-secrets scan零finding；全庫scan checker另記補充結果，不以scoped scan代替全庫成功。
沒有跑全套scripts/check／真模型語義／真Gateway／L3，保留七項相鄰套件既有warnings。

全庫補充：detect-secrets scan退出0，但既有check_secrets.py驗證退出1，**全庫密鑰檢查未過**。
1576個未解finding落在36個既有檔案，本卡新增檔均無finding；詳secret-scan-summary.json。
逐檔以git show HEAD:path核對：36檔皆與base blob在LF normalization後相同，但原始bytes
皆不同（本worktree CRLF checkout）；這會影響既有精確bytes allowlist。這不是證明所有
finding都是誤報；未逐一重新審核、未改全庫allowlist或掃描器，也不假稱完整check通過。
本卡沒有引入那些檔案的內容變更，保留原結果供整合者按既有安全流程處理。

## 尚未完成的產品工作

這是本機規則基線，不是通用語意理解／完整DLP；未校準真人誤記率，不宣稱達成<=5%目標。
無持久候選審閱、編輯、拒絕、刪除與關閉UI；無按類型啟用／保存期間、batch100／60秒／
單background owner與前景cancel/join；無原子候選採用／lineage，也未解除MEM02 27/30 gate。
本地規則能漏掉未列敏感說法，因此產生草稿絕不能直接拿去自動保存或外送。
現用入口沒有owner marker／真Policy adapter，仍拒絕舊事件，不為了產候選補造owner。
未來持久採用必須在寫入邊界重驗，不能把本卡返回的snapshot當永遠有效的授權。

主MEM03、MEM04–06與T18／T30產品接線繼續未完成；共享STATUS／PLAN由整合者依本交接更新。
原checkout其他owner仍在修改音訊／renderer相關檔，未觸碰或納入本卡。
回退可移除新模組與新caller引用（目前無正式caller），無DB migration／資料回退。
本機commit SHA由最終git log與回覆給出；未push／PR／merge／部署，原持續目標保持active。
