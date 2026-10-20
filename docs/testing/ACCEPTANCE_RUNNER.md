# 局部 pytest 驗收紀錄

T01-ACCEPTANCE-01 補強既有 scripts/check；不取代全套檢查、不自動宣告 A01–A24 或產品卡完成。
無新依賴，使用既有 Python 3.12–3.14 與已鎖定 pytest。只執行明確指定的 tests/ 路徑或 nodeid。

## 使用

在目前 worktree 根目錄，使用該環境的 Python：

```sh
python scripts/run_acceptance.py tests/test_doctor.py tests/contract/test_events.py \
  --level L1 --output /tmp/siro-acceptance-example-001
```

Windows 可指定尚不存在的本機輸出目錄。WSL 執行時，virtualenv、cache 與輸出建議留 ext4。
使用前自行確認指定測試的副作用、fixture 與外部條件；此工具不是 sandbox，也不自動隔離服務。
不會安裝依賴、下載模型、呼叫雲端、重試或重跑失敗案例；只有所選測試本身的行為。

輸出目錄必須不存在。中斷或失敗後重跑，使用新目錄，不覆蓋上一輪證據。
請勿使用私人對話、真密鑰或錄音作 fixture。pytest 診斷仍顯示於終端；不要把終端內容自動公開。
JSON 不保存 assertion、收集到的測試名稱、原始 stdout/stderr、JUnit 內容或環境變數；明確指定的 targets/nodeid 仍會記錄。
XML 放在私有暫存目錄，正常結束後移除；程序遭強制終止時暫存清理不保證完成。

## 結果判定

| outcome | 條件 | 退出碼 |
| --- | --- | --- |
| PASS | pytest 成功，至少一項測試，無 failure/error/skip，source 未變 | 0 |
| PARTIAL | 有 skipped／預期 xfail，即使 pytest 原本退出 0 | 1 |
| FAIL | 測試失敗／錯誤；意外 XPASS 強制 strict 也算失敗 | 1 |
| NO_TESTS | 零測試或 pytest 退出 5 | 1 |
| ERROR | 缺失／無效 XML、收集錯誤或其他非預期 pytest 退出 | 1 |
| SOURCE_CHANGED | 執行前後 commit、dirty 清單或非忽略檔案內容有變化 | 1 |
| setup failure | 無效 target、非 Git repo、既有輸出目錄、I/O 失敗 | 2 |

沒有 receipt、損壞的 receipt 或非零退出都不能當 PASS。SOURCE_CHANGED 優先於其他結果，
原始 pytest returncode 與計數仍可查；收集錯誤可能記為 JUnit testcase，不能當成正常執行數。

## receipt.json

schema_version=1。記錄 UTC 開始／結束時間、耗時、命令 argv、targets（即所選 fixture 入口）、
profile=selected-pytest、Python/pytest/OS/kernel/架構/CPU 數、原始 pytest returncode 與計數。
執行前後各記完整 commit、dirty bool、status SHA256 及 content SHA256。
content hash 涵蓋 HEAD 到 worktree diff 與所有未忽略的 untracked 檔案，僅保存合併摘要。
不包含 ignored 檔案、外部模型、依賴包或硬體狀態；不保證發現執行期間改了又還原的內容。
輸出應放 repo 外，避免下輪 source hash 包含上輪 receipt，或被誤加入 Git。

--level 只是執行者依 ACCEPTANCE.md 宣告的 L1/L2/L3；evidence_level_verified 永遠 false。
工具無法證明真硬體、真人聽感、provider 真偽或指定次數達標；需另附脫敏人工證據。
command 中 JUnit 暫存路徑正常結束後已刪除；重現時重新執行上方入口及相同 targets，使用新 output。

為避免環境選項只收集不執行，子程序移除 PYTEST_ADDOPTS，固定 strict markers/config/xfail，
不接受其他 pytest CLI 選項；保留測試的正常環境，PYTHONPATH 明確指向當前 worktree/src。
pytest 設定與 plugins 仍是可信任的專案程式，工具不防止惡意測試偽造 XML。

全套 lint/type/schema/secrets/Rust gate 仍走 scripts/check；本卡沒有改 CI 或降低任何 gate。

## Windows worktree 與 WSL Python

Windows Git 建立的 worktree 若在 .git 檔中使用 E:/... gitdir，Linux Git 可能無法解讀。
此時明確指定 --git-executable git.exe（須已在 WSL PATH），不修改 worktree metadata：

```sh
PYTHONDONTWRITEBYTECODE=1 /home/pepepig/.local/share/siro/venv/bin/python \
  scripts/run_acceptance.py tests/test_doctor.py --level L1 \
  --git-executable git.exe --output /tmp/siro-acceptance-example-002
```

未指定時仍使用 git；不可讀取 Git metadata 會以 setup failure 退出，不會聲稱已驗版本。
選用的 Git 執行檔也記在 receipt；路徑含空格時依 shell 規則引用，工具不使用 shell=True。
