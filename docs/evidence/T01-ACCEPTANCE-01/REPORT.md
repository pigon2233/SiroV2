# T01-ACCEPTANCE-01 — 局部驗收自動紀錄

2026-10-20 Asia/Taipei；DONE／LOCAL_VERIFIED（本卡工具範圍），LOCAL_ONLY／NOT PUSHED。

## 問題與結果

既有 scripts/check 已有完整檢查鏈，本卡沒有重建它。新增 scripts/run_acceptance.py，
把指定 pytest 路徑／nodeid 的執行與機讀 receipt 結合，記錄 source、環境、命令、時序、
證據層宣告與計數。跳過、xfail、XPASS、零測試、收集錯誤、失敗及 source 變動不會回 PASS。
不覆寫舊輸出，無自動重試；JUnit 私有暫存，正常結束後只保留內容摘要與計數。
詳細操作、結果語意與限制見 ../../testing/ACCEPTANCE_RUNNER.md。

## 基線與修改

Branch：codex/acceptance-receipts-20261020。
Base：34860f1d3ac6decf8c8708ea355d89eae9f3aefa（前次本機規範 commit）。
產品來源：origin/main 137a561c3b5f03c27083eeea2cbd7161b3061d2b。
修改：scripts/run_acceptance.py、tests/test_acceptance_runner.py、操作文件、本報告與 receipt、認領文件。
沒有修改 renderer、Core、Runtime、CI、scripts/check、依賴或 lockfile；無安裝／下載。

## 可重現驗證

WSL Ubuntu，Python 3.14.4／pytest 9.1.1，重用 ext4 上既有 venv。
從此 worktree 根目錄執行；輸出目錄須不存在，重現時換新名稱：

```sh
PYTHONDONTWRITEBYTECODE=1 /home/pepepig/.local/share/siro/venv/bin/python \
  scripts/run_acceptance.py tests/test_acceptance_runner.py tests/test_doctor.py \
  tests/contract/test_events.py tests/contract/test_boundaries.py \
  --level L1 --git-executable git.exe --output /tmp/siro-acceptance-T01-20261020-04
```

實際結果：33 passed in 7.67s，runner PASS，退出 0。本卡19＋既有14，沒有 skip。
receipt.json 是該次實際機讀結果；source 為 base＋本卡 dirty，前後 content/status hash 相同。
完成測試後僅追加交接／證據文件，沒有再改 Python 實作或測試；不是 final commit clean checkout 重跑。

```sh
/home/pepepig/.local/share/siro/venv/bin/ruff format --check scripts/run_acceptance.py tests/test_acceptance_runner.py
/home/pepepig/.local/share/siro/venv/bin/ruff check scripts/run_acceptance.py tests/test_acceptance_runner.py
MYPY_CACHE_DIR=/tmp/siro-acceptance-mypy /home/pepepig/.local/share/siro/venv/bin/mypy scripts/run_acceptance.py tests/test_acceptance_runner.py
```

結果：2 files already formatted／All checks passed／Success: no issues found in 2 source files。
git diff --check 與 staged diff --check 通過。

## 負例與修正過程

- 初始19項之前的16項已驗 PASS；最終全選定33包含這些案例，不加總成額外測試數。
- 真 Windows worktree＋WSL Git 起初因 Windows gitdir 不可讀，setup 退出2，沒有 receipt；
  新增 --git-executable 選項，以 git.exe 正確讀取 metadata，沒有修改 .git 指標。
- 第03輪32 PASS／1 FAIL：不存在的 Git 名稱在 WSL 的混合 PATH 回 PermissionError，
  測試原期望 FileNotFoundError；改用明確不存在的絕對路徑，保持產品拒絕發 PASS 的行為。
- lint 初次格式／unused import、型別檢查 ModuleType.__file__ nullable 失敗已修正，最終通過。
- 真 subprocess 負例涵蓋 assertion failure、skip、xfail、strict XPASS、空收集、收集失敗、
  source 由 clean→dirty 與 dirty→不同內容、環境 collect-only 干擾；CLI 驗證0/1/2退出與舊證據保持。

## 限制與交接

只驗本卡工具與選定 L1 相鄰測試，沒有執行 full scripts/check、真模型／broker／renderer／
真硬體／人工／soak／部署回退。--level 為執行者宣告，工具不證明 L2/L3 或 A 卡完整通過。
不替任意測試做 sandbox 或 timeout；強制中斷可能沒有 receipt，這不代表 PASS。
Git hash 不涵蓋 ignored 模型／環境，也不能發現測試期間改了再還原的內容。
JSON 沒有原始測試內容；終端與暫存 XML 仍可能含 fixture 診斷，僅使用合成測試。

docs/STATUS.md 為共享檔，依本輪 owner 範圍延後由整合者更新，以本報告交接。
原 checkout 本輪其他 Agent 繼續 commit 視覺修改；沒有切換、搬移或改動其工作。
下一步可由其他任務沿本入口產生對應測試 receipt；CI 整合與全 A01–A24 gate matrix 不在本卡範圍。
完整交付 SHA 由 git log 與最終回覆提供；本分支無未提交變更後交付，不 push／不開 PR。
回退：git revert 本卡 commit，保留測試報告與使用者資料；不還原或刪除任何產品 DB。
