# FIX-011 — 有界技能執行生命週期

日期：2026-10-11；基準為 HEAD `c1d2d41` 的既有 dirty workspace。D45／修復定義與 RED 先於對應 source 修改。**FIX-011 DONE／VERIFIED：限定 trusted worker lifecycle 修復**；不批准不可信技能或部署。

## A. Current State

修復 trusted-local worker 的輸出洪水、合法大型 JSON 誤拒及 spawn／輸入取消留下程序；沒有增加產品執行入口或正式部署。RI-004 原 D44 待審準備成果維持有效，嚴格 worker 與人工批准仍須各自驗證。

## B. Codebase Memory Status

本輪沒有可呼叫的 Codebase Memory MCP；未重索引、未繞過既有 owner lease、未宣稱圖譜更新。以目前 source、呼叫點和合成反例直接核查，保留原開發工具。沒有讀私人 DB／聊天／WAV／key、運行中服務或模型。

## C. Architecture Findings

既有 bounded process helper 已具有持續 drain／PGID ownership，worker 自己的 spawn／stdin／單次輸出讀取繞過這個生命週期。將原 helper 下移到 adapter，服務保留相容 facade；Core 和 registry 沒有 OS 耦合或第二個 executor。沒有證據推翻原 Runtime Evolution 設計。

独立 review 抓到此次 relocation 的兩個相容缺陷：Gateway 動態 caller 的 private cleanup wrapper 遺漏，以及 UTF-8 replace 將壞 JSON 修成成功。先新增 3 FAIL／1 PASS 反例後修復，原 argv 文字仍容許 replace，worker 使用 strict decode；真正 U+FFFD 保留。另修 supervisor 與 Dispatcher 在外層清理取消時掩蓋 primary ExecutionCleanupError 的局部缺陷；後者是既有 D40 模式，不改完整 package identity。

## D. Implemented Changes

- 原 process owner 移到 `adapters/process_execution.py`，`services/tools/execution.py` 保留型別 identity、入口與 private signal／cleanup caller；float 秒 timeout 保留 manifest 毫秒精度。
- request 使用 offloop 建立的 owned read-only `request.json`，最多 65,536 UTF-8 bytes，拒絕非有限數字；獨立 mount 不污染 package digest。legacy standalone stdin 改有界讀取。
- bwrap 加 PID namespace／die-with-parent，移除重複 session；同一 helper 處理 spawn、shared stdout／stderr drain、逾時與重複取消，收完 owned 程序才回覆。
- request 與 frozen snapshot 清理保留 primary typed cleanup failure；成功結果在 late cancellation 後不返回。原 venv/source mounts、registry、schema、批准、worker concurrency、permissions 不變。

## E. Tests and Verification

| 驗收 | 實際結果 | 證據 |
|---|---|---|
| 原 worker 反例 | stdout/stderr 洪水外層 5.004s 才中止；100k 合法 JSON 誤拒；spawn/stdin 取消留 owned 程序 | synthetic-probes.json；所有 synthetic PID 已收尾 |
| 最初 RED | 5 FAIL／9 deselected／0.51s；不是 14 個全部失敗 | worker-before.log |
| 新局部反例 | primary cleanup error 1 FAIL；UTF-8／private facade 3 FAIL／1 PASS；Dispatcher 1 FAIL | worker-after.log、worker-utf8-before.log、dispatcher-error-before.log |
| 新 lifecycle 最終 | **24 PASS／3.41s**，獨立再驗 24 PASS／3.53s | worker-final.log、worker-audit-final.log |
| 原 process＋UTF-8／facade | 39 PASS／3既有warnings／23.08s | process-owner-tests-final.log |
| 完整離線 | **1,151 PASS／5 real_provider 未選／3既有warnings／132.76s**；保留原1,127 cases、追加24，不與focused重複相加 | full-suite-final.log |
| 靜態 | Ruff lint／format291、mypy226、schema check PASS | lint-final.log、format-final.log、types-final.log、schemas-final.log |
| 保存／精確回退 | baseline252中249不變，只有3個既有檔改動／2個新增；temporary exact5 reverse/check/reapply bytes相同 | preservation.json、rollback.json、verify_source.py、verification.log |
| Secrets | source5個檔零 findings；owned evidence278個逐項核對為記錄的SHA/Git identity，unresolved0，all-files／no network verification | secrets-source.json、secrets-evidence.json、secrets-review.json |

真 bwrap cases 包含 100k JSON、stdout/stderr flood、manifest deadline、fork＋setsid descendants 的 timeout／cancel 消失及 unrelated canary 存活。受控 fixtures 驗 prep/spawn/cleanup 取消窗口與 typed failure，不把 timing hooks 當 OS 壓力測試。legacy stdin 的兩個案例使用合成可信 plugin 的 standalone 入口；不是敵意 host sandbox 驗收。非法 UTF-8 strict decode 在程序已 reap 後執行。

## F. Risk Assessment

輸入 64KiB／非有限 JSON 是明示契約收斂，過去過量輸入現在拒絕；沒有靜默截斷。PID namespace 不支援即拒絕，沒有 host fallback。CPU soft limit、trusted full source/venv mounts、任意 import／fork／exec 仍屬舊可信 profile；本卡不能批准不可信生成技能。collect 與清理有獨立期限，不把 blocked host filesystem IO 或 kernel aggregate RAM 宣稱已達 SLO。semaphore retention 仍為技術債。

## G. Recommended Next Tasks

沿 RI-004 下一個固定 stdlib single-process worker 切片驗 irreversible restrictions、最小 mounts、權限／資源／取消；再接 server-held review、package-bound owner approval、disabled install、explicit enable/revoke 到原 catalog。沿用同一 registry／dispatcher／orchestrator，不設平行狀態服務。

## H. Deferred Work

一般依賴／多程序／其他 OS／aggregate kernel RAM；LLM 任意技能生成、runtime MCP、自動部署及 RI-005 latest-data rollback 仍未驗。FIX-002 有用搜尋、FIX-005 語音速度／人工聽驗、FIX-006 理解品質保持 PARTIAL。RT-011／013／015 已有的 DONE 切片不重做。

## Scope and rollback

精確 source/test 範圍只有三個既有檔（worker adapter、service execution facade、standalone worker）和兩個新增檔（neutral process adapter、lifecycle tests）。文件與 evidence 另外保存。不更改 Gateway/UI、Core、registry、DB/migrations、權限、模型/TTS/Live2D、locks、Rust、scheduler、release 或 launcher。patch SHA256 `402f8c8201e14fe0a73e5d699c7d80b979ae80024b0479ab102f3f6fc659e966`。

回退先停 trusted worker dispatch／drain，再逆本卡精確五檔 patch；演練只在 temporary mirror，保留所有前序 dirty work，不碰 DB／ledger／private files。退回的舊 worker 有已知 lifecycle 缺陷，dispatch 應保持停用，不作 generated-code fallback。
