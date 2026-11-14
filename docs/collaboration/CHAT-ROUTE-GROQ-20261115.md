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
