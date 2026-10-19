# 混合與狀態規格 v0

此文件是 P01 loader 的輸入規格，不是新 wire API。pack metadata 不塞進 extra=forbid 的 BodyAssetManifest v1。

## 值與通道

motion3 是模型單位的 absolute target，非 additive offset。body 白名單：
ParamAngleX／Y／Z、ParamBodyAngleX／Y／Z。以 pack 的 moc3／model3 hash 配對。
眼球 ParamEyeBallX／Y 只在 gaze-cues，須獨立 lease；不得同時對 SDK drag 與 gaze cue 相加。
expression（包括嘴形）、ParamMouthOpenY、呼吸、眼睛開合、眉、衣物／頭髮物理、手臂、root 均不在 body 包。

SDK stock Idle 寫 42 參數，取得 body owner 時應只屏蔽其中 6 個 body 值，不停止全 motion／expression。
body 合成後這 6 個參數的原 head-breath／drag 影響由同一仲裁器決定是否保留；本包已含小幅頭微動，
不可無界累加造成角度飽和。ParamBreath 本身仍由 renderer 驅動，body 不清零它。

## 開始、結束與恢復

1. 套用前驗證 digest／大小／路徑、SDK／模型相容及參數範圍，缺任一白名單 ID 則整個活動 unsupported；保持目前包，不能自行換角色。
2. entry 擷取當前**完成合成後**姿態 p0；0.35 秒內使用 smoothstep：p=(1-w)p0+w*clip(t)，w=3u²-2u³。不能先寫 clip(0) 再開始 fade。
3. 意圖相同且 instance／generation／asset version 不變則保持 phase，不重啟 entry。新 generation 即使 kind 相同也重新驗證有效性，不沿用舊 callback。
4. 主活動一次一個。interrupt 在任意 frame 保存先前 activity／phase、當前 body pose；立刻失效舊回呼；不停止表情或有效音訊。
5. resume 在 0.4 秒內由當前 pose 淡入已保存的 phase（loop 取 modulo duration）。先前已終態／過期就回有效 idle；不能重播已完成工具或語音。
6. exit 是 0.4 秒的動態交接：從當前 pose 到下一有效活動曲線，不是 reset default。nod 結束回上一有效活動。
7. entry／resume／exit 全在 renderer 本地逐幀，不請求模型。暫停 phase 時不可忙等 finished callback；取消／loop 由控制器顯式結束。

pack entry=.35、exit=.4 為資料初值；此次姿態診斷統一用 .4 秒 entry，
因此不宣稱 .35 秒 production entry 已驗。P01 應按 pack 跑逐幀驗收並調整版本，不默默改門檻。

## SDK 接線注意

已核對該版本機 Framework：CubismMotion.create(buffer,size,undefined,undefined,true) 啟用 consistency。
Meta.Loop 不會自動設 instance 的 loop；需 motion.setLoop(pack.loop)，以 getLoop() 檢查。
getDuration() 對 loop 是 -1，不可當作壞 duration；計時用 pack.duration；nod 應是 1.2。
不使用 sample sound 或第二 speech owner。活動終態、過期 generation／callback 防護由 P01 實作，本資料包不能代替它。

## 保留與 fallback

單活動取消只釋放其 body／合法 gaze lease。audio mouth 由有效 owner 接管，不能像 V01 問題永久 set 0。
沒有音訊能量時標示嘴型未同步，不自造嘴巴開合。沒有新包就保留原可用角色。
重連只投影最新有效 activity／phase／affect，不重新開始一次性 nod、不補播音訊；換包在安全點，失敗回舊包。
