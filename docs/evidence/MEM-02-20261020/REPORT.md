# MEM-02 — 上下文接線、來源fence與理解評測

2026-10-20 Asia/Taipei。PARTIAL：Core接線與確定性硬gate LOCAL_VERIFIED；
真模型27/30語義gate BLOCKED_CONFIG。整個持續目標保持active，MEM03–06未完成，
不以capture或mock回覆把理解能力標DONE，也不繞過此依賴直接啟用自動記憶。

## 變更與真實caller

CompanionCore原本把完整user句子交exact all-terms檢索；「那我喜歡喝什麼」找不到
「我喜歡喝無糖烏龍茶」。本輪先重現4個FAIL（中文檢索、cloud working資料洩漏、
checkpoint後更正未阻擋dispatch、tool continuation來源刪除未阻擋），再實作修復。

- MemoryService.recall_context使用有界Unicode詞／中文二三字片段，最多12terms/query、
  最多3個query；只有追問cue才回退最近兩個user話題，不用assistant/tool輸出作owner事實。
  同一SQLite檢索先篩identity/person/privacy/時效/lineage，再OR比對，最多5個記憶。
  原recall預設all-terms保持。這是lexical語境召回，不宣稱真正語義指代解析或embedding。
- ContextEvidence為typed/source-backed資料，分開scope/revision/kind/status/confidence/
  source IDs/有效時間，authorizes_execution=false。超過1024字只傳前後excerpt並標示省略，
  不剪裁當前request/system/goals/pending native pairs；原budget guard仍可拒絕整體超限。
- sourced context packet在既有assemble_prompt／CompanionCore使用，不是孤立helper。
  prompt明說current correction優先、舊任務不等於新批准、assistant/tool文字不證明owner事實、
  多個指代候選時應澄清、unknown不等於completed。runtime observation與legacy working以JSON data呈現。
- MEM01 snapshot在選取時交易核對expected Memory，再於ConversationEngine完成start_turn/
  checkpoint後、真正model.stream前重驗hash/revision/event集合/route。
  變更則FAILED／ContextSourceChanged、零provider dispatch；不重試工具或模型。
- tool continuation不重做user記憶查詢，從owned首個system packet讀既有來源binding重驗；
  native assistant/tool pairs、call IDs與順序保持。owned packet不能跨session/identity/privacy重用。
  舊無packet的手工library history仍沿既有trusted-caller路徑，不當成本輪新binding驗證證據。
- WorkingMessage現在帶privacy；cloud排除local-only working與durable memory，
  即使legacy caller省略或傳錯memory route，實際cloud model route仍優先。
- pre-dispatch已cancel時，不呼叫連CancellationToken都不理會的model；此反例先FAIL再PASS。

沒有修改Gateway/HTML、語音、renderer、schema、依賴或lockfile。原正式服務與私人DB未改。
Gateway現有IntegratedCompanion→Core caller可使用此實作；沒有部署或合併到使用中的checkout。

## 固定30組評測

tests/fixtures/context_understanding.json固定30個唯一ID，含中文指代／多候選、刪除撤銷、
來源更正、local-only/person/identity隔離、過期／未到期、assistant推測、假設／引用、
新話題／返回舊目標、最新更正、偏好衝突、來源prompt injection，以及native tool
unknown/pending/readback-completed。全部是合成資料，不是私人對話／真設備紀錄。

scripts/evaluate_context_understanding.py提供：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/pepepig/.local/share/siro/venv/bin/python \
 scripts/evaluate_context_understanding.py --mode capture --git-executable git.exe \
 --output /tmp/siro-context-capture-new.json

# 只有已有授權模型配置時使用；不要把key放在CLI或貼入聊天。
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/pepepig/.local/share/siro/venv/bin/python \
 scripts/evaluate_context_understanding.py --mode real --git-executable git.exe \
 --env-file /path/to/existing/authorized.env --output /tmp/siro-context-real-new.json
```

每個case走真Core/SQLite/context/repository。capture model只記request並回固定標記，
semantic_passed永遠null、semantic_status=NOT_RUN；30/30只證明input hard gates。
real模式才呼叫既有OpenAI-compatible或Ollama adapter，保留model/profile、fixture及source hash、
結果與rubric失敗原因。只有合成input，2048 output-token budget、原byte budget守住，
HTTP錯誤停止後續case，不自動retry或換provider；output必須新建，不覆寫舊證據。

設定可來自process環境或明確指定檔案：SIRO_OPENAI_BASE_URL/MODEL/API_KEY，
或SIRO_OLLAMA_MODEL（及評測器可選SIRO_OLLAMA_BASE_URL；預設沿既有adapter本機位址）。
同時有完整cloud設定與local設定時優先沿用cloud profile，不在失敗後偷偷fallback。
profile僅記model/protocol/host，不記key、headers或env檔內容。

本輪capture 30/30 PASS；source/permission硬gate未失敗。real嘗試退出2、BLOCKED_CONFIG、
complete=false、0 cases／0 provider請求，見兩份evaluation JSON。工作區.env.local/.env/
.siro-data/config.json/config.json不存在；Windows與WSL的既有模型env均未配置（只檢查bool）。
已向使用者詢問既有設定檔路徑或本機endpoint/model，沒有要求貼key，仍待回覆。
固定rubric是可重現的結構化回答檢查，不等於無限泛化能力；即使未來達27/30，
仍須檢視失敗／矛盾與真人體驗，不能以格式正確推論模型全面理解。

## 驗證證據

Base 259fddacb9c585de3c5c4a7ae3ac6a111539cd00。
Branch codex/memory-mem02-20261020；worktree E:/coding/股票策略機器學習/SiroV2-mem02-20261020。
使用既有WSL ext4 Python3.14.4／pytest9.1.1；cache在/tmp，無安裝／下載或venv同步。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/pepepig/.local/share/siro/venv/bin/python \
 scripts/run_acceptance.py tests/integration/test_context_understanding.py \
 tests/integration/test_conversation.py tests/integration/test_persistent_companion.py \
 tests/integration/test_session_restore.py tests/integration/test_integrated_companion.py \
 tests/integration/test_memory_ingress.py tests/integration/test_memory_v2.py \
 tests/integration/test_memory_derivation_bindings.py tests/integration/test_context_budget.py \
 tests/integration/test_context_summary.py tests/contract/test_boundaries.py \
 --level L1 --git-executable git.exe --output /tmp/siro-mem02-regression-20261020-02
```

114 PASS／0 SKIP／7既有warnings，74.54s；regression-receipt.json。
之後只在評測器新增既有Ollama配置支援／2個配置測試，production沒有再改，
最終專項44 PASS／0 SKIP／1既有warning，6.64s；final-scope-receipt.json。
另外cloud conversation switch五項PASS／0 SKIP，5.89s；cloud-switch-receipt.json。
數量有重疊：44與114重疊42，5項switch不重疊；不加總成163。未跑一次單一121項套件。
測試後只追加精確synthetic model識別字的scanner pragma與交接／證據文件，未改執行邏輯。
所有capture測試均不被算進27/30理解分數。

七個本次Python檔Ruff check/format、明確當前src的mypy PASS；schema export --check PASS；
七檔＋固定fixture JSON的secret scan/check_secrets PASS。
scanner一度把測試用synthetic-existing-model字串判成Base64 entropy，精確allowlist該行，
未改全域規則。D77/CONTRACTS在修改前記錄，git diff/staged diff --check PASS。

完整mypy檢查302檔有2個環境診斷：whisper_worker.py缺faster_whisper，現有ignore[import-untyped]
因此也被判unused。該檔未修改，在259fdda基線的同檔重現相同2個診斷；沒有放寬ignore或假稱全綠。
只查部分檔案時曾因已安裝editable path指向原checkout造成mypy誤讀舊src；改以MYPYPATH=src/
明確本次source清單重驗通過。未執行全套scripts/check／遠端CI／真模型或L3。

中途113PASS／1FAIL為cloud NO_SOURCE原體驗說明被新版packet覆蓋，已恢復原說明而非刪測試。
最終114的原斷言通過。原24項Core/session/native整合也通過，但與114重疊不加總。

## 交接與後續

本輪是進展，不是整個持續目標完成。MEM02保持PARTIAL，需實際既有模型跑30case並審核27/30 gate。
未滿依賴前不把MEM03自動記憶或MEM05/06標已啟用。其他owner的Gateway/HTML/音訊dirty仍未接手。
共享STATUS留整合者由本報告納入，持續目標不縮成只做capture。
本機commit、不push、不PR、不自行merge。source回退本輪commit，保留schema16與最新私人DB；
沒有部署，所以不把source回退等同正式部署rollback。完整SHA由git log／最終回覆提供。
