# CP-V04：完整活動資產（VRM 路線）

2026-10-20。**LOCAL_VERIFIED／擁有者目視驗收待確認**。分支 `claude/vrm-renderer-m1`，只有本機 commit，
沒有推送。角色在 2026-10-19 由擁有者改走 VRM（three-vrm），本卡由 Claude 負責；原本 Live2D 版的
「Editor 往返 gate」改為 VRoid → Blender → VRM 的往返（見 [MODEL.md](MODEL.md)）。

## 交付

| 項目 | 位置 |
| --- | --- |
| 可編輯模型工程 | [`model/siro-v2.vroid`](model/siro-v2.vroid)＋產生鏈與雜湊 [MODEL.md](MODEL.md) |
| 衣物碰撞（袖子、帽兜、繩子、衣襬） | `scripts/tune_vrm_springs.py`（測試 `test_spring_tuning_assigns_body_colliders_to_clothing_chains`） |
| runtime 動作包（37 個 .vrma） | `assets/companion/siro-vrm/0.1.0/pack.json`＋各片段 |
| 動作的可編輯來源 | `scripts/build_vrm_mocap.py`（動捕重定向＋疊加層）、`scripts/build_vrm_motions.py`（骨架與舊手調片段）；動捕原檔以 sha256 釘住、按需下載到 repo 外的快取 |
| 目視檢查工具 | [`contact-sheet/`](contact-sheet/)：在註冊的擁有者模型上逐格渲染每個片段 |
| 目視證據 | [`evidence/`](evidence/)：正面、3/4 側面、步態側面、揮手特寫 |

每個 pack 條目都有 entry／exit 姿勢、loop、interrupt、接地方式、root motion（步行另有
`root_speed_mps`）、crossfade、duration、sha256、來源與授權。channel 由 pack 的 `write_mask` 規定：
只寫 humanoid 骨骼，不寫表情、視線、眨眼與 spring bone（`test_clips_are_vrm_animation_with_hips_root_and_seamless_loops`）。

## 任務卡要求對照

| 要求 | 狀態 | 證據 |
| --- | --- | --- |
| rig | 完成 | VRoid humanoid＋衣物碰撞；renderer 每幀只透過 humanoid 驅動 |
| 左右步態、起停、轉向 | 完成 | `walk`（左右對稱、1 秒循環）、`walk_start`、`walk_stop`、`turn_step`；側面圖每格都看得到交替落腳；`test_walk_holds_the_planted_foot_still_at_the_pack_speed`、`test_lead_ins_hand_over_to_their_loop_exactly`。桌寵視窗往左或往右走由 P06 依方向轉身 |
| 坐、起 | 完成 | `sit_down`→`sit_loop`（坐地抱膝）→`stand_up`；`test_sitting_rests_on_the_floor_with_planted_feet_and_exact_handovers` |
| 注意、揮手 | 完成 | `attention`、`wave`、`bye`、`bow` |
| 筆記本拿出／閱讀／收起 | 完成 | `notebook_out`→`notebook_read`→`notebook_away`；筆記本道具由 renderer 畫（不在片段裡） |
| 關節、衣物不破圖 | 目視 PASS（軟體 GPU） | 37 個片段 × 6 格 × 正面與 3/4，共 444 格在縮圖解析度下逐一看過，沒有看到關節反折、穿模或外套撕裂。抬手過頭會撕外套，除了 `wave` 以外都有測試擋住（`test_upper_arms_stay_below_overhead_where_the_jacket_tears`） |
| 左右身份一致 | PASS | 單一 3D 模型，各角度同一份網格與貼圖；3/4 圖可看出 |
| 真步態有腳步，不是站姿平移 | PASS | 見步態側面圖；P06 讓視窗以片段記錄的步速移動，著地腳不滑 |
| 可編輯工程＋runtime 包 | 完成 | 見上方交付表；髮夾的限制見 MODEL.md |
| 舊模型保持可選 | 沿用 | gateway 優先序 VRM > Live2D > placeholder；`test_vrm_takes_precedence_and_live2d_stays_mounted` |
| binary 有合法來源與取得方式 | 完成，附非商用限制 | 下一節 |

## 授權

- `wave`、`bow`、`bye`：Bandai Namco Research Motion Dataset，**CC BY-NC 4.0，只能非商用**。
  擁有者 2026-10-20 決定：沒有商用計畫，保留這三個片段。日後若要商用，要先換掉這三個。
- 其餘 34 個片段：取自 three.js examples r169 的 `Xbot.glb`，動作是 Adobe Mixamo 的動畫，
  適用 Mixamo 條款，不是 three.js 的 MIT 授權（pack 原本寫成 MIT，已更正）。Mixamo 允許用在自己的
  作品裡；把重定向後的 .vrma 放進公開 repo 是否算單獨散布，沒有查證，若 repo 要公開請先確認。
- 模型：擁有者自製（VRoid Studio），VRM meta 為 `personalNonProfit`、不允許再散布。

## 已知的小地方（不是 blocker）

- `wave` 是動捕原樣的大幅揮手：手會舉過頭頂、前臂越過頭頂上方（見 `evidence/wave-close-front.jpg`）。
  外套沒有撕裂，但看起來比較像「用力打招呼」。若想要只在臉旁邊揮，可以改疊加層壓低上臂，需要擁有者決定。
- 證據圖是 headless Chromium＋SwiftShader 渲染，只播片段本身（沒有 renderer 的呼吸、視線、情緒層）。
  真機 GPU 的畫面與自然度要擁有者實際看過才算驗收。

## 重現

```
# WSL，repo 根目錄；需先 prepare_vrm_renderer.py 註冊模型
UV_PROJECT_ENVIRONMENT=$HOME/.venvs/sirov2 uv run python design/companion/CP-V04/contact-sheet/render.py \
  "$PWD" /tmp/v04-sheets "$(readlink -f "$(which chromium)")"
UV_PROJECT_ENVIRONMENT=$HOME/.venvs/sirov2 uv run python scripts/build_vrm_mocap.py   # 動作包重建，.vrma 位元組不變
```

回退：本卡只新增 design 檔與 pack 的說明欄位；.vrma 片段沒有改。撤掉本卡 commit 即可，不影響人格、記憶或 renderer。
