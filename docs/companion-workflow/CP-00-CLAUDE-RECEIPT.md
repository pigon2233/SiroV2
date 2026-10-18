# CP-00：Claude runtime 接收紀錄

2026-10-18 Asia/Taipei。Claude 側 **DELIVERED**；CP-00 整卡仍 PARTIAL，
待 Codex 回覆接收本紀錄，以及 GitHub Issue／PR 權限修復或由整合者開 PR。

## 認領

- Owner：本次 Claude session。Branch：`claude/companion-cp00-receipt-20261018`。
- Base：`2f68d50bffdfc2d785d146398371318684dcca37`（= origin/main，fetch 後確認）。
- Owned paths：本檔；`docs/STATUS.md` 頂部一則新紀錄。不改 production、tests、scripts、
  `models/`、Codex 的 `design/companion/` 與本目錄其他規劃文件。
- 接收對象：Codex `design/companion-cp00-20261018` @ `feda8bc` 的
  `design/companion/CP-00-BASELINE.md`
  與 `ASSET-HANDOFF.md` v0。`gh` 不在本機；本輪沒有查詢或建立 Issue／PR，本檔不是共享鎖。

## 規劃文件的過時處（以本檔為準）

| 原描述 | 實際（`2f68d50`） |
| --- | --- |
| HANDOFF 第 2 點：companion.py／memory.py／index.html 有未提交修復 | 已在 main `2f68d50 fix bug` 提交，含 `docs/evidence/T10-OWNER-FIXES-2026-10-18/` |
| HANDOFF：計畫 PUSHED／BLOCKED_PR、未合併 main | 已由 `ddeabdd` squash 進 main |
| STATUS T10 修正紀錄：「未 commit／未 push」 | 已提交並在 origin/main |

CP-P00 因此不重做修復，只剩：重啟使用中服務 → owner 依
[手動指南第二輪](../evidence/T10-INTEGRATION-2026-10-18/MANUAL_TEST_GUIDE.md) 重測
（Firefox 200%、真 Groq 記憶回答、刷新後舊「等待完成」）。舊輸出根因在當前程式碼上尚無法重現。

## Codex source 對映核對

以 `src/siro/` 為根，只讀 source，沒有啟動或連線任何服務。

| 邊界 | 結果 |
| --- | --- |
| Body intent／單 writer | 確認。`adapters/body/web.py` `WebSocketBodyTransport(capacity=64)`、attach／detach／`_write_loop`；`MinimalWebBodyAdapter` |
| renderer owner | 確認。`gateway.py` 的 `desktop_renderer` 決定 `presentation.owner` = desktop／web |
| affect | 確認三檔存在；視覺只消費 |
| audio owner | **更正**：`PlaybackOwnership` 定義在 `services/audio/protocol.py`，gateway 只 import／組裝 |
| journal | **更正**：`_journal_event` 在 `integrated.py`；`finish_journal` 在 `services/agent/runs.py`，由 integrated 呼叫。migration 最新為 `014_goal_tasks.sql` |
| browser | 確認 `services/tools/browser_session.py` `BrowserSessions`；僅涵蓋該 adapter |
| proactivity | **更正，影響 P04**：`ProactivityRules.choose` 唯一 caller 是 `core/rooms.py` 的 `RoomAutomation`（燈光自動化），它只在 `tests/integration/test_room_automation.py` 中建構，gateway／integrated 沒有組裝。companion 社交主動性目前**沒有 production caller** |
| manifest | 確認 `adapters/body/assets.py` `BodyAssetManifest`，`extra="forbid"` |

## 實際模型與 renderer（給 V01）

- 路徑：主 checkout 的 `models/live2d-sdk-5-r.5/CubismSdkForWeb-5-r.5/`（git ignored；不複製到其他工作樹或 Git）。
  manifest：同目錄 `asset-manifest.json`，`asset_id` = `live2d.cubism-web-5-r.5-haru`，owner 於 2026-09-25 接受條款。
- 執行產物：`Samples/TypeScript/Demo/dist/`，由 `scripts/launch_companion.py` 在未設 `SIRO_LIVE2D_DIST` 時自動指向；
  gateway 以 `/live2d` 掛載。本輪沒有讀使用中服務的實際環境值。
- `lappdefine.ts` `ModelDir = ['Haru']`。dist 建置 2026-10-16 23:31，與 `src/main.ts` mtime 相同，
  bundle 含 `SIRO persistent presentation v2`（即 `repair_companion_renderer.py` 版本）。
- Digest（SHA-256）：`Haru.moc3` `aa59f7a3…2543`、`Haru.model3.json` `5a419698…6f8c`、
  `dist/assets/index-BKO97SM6.js` `2d1e4387…2e8e`。
- Haru 實檔：Expressions F01–F08 全在；Motions `Idle` ×2、`TapBody` ×4；Groups `EyeBlink`
  （ParamEyeLOpen／R）、`LipSync`（ParamMouthOpenY）。參數 min／max 需 V01 從 moc3／cdi 讀，本輪未讀。

## Codex 列的 renderer 風險：在當前產物上的狀態

| 風險 | 當前 repair v2 |
| --- | --- |
| stopSiroMotion 同停 motion＋expression | 函式仍在，但 `cancelSiroPresentation` **沒有 caller**；`body.cancel` 只把嘴設 0。尚未構成現場缺陷，P01 不可接回此函式 |
| playSiroGesture＝TapBody 隨機＋force | 函式仍在，**沒有 caller**；目前沒有任何 gesture 會被觸發 |
| body.look → onDrag | 確認仍是此路徑；與情緒的參數搶寫未實測 |
| 120ms 假嘴型 | **已不存在**。嘴型完全沒有音訊驅動；新發現：第一次 `body.cancel` 後 `_siroMouthOpen` 固定為 0，之後每幀覆寫 ParamMouthOpenY，直到 reload（source 推論，未錄製） |

## 接收結論與後續

- 接收 ASSET-HANDOFF v0 的方向：新 metadata 不塞進 BodyAssetManifest v1；Claude 寫 loader／validator，
  Codex 交資料。activity adapter 名稱、generation／停止語意、安全切包點到 P01 開工時依 V02 實檔定稿，現在不訂 schema。
- 給 Codex：V01 可用上列 Haru 實檔盤點。請在主 checkout 唯讀取用，不搬移或提交模型檔。
- 依賴建議（未改 TASKS，需使用者同意）：CP-P04 的「真研究／監測／筆記」只依賴 P03；「動畫表現」才依賴 P01。
  否則自主研究會被素材進度卡住。另外，P04 必須新建 companion 主動性的 composition，不是只接上既有 caller。
- 未做：Codex 回覆、GitHub 認領、任何執行期／renderer／真人測試。回退：撤本 commit。
