# CP-V02：Haru 上身動作資料包 0.1.0

2026-10-18 Asia/Taipei。**資料製作／SDK 解析／隔離姿態預覽已交付；整卡 PARTIAL，待 Claude P01 接線及真音訊／自然度驗收。**
使用者本輪指示開始 V02；以 V01 已驗 42 參數基線製作資料，沒有將 V01 未驗音訊與實機 gate 改為完成。

## 可用交付

Runtime 資料：[pack.json](../../../assets/companion/haru-upperbody/0.1.0/pack.json)。
六個原創 motion3：idle、attention、nod、thinking、reading_pose、speaking_pose。
每個檔僅寫 6 個頭／上身 ID；各有 duration、fade、loop／一次性、interrupt／resume 及 hash。
附獨立 gaze-cues.json 與 channel-mask.json。整包 9 個 JSON 共 24,774 bytes，不含模型、SDK、texture 或聲音。

可編輯來源：[authoring-keyframes.json](authoring-keyframes.json)，包括所有時間點與參數值。
Bezier 的時間 handle 為各段 1/3、2/3，值 handle 等於兩端值（smoothstep）；每個節點速度為零。
loop 的首尾值一致；這是曲線連續性，並非自然度 4/5 的評分。

| 活動 | 秒數／循環 | 此包能力 |
| --- | --- | --- |
| idle | 6／loop | 輕頭部／上身微動，呼吸／眨眼保持 renderer owner |
| attention | 3／loop | 向一側偏頭注意；眼球 cues 需注意力仲裁，非自動追人 |
| nod | 1.2／一次 | 小幅點頭後返回先前有效活動，不等待循環 callback |
| thinking | 5／loop | 抬頭微偏姿態，不代表模型有執行研究 |
| reading_pose | 5／loop | 低頭姿態；沒有筆記本道具或真閱讀宣告 |
| speaking_pose | 4／loop | 說話時輕微頭／上身活動，不包含嘴型或聲音 |

步行、坐起、筆記本道具、root 位移、真研究及 audio lip sync 均 unsupported。
保留目前 Haru 身體，不新增身份、情緒或記憶 writer。

## 驗收證據

- [sdk-parse-results.json](sdk-parse-results.json)：本機真 SDK CubismMotion.create 啟用 consistency check，6/6 解析成功；setLoop／getLoop 確認五個循環，nod duration 1.2。
- [data-validation.json](data-validation.json)：逐段 121 點 bounds／finite、metadata point／segment 計數、hash、白名單、loop 值／速度接縫與 gaze 範圍通過。
- [preview-readback.json](preview-readback.json)：真 Haru／Core 6.0.1，暫時診斷合成器預覽 32 張，八個切換起點 delta=0；body 讀回最大誤差約 1.73e-7，其餘參數被該合成器改寫計數為 0；pageerror 0。
- [preview-artifacts.json](preview-artifacts.json)：GIF、接觸表與 32 張圖的本機路徑／hash。GIF 每張 500ms，用來比較姿態，不是真實時間的動作錄影。
- [pack-digests.json](pack-digests.json)：9 個 runtime JSON 的完整 digest／大小。

預覽是「真模型＋資料曲線的診斷合成器」，不是 P01 loader。SDK 對 motion3 做真解析，
畫面則用可編輯 keyframes 依相同 cubic 插值，再在 Core.update 前只覆寫 body mask。
未執行 SDK motion manager 的完整 playback／crossfade，沒有以這批畫面宣稱已整合。

## 邊界與限制

沿用 V01 的 source base 82fa6c2／已驗模型 digest（pack 內完整值）；真服務 SHA／配置未核對。
唯讀使用主 checkout 模型；本輪不修改 production、scripts、desktop、tests、共用進度或既有 dirty TASKS。
不接真 WS／音訊／provider、不占 renderer lease、不重啟服務，診斷 browser／HTTP server 已關閉。

第一輪診斷錯用 isLoop() 查詢，實際 SDK 為 getLoop()；修正診斷呼叫後 6/6 通過，沒有改 SDK 或門檻。
V01 取消後 mouth pin 未修，不能由本包解決；真音訊、反覆中斷／重連、SDK mixer 實播、實機自然度仍待驗。
資料未公開授予新再散布授權；原創數值與專案資料依 repository 授權規則，Haru／SDK 仍依既有 Live2D manifest 條款。

接線規格：[MIXING.md](MIXING.md)；逐項交接：[CLAUDE_HANDOFF.md](CLAUDE_HANDOFF.md)。
撤回本卡 commit 即回退資料交付；正式啟用後須先在安全點退出新活動再切舊包，保留表情與有效音訊。
