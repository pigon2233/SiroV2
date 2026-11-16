# CHAT-ROUTE-GROQ-20261115

- Task：一般閒聊可改走 Groq（`SIRO_CHAT_ROUTE=groq`），本機 qwen3:4b 負責短呼叫、敏感內容與備援；Claude 只用於推理。
- Owner：Claude（Remote Control session）；時區 Asia/Taipei。
- 狀態：PARTIAL（階段一完成；記憶隱私腳本為階段二，未開始）。
- 分支／worktree：`claude/chat-route-groq` @ `E:/coding/Worktrees/chat-route-groq`
- Base SHA：335aaa6369e724b162f6ab5cdcf7d6c86aec3fd1
- Owned paths：`src/siro/adapters/models/router.py`、`tests/unit/test_model_router.py`、
  `scripts/launch_companion.py`（只加白名單一行）、`.env.example`、`docs/MODEL_ROUTING.md`、本檔。
- 排除：computer-use 相關檔案、`src/siro/persistence/memory.py`、STATUS 等共享檔。

## 驗證（WSL，共用 venv 未改；PYTHONPATH 指向 worktree src）

- `pytest tests/unit/test_model_router.py`：15 passed。
- 改動檔案 `ruff check`、`ruff format --check`、`mypy`：通過。
- 全庫 `ruff check .`：170 錯誤，與 main 相同（既有）；`ruff format --check .`：19 檔（既有）。
- 全庫 `mypy`：因 `tests/contract/test_ollama_reasoning_options.py` 重複模組名中止（既有，與 main 相同）。
- 全庫 pytest：3550 passed、76 failed。34 個在 main 同樣失敗；其餘 42 個改用 main 的 src
  在同一 worktree 重跑：19 失敗、23 通過。錯誤訊息皆指向以 src 位置推算的環境檔
  （worktree 缺 `.siro-data` tokenizer、`target/debug/siro-runtime`、`.venv/bin`；
  skill worker 子程序走 venv 的主 checkout 安裝），推測為環境差異，非 router 邏輯；
  尚未在完整環境（複製資產或主 checkout 合併後）重跑確認。
- cargo：未跑（本次無 Rust 變更；`scripts/check` 會 `uv sync` 共用 venv，故未整支執行）。

## 遠端

LOCAL_ONLY／NOT PUSHED。使用者自行 push 與開 PR。

## 2026-11-15 補充：既有 ruff／測試失敗

- 環境補齊（WSL 獨立 venv `~/.venvs/chat-route-groq`、worktree 的 `.venv` 連到它、複製 tokenizer 與
  `target/debug/siro-runtime`、PATH 加 `~/.local/bin` 與 Playwright Chromium 的 `chromium` 連結）後，
  完整 pytest：3592 passed、35 failed；其中 30 個重跑全過（環境），剩 5 個：
  `tests/unit/test_computer_use_perception.py` 4 個、`tests/unit/test_undertale_wait_counterfactual.py` 1 個，
  屬 computer-use 範圍，未修。
- ruff check：170 → 2（剩 `tests/unit/test_computer_use_loop.py`，不碰）。commit 7c76c4c。
- `test_vrm_renderer.py` 只改換行；其 14 個測試因未 `npm ci` 被 skip，未實跑。
- mypy：全庫原本在重複模組名處中止。試加 `explicit_package_bases` 後可完整檢查，但出現 196 個既有型別錯誤，
  已撤回該設定，未修。

## 2026-11-15 階段二：記憶隱私腳本（第 5 項）

- `scripts/report_memory_privacy.py`：唯讀（`mode=ro` + `query_only`），依來源事件 privacy 計算等級，
  關鍵字分類 稱呼／喜好／作息／敏感／其他。對 WSL 實際資料庫執行：63 筆有效記憶全為 local_only；
  可升級候選 喜好 3、作息 1、稱呼 0。
- `scripts/promote_memory_privacy.py`：需 exclusive_data_owner 鎖（SIRO 須停止、限 Linux）；逐類 y/s/N、
  最後再確認；敏感類不列出；有 derivation 或 semantic_facts 的記憶跳過。寫入方式：新增 cloud_allowed
  `memory.corrected.v1` 同意事件 + 新記憶，舊記憶軟刪除並記 revision，log 寫 `memory-privacy-promotions.jsonl`。
  未對實際資料庫執行（需使用者親自逐類確認）。
- 測試：`tests/unit/test_memory_privacy_scripts.py` 3 passed；ruff、format、mypy --strict 乾淨。

## 2026-11-16 階段三：閒聊走 Groq 時依記憶隱私決定整輪等級

- 狀態：PARTIAL（程式與自動測試完成；未在實際 SIRO＋真 Groq 上手動驗證；`promote` 仍未對實際資料庫執行）。
- 本次新增擁有路徑（使用者指示）：`src/siro/services/presentation/integrated.py`（`_privacy_for_turn`、
  `_needs_local_memory`、`chat_turn_to_groq` 屬性）、`src/siro/services/presentation/gateway.py`（只加接線一行）、
  `tests/integration/test_chat_route_memory_privacy.py`。仍未碰 `src/siro/persistence/memory.py`、computer-use 與 STATUS。
- commit `2b69b40`：`SIRO_CHAT_ROUTE=groq` 的閒聊先以本機與雲端兩種等級各跑一次 `recall_context`
  （與組提示相同；排除 SELF 記憶的規則相同），本機召回中只要有一筆雲端召回不到（來源非全部
  `cloud_allowed`）就整輪改 `local_only`；檢查例外也留本機。命中 `router._SENSITIVE` 一律本機。
  `SIRO_CHAT_ROUTE=local` 不執行檢查。新增 `ModelRouter.chat_turn_to_groq()`，無本機模型時回 False。
- commit `c928306`：報告逐筆列出不升級的日常記憶與原因（derivation／semantic_fact／revoked）；
  `promote --everyday` 三類一次列入、只問最後 y/N；`--dry-run` 唯讀、不拿鎖、不寫任何東西。
- 對話還原：確認 `recent_session_messages` 以 `run_journal.privacy` 完全相同過濾，走 Groq 那輪拿不到
  `local_only` 回合；既有 `tests/integration/test_session_restore.py`、`test_provider_completion.py` 已覆蓋，
  本次未另寫端到端 candidate 測試。文件寫進 `docs/MODEL_ROUTING.md`。
- 限制：每輪 Groq 閒聊多兩次 SQLite 記憶檢索；只用當句做檢索（不含 recent_users 的追問擴充），
  追問句可能漏判；`affect` 偏好不參與判斷（仍由原本隱私篩選擋住）。

### 驗證（WSL，`~/.venvs/chat-route-groq`）

- 改動檔 `ruff check`、`ruff format --check`：通過。全庫 `ruff check .`：2（與前次相同，computer-use 測試檔）；
  `ruff format --check .`：12 檔（既有）。
- `mypy`：腳本、測試、router 0 錯誤。gateway.py／integrated.py 有 8 個錯誤，用 `git archive HEAD` 取出
  944bb05 版本比對，同樣 8 個（只是行號位移），皆為既有。
- 新／相關測試：`test_memory_privacy_scripts.py` 6、`test_chat_route_memory_privacy.py` 3、
  `test_model_router.py` 16，共 25 passed。
- 全庫 pytest：3627 passed、10 failed、19 skipped（868 秒）。5 個為已知 computer-use／undertale；
  其餘 5 個（activity_monitor 真瀏覽器、operational_cli、provider_completion length、runtime_boundary、
  tool_catalog computer.execute）單獨重跑 13 passed，判定為負載下的不穩定，非本次改動。

## 遠端（階段三）

LOCAL_ONLY／NOT PUSHED。未 push、未開 PR、未合 main。
