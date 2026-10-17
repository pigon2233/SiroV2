# D67 / T08 日常對話長度修正

日期：2026-10-17。使用者反映 SIRO 回覆很長、常生成到上限。先前已有 D63 的截斷失敗標記與 D64 的可取消停止流程；人格提示只有籠統的「簡潔」，沒有日常短答的具體目標。

## 修改

`src/siro/core/memory.py` 現在要求一般聊天直接回答 1–3 句、通常不超過 120 個中文字；背景、例子與摘要只在有幫助時加入。詳解由使用者要求或任務本身決定，避免重述、填字和自行宣布續寫。新增 `tests/integration/test_persistent_companion.py` 合成身分提示回歸。

Ollama 的 512 輸出 token 上限、`done_reason=length` 的 `ProviderOutputTruncated`、partial 文字保留、前端未完成提示、不自動重送及 D64 停止／晚到輸出 fence 都沒有改動。沒有硬截字串或建立自動續寫。

## 驗收

| 證據 | 結果 |
|---|---|
| 本機真 `qwen3:4b-instruct`；候選模式 system+user 格式；合成問題「你可以做什麼？」；相同 seed、temperature=0、`num_predict=512` | 原提示 115 tokens／120 個中文字／4句；新提示 23 tokens／30個中文字／2句。兩者均 `done=true`、`done_reason=stop`。未保存原始 prompt 或回答。 |
| 相關回歸組，來源副本 `5da368adb574` | 首輪 431 PASS／5 FAIL；失敗來自隔離 subprocess 首次編譯 Jieba 所發出的原有 SyntaxWarning。執行正常 compileall 後同一命令 **436 PASS／1既有 Starlette warning／34.73s／exit 0**。未改第三方檔、測試斷言或 warning filter。 |
| 最終精確部署副本 `7f8a0034fb1d` 的 `test_persistent_companion.py` | **5 PASS／0.19s**。 |
| 最終副本靜態檢查 | Ruff check、Ruff format、mypy 兩個受影響檔案均 PASS。 |
| `prepare_ext4.py` | source identity verified；完整 `src` 閉包144檔；`uv sync --locked --all-groups`、source/tests compileall、`cargo build --workspace --locked` 全部 exit 0。 |
| Windows `Start-SIRO.cmd` 正式入口 | `check_final_entry.py` PASS；health healthy、唯一 native PID 80741、模型 `ollama:qwen3:4b-instruct`、body websocket、TTS `local:qwen3-tts-0.6b-base:siro-sweet-b-v1`，沒有在 source 建立私人資料目錄。 |
| 部署後 B 聲線預熱 | 合成台詞經 authenticated speech API PASS，20.616s、3.68秒／24kHz WAV、peak 0.3555、saturation 0；沒有建立 conversation turn、開麥克風或播放喇叭，worker 留 warm。原 D66 WAV／結果另存保留。 |

## 命令與限制

相關測試與副本檢查均在 WSL Ubuntu、專用 Python 3.12 環境執行。寬回歸組使用本機忽略檔 `.siro-data/wsl-setup/check_ext4.py`，首次 Jieba bytecode 處理由 `.siro-data/wsl-setup/prepare_canonical_bytecode.py` 執行；完整首輪錯誤與修後結果分開保留於 `.siro-data/wsl-setup/voice-quality/`。合成模型前後 probe 使用 `.siro-data/wsl-setup/verify_reply_length.py`，只保存 token／字數／EOS 狀態，不保存回覆內容。

一般聊天縮短幅度以單一合成問題證明提示有被模型採納，不代表所有輸入、長篇解說或其他模型都會遵守相同字數。沒有使用私人對話、私人資料庫、雲端 provider 或真人錄音。D64 停止路徑已有獨立真模型證據，本輪沒有改動其程式或重跑完整 `scripts/check`、remote CI；真人長回答體驗仍待使用者試用。

部署來源副本在寫入本報告／狀態紀錄前完成；之後只有文件更新，不改已驗證的 runtime/test code。原 D66 部署保留，可作既有回退點。
