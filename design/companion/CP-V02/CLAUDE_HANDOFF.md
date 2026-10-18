# 給 Claude：CP-V02 可接收資料

分支 design/companion-cp00-20261018；本卡 parent 82fa6c2。實際 head 以 Git log／交付回覆為準。
owned paths：assets/companion/haru-upperbody/0.1.0/ 與 design/companion/CP-V02/。
共用 STATUS／TASKS／DECISIONS 仍由 Claude 整合，本輪沒有修改。

請先讀 README 與 MIXING，再核對 pack-digests、pack compatibility 及實際 caller。
本包不是 production 已接受 schema。請在 P01 做窄 loader／validator，不直接更改 Body v1。
SDK 已真解析 6/6；姿態預覽是診斷合成器，P01 必須補 SDK playback／過渡驗證。

接收後逐項驗：

- 原始 motion3 在真 SDK 播放；stock Idle 的 42 通道只對 body mask 屏蔽，保留表情／音訊 mouth／blink／breath／physics。
- .35 秒 entry／.4 秒 exit 由當前姿態開始；連續閱讀→注意→點頭→說話→原閱讀 phase，沒有回 default 的瞬間。
- 同意圖重送 20 次不重啟 loop；舊 instance／generation callback 在新 turn／重連後被拒絕。
- 循環、中斷及一次性 nod 都能終結；不要等 loop finished callback。
- V01 F03→cancel→新語音 mouth pin 修復並真音訊驗證；取消 body 不停止另一有效前景說話。
- 模型缺 ID／hash 不合／檔案缺失明確 unsupported 或 failed；保持舊可用包，無角色偷換。
- 重新連線不補播 gesture／speech，最新 Core affect 保持；source／asset／config 要同版記錄。

這些是待執行 P01 情境，並未由本卡 production 測試通過。
V01 真音訊／宿主驗證欠項仍保留；使用者已要求先製作 V02 的資料部分，沒有撤銷 gate。
預覽在本機 artifact receipt 路徑；跨機請顯式轉移並驗 hash，尚無遠端圖片儲存連結。
回退：先安全結束新 body lease，保留有效表情／音訊，再停用新 pack；不刪 identity／memory／journal。
