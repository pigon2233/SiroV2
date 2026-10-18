# CP-P01：Haru 上身活動接線（2026-10-18）

**結果：PARTIAL。** 程式接線、單元／契約／整合測試與真 renderer 逐幀讀回都完成；
使用中服務尚未重建 renderer 或重啟，真人自然度與真音訊嘴型也還沒驗，因此不標 DONE。

- Branch：`claude/companion-p01-20261018`，base `2f68d50`（origin/main）。
- 素材：Codex `design/companion-cp00-20261018`@`f58c4d4` 的 `assets/companion/haru-upperbody/0.1.0/`，原樣帶入、未修改。
- 規格：該分支的 `design/companion/CP-V02/MIXING.md`、`CLAUDE_HANDOFF.md`；契約變更見 DECISIONS D76。

## 做了什麼

| 部分 | 檔案 | 內容 |
| --- | --- | --- |
| 素材包驗證 | `src/siro/adapters/body/visual_pack.py` | 驗結構、檔名、大小、逐檔／模型 hash、只寫 6 個 body ID、段落格式與時間、有限值、必須有 idle；失敗停用活動並保留原角色 |
| 送意圖 | `adapters/body/web.py` | `set_activity`／`stop_activity`；speak 成功後送 speaking_pose（ttl 2–30 秒）；重連只重送無 ttl 的循環活動且沿用原 id |
| 選意圖 | `services/presentation/integrated.py` | 真實 stream 事件 → thinking／reading_pose／idle（見 D76） |
| 提供資料 | `services/presentation/gateway.py` | 啟動時驗包；`GET /v1/body/pack`；`SIRO_BODY_ACTIVITIES=0` kill switch；runtime feature `body_activities` 顯示狀態，gaze／lip_sync 標 unsupported |
| renderer | `scripts/companion_renderer/siroactivity.ts`、`scripts/repair_companion_renderer.py` | 本地逐幀控制器；在 stock motion 之後、breath／drag／physics 之前只覆寫 6 個 body ID；取消時解除嘴型覆寫（V01-D01） |

控制器行為（依 MIXING）：entry 從當下姿勢以 smoothstep 淡入且 clip 從 phase 0 開始；同 id 重送回 duplicate，不重啟；
同類循環換新 id 時保留 phase，舊 id 回 interrupted／superseded；nod 暫停主活動，播完回到保存的 phase，不等 SDK callback；
stop／ttl 到期回 idle，再停一次才交回 stock motion；過期 id 的 stop 回 ignored；pack 或模型還沒好時只保留最新意圖。

## 證據

### 自動測試（mock／合成資料）

- `tests/contract/test_visual_pack.py`：16 PASS、1 SKIP（真 Haru 比對只在有授權模型的本機執行）。
  驗證器 9 種竄改情境；控制器 8 個 Node 情境（直接跑 `siroactivity.ts`）；bridge 嘴型回歸。
- `tests/integration/test_body_activities.py`：6 PASS。adapter 訊息、重連投影、`/v1/body/pack`、kill switch／壞包、真 turn 事件順序。
- 突變檢查：拿掉姿勢擷取 → 2 FAIL；拿掉 nod 保存 phase → 1 FAIL；換回舊嘴型邏輯 → 1 FAIL。都已還原。
- `tests/integration/test_desktop_web.py` 的合成 SDK 補上兩個真 SDK 錨點行（repair 腳本需要）。
- 相鄰回歸（body／desktop／integrated／fence／agent runs／batches）80 PASS。
- 全套 `pytest tests`：2391 PASS／41 FAIL／7 SKIP。40 項在 origin/main 等價工作樹同樣失敗，原因是新 worktree 沒有
  `.siro-data/tokenizers`、`target/debug/siro-runtime` 與 skill worker 環境；`test_gateway_main` 單獨重跑 PASS（負載下計時 flaky）。
  未在已備妥環境跑完整 `scripts/check`。
- 靜態：Ruff check／format、mypy（294 檔）、`export_schemas --check`、`git diff --check` PASS；repair 腳本對真 SDK 副本
  `tsc --noEmit`＋vite build PASS，第二次執行無變更（idempotent）。

### 真 renderer（合成事件，無音訊）

`renderer_probe.py`：真 gateway `create_app`＋`WebSocketBodyTransport`＋scratch 重建的 Haru 5-r.5 renderer，
headless Chrome（SwiftShader），每幀讀 Core 參數。唯一診斷 hook 是 probe 端包住 `Live2DCubismCore.Model.fromMoc`。
`analyze_probe.py` 產生 [probe-summary.json](probe-summary.json)；原始 frames 只在本機（SHA-256 `e40e756c…0483`）。

- 1093 frames、median dt 16.9ms、pageerror 0；表情 F01→F03 後保持，呼吸 0–1 持續變化。
- 時間軸：stock → reading_pose → attention → nod →（finished）→ speaking_pose → cancel → idle → speaking_pose →（ttl expired）→ idle → thinking → stop → idle。
- 10 次切換的第一幀位移都和前一幀的自然步幅相當（例如 attention 0.198 vs 0.129，nod 0.152 vs 0.123），沒有跳回 default 或 clip(0)。
  stock→reading_pose 為 1.233 vs 1.097：stock 動作本來每幀走約 1.2，切換後從擷取姿勢平滑減速。位置連續，但 stock 原有速度被截斷，自然度待真人評。
- 同一 thinking 意圖重送 20 次＋斷線重連重送 1 次 → 21 個 duplicate，phase 不重啟；重連前後最大步幅 0.07。
- 嘴型：取消前後與新語音期間 ParamMouthOpenY 都依 F03 表情維持 1，沒有再被固定成 0（V01-D01 修正）；沒有音訊驅動嘴型。

## 未做／限制

- 已啟用（使用者同意）：主 checkout 的 renderer 以本分支 repair 腳本重建（bundle 與 probe 驗證版相同），
  8000 服務改從本分支工作樹啟動（`.env.local` symlink、沿用原資料目錄／tokenizer／runtime），`/v1/runtime` 顯示
  `body_activities: ready`，live renderer 載入 pack、pageerror 0。原 renderer 備份在本機 scratch。
  此服務跑的是本分支程式，不含主 checkout 中另一個對話未提交的 index.html 修改。
- 真人自然度、桌寵視窗（24fps frame budget）、WSLg／Windows、真音訊、200% 下的表現都還沒驗。
- gaze cue 未套用；lip sync unsupported。speaking_pose 壽命是字數估計，不是實際播放結束。
- renderer 事件（accepted／started／finished…）只 postMessage 給父頁與寫 dataset，後端尚未消費。
- secret gate：`pack.json` 的 11 個摘要已依 D77 精確綁定（[secret-audit.json](secret-audit.json)）；
  `test_desktop_entry_scripts.py` 3 個合成值補 allowlist 註記。detect-secrets＋check_secrets 現為 PASS，gate 測試 63 PASS。

## 回退

設 `SIRO_BODY_ACTIVITIES=0` 立即停用（角色回 stock motion）；或撤回本分支後以舊 repair 腳本重建 renderer。
沒有 DB、migration 或設定格式變更；表情、記憶、人格資料不受影響。
