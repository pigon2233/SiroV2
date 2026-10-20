# CP-P01（VRM renderer 部分）：動作、表情、視線與嘴型接線（2026-10-20）

**結果：PARTIAL。** VRM renderer 的接線與驗收項都有自動測試與真模型取樣；owner 尚未在重啟後的桌寵上實際試用，
因此不標 DONE。本報告只涵蓋 VRM renderer（`renderers/vrm/`）與它用到的頁面訊息，不涵蓋 Live2D 路線。

- Branch：`claude/vrm-renderer-m1`（本機，未推送）。說明文件：`renderers/vrm/BEHAVIOUR.md`。
- Core 的 body 協定（`body.emotion`／`body.look`／`body.gesture`／`body.speech`／`body.cancel`）不變；
  Core 不知道骨骼或像素。頁面 → renderer 只多了 `siro.speech.mouth`（播放中的音量）與 `siro.view.focus`（聊天框位置）。

## 驗收對照

| 要求 | 做法 | 證據 |
| --- | --- | --- |
| motion／expression／gaze／mouth 不衝突 | 每幀固定順序：片段 → 保持狀態 → 生命層 → 情緒姿態 → 互動反應 → 臉；表情取 Core 情緒、互動反應、片段表情三者混合；嘴型只來自實際播放的音訊 | renderer 測試：情緒＋手勢＋說話＋取消同時進行；`expression('aa')` 只隨音訊開合，停止送就閉合；v2 訊息被忽略 |
| 相同意圖去重 | 同一情緒重送不重播反應；同一回覆（generation）最多一個說話手勢；同一手勢播放中不重啟 | `你好呀!` 後同 generation 的 `嗨` 不再揮手 |
| loop／interrupt 不死等完成回呼 | 一次性片段結束交回 idle；保持狀態（坐下、看筆記）與散步由自己的時鐘換段；被拎起、被叫住可在任何時刻打斷 | 坐下後手臂不會變 T（held pose 回歸）；拖曳→dangle→land→idle；看筆記中 Core 手勢先等 |
| asset 缺項明示 fallback | 缺片段時那個行為就不做（選單按鈕變灰），缺整個 pack 時退回程序姿勢並在 console 警告；不換角色 | 合成模型（無手指、無多數表情）與真模型都能跑；`activity()` 在 pack 載入前為 null，不會誤判 |
| 停止移動不打斷另一個有效說話 | 散步被叫住只停走路；嘴型與音訊無關於身體動作 | 散步測試；說話中手勢與嘴型同時進行 |
| 回退 | 新表現都在 renderer 內；body.v1 不變，舊 Live2D renderer 與啟動器未動 | — |

## 主要內容

- 取景：載入時取樣每個片段，保留手舉到的最高點；桌寵窗格 360×640（透明區不攔滑鼠）。
- 視線：眼球映射改為水平 28°／垂直 22° 轉滿；優先順序 Core look → 身體動作（東張西望、看筆記、走路）→
  滑鼠／聊天框 → 看著使用者（含依情緒的瞥視與微跳視）。
- 情緒：依 Core 的實際對映與強度決定一次性反應、專屬待機（≥0.45）、姿態、眨眼與節奏；2 分鐘無新情緒回平靜。
- 互動：摸頭、點擊、連戳、拖曳；說話時手勢；閒置時的小動作與坐下、看筆記、散步。

## 測試

- `tests/integration/test_vrm_renderer.py`（12）：協定與嘴型、取景／視線／滑鼠反應、拖曳與筆記、散步、聊天框位置。
- 相關集合 80 PASS；renderer 測試多次重跑穩定（先前兩個依隨機瞥視的相對斷言已改成絕對位置）。
- 真模型（headless Chromium）：揮手與伸懶腰不被切、各情緒姿態、摸頭／被戳／被拎起／落地、筆記本道具、走路都取樣檢查過。

## 限制

- 口型只依音量與音色，沒有音素對應。
