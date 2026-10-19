# CP-V01 固定鏡頭與動作分鏡

本卡是現況基線與 V02 設計輸入；不新增 production wire schema 或精確活動支援宣告。

鏡頭：640×720、固定正面、整體角色完整可見、不移相機、不拖視窗；角色 root 固定。
主情境 seed 17018；禁止 TapBody 的 sample sound 播放。此 seed 不固定牆鐘／GPU 幀率。

| 段 | entry | loop／觀察 | exit | interrupt | resume |
| --- | --- | --- | --- | --- | --- |
| 待機 | 現有 Idle，保留當前姿態 | 看頭部／呼吸／手臂切換 | 注意到來 | 前景事件優先 | 只恢復有效 Idle，不 replay speech |
| 注意 | body.look x=.65,y=.25 | 頭／眼球靠向目標，不寫 root | 視線回到 0,0 | 表情與停止都可發生 | 從當前 gaze 淡回，不清 affect |
| 說話意圖 | 合成 body.speech | 目前 renderer 忽略，無音訊；不把嘴部變化當真 lip sync | body.cancel | 中止音訊權在 parent；本輪未接音訊 | 新 generation 不應被舊 mouth pin 卡住 |
| 情緒 | happy→F05 | 保持已選 affect，觀察眼／眉與 Idle 交集 | 新情緒接手 | 取消活動不可清 expression | 本輪取消後 F05 仍保留 |
| 停止 | body.cancel | 觀察嘴／呼吸／表情各自命運 | 新說話／活動 | 不調 stopAllMotions | mouth 應由有效 owner 恢復控制 |
| 恢復 | gaze 回 0,0 | 待機仍活躍、F05 持續 | 下個有效意圖 | 過期 callback 不得重播 | 無研究／工具副作用重放 |

主錄製每段 6 次：等待至少 250ms→讀回全部參數→截圖；實際間隔含截圖成本。
總 36 張、首末參數樣本約 24.5 秒；GIF 依真樣本時間配置，不宣稱 60fps 錄影。

補充 mouth 反例：全新隔離頁→angry／F03→等 600ms→讀 5 次（間隔至少 150ms）→
body.cancel→等 600ms→讀 5 次→新 body.speech→等 600ms→再讀 5 次。
對照同一 ParamMouthOpenY 與 ParamBreath，排除整個模型暫停的誤判。

## V02 製作輸入

- 身體、expression、gaze、mouth、breath／blink 分列 mask；六個既有 motion 都寫 42 參數，不可整包套入後宣稱通道隔離。
- 注意／點頭先限頭頸與上身；頭角度合法範圍 -30～30，設計曲線須保守，從當前姿態開始。
- 閱讀只能先作低頭／注視設計；本模型沒有筆記本道具能力驗收，不能說已拿出／閱讀真筆記。
- 步行／坐起／root 位移在現包 unsupported；不把站姿滑行當全身活動。
- entry／exit 初始 0.2–0.6 秒是設計候選，須待真預覽調整；不在本卡稱已自然。
