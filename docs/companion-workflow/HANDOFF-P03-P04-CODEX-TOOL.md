# 交接：CP-P03／P04 與 Codex 工具（Claude，2026-10-23）

**NOT PUSHED**：全部是 `main` 上的本機 commit，沒有 push、沒有遠端 PR。Owner 2026-10-23 試用後回報「感覺沒問題了」。

| commit | 內容 |
| --- | --- |
| `02707ce` `1364847` `d47ecb3` | P03：單一活動停止 API、活動頁、桌寵氣泡 |
| `473b8a6` `778851a` `3e242fb` | P04：背景 owner（`siro.self`）、自己挑題目與排程、研究筆記與「查好了，要聽嗎？」 |
| `7d07dc1` | 網頁打不開回 `NavigationFailed`＋原因（舊網址 `www.cwb.gov.tw` 事件） |
| `d2a654e` | `codex.ask`：Codex CLI（WSL `~/.local/codex`，預設 gpt-6-luna）唯讀、只送任務、雲端開關開才可用 |
| `680f90d` | 她自己的研究會打開 Codex 附的網址，逐條記 supported／contradicted／not_found／unreachable／unchecked |
| `1ea972c` | 排程修正：4b 照抄來源選項清單導致每次被丟；每次 tick 記錄原因到 `siro.log`。此 commit 也意外帶入另一條工作線未提交的 `share` hook 與一個測試（內容未改動，已通知協調者） |

驗證：各 commit 訊息與 `docs/STATUS.md` 的 P03／P04 段落記有測試數；Codex 以真帳號實測一次（18 秒有回答）。`test_gateway_main` 因本環境沒有 `.venv/bin/siro-gateway` 無法執行；`test_capability_product` 能力清單測試為既有失敗。

未做／限制：聊天時檢索自己的筆記（owner 未要求接續）；聊天中的 Codex 回答不核對來源；暫停狀態不持久；`self-notes-shared.json` 不在 DB；qwen3:4b 判定可能錯；「雲端」開關需 owner 自己打開才會用到 Codex。
