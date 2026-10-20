# VRM M1 — VRM renderer 接上 gateway（2026-10-19）

決策：擁有者於 2026-10-19 選擇角色改走 VRM（three-vrm），取代 Live2D 路線。
本分支 `claude/vrm-renderer-m1` 只做 M1；**未 push**（擁有者明確要求）。STATUS.md 未修改。

## 範圍

- `renderers/vrm/`：three.js 0.169.0 + @pixiv/three-vrm 3.1.0（MIT，lockfile 鎖版本），
  沿用 body.v1 邊界與 renderer ownership v3；不合成語音、不假造嘴型（語音仍由父頁擁有）。
  支援 body.emotion（happy/sad/angry/surprised/relaxed，未知名稱回 neutral）、
  body.look（4 秒後回看鏡頭）、body.gesture（點頭）、眨眼、呼吸、desktop 24 fps 與透明背景。
- `scripts/prepare_vrm_renderer.py`：`npm ci --ignore-scripts` 後把 renderer 複製到
  Git-ignored `models/vrm-renderer`（含 build-manifest 雜湊），並可把擁有者 VRM 註冊到
  Git-ignored `config/body-assets/siro-vrm/`（BodyAssetManifest v1）。
- gateway：`SIRO_VRM_DIST` + `SIRO_VRM_MODEL_MANIFEST` 必須成對設定；模型經 manifest 雜湊驗證，
  由 `/vrm-model/model.vrm` 提供（no-store）。優先序 VRM > Live2D > placeholder。
- launcher：非簽章 release 且兩個本機產物都存在時自動選 VRM，並跳過 Live2D 修復。

## 安裝（擁有者本機）

```
uv run python scripts/prepare_vrm_renderer.py --model "<你的 .vrm>" --license-url https://vroid.com/en/studio/terms
uv run python scripts/launch_companion.py
```

## 驗證

- 新增 `tests/integration/test_vrm_renderer.py` 8 項通過（合成 VRM 1.0、mock gateway 瀏覽器測試）。
- 相關回歸 128 項通過；mypy（gateway.py、assets.py）無問題。
- E2E（`e2e-run.py`）：真 `create_app` + uvicorn + 擁有者模型 `SIRO V2 blender.vrm` + headless Chromium
  （SwiftShader）。結果見 `e2e-report.json`、`e2e-expressions.jpg`：
  - `/` 的 iframe 指向 `/vrm/`；renderer 完成 session 認證並接管 body transport。
  - 五種情緒權重皆達 0.98 以上並回報 `siro.renderer.ready`；look、點頭生效；未觸發 speechSynthesis。
  - 開啟 desktop renderer 後，web renderer 收到 `siro.renderer.detached` 且不重連。
  - 無 console error。fps 數字（5／3）來自軟體 GPU，不代表實機。

## 未做（後續）

- M2 VRM 活動素材（V04 改由 Claude 負責）、M3 動畫管理（P01）、M4 全身桌面（P06）。
- 袖子與帽兜仍需 spring bone collider；直式畫面取景之後在 M4 調整。
