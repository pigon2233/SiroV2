# Haru 實檔盤點

2026-10-18 Asia/Taipei。真 moc3 經本機 Core 讀回；非從 motion 曲線猜模型合法範圍。

Core runtime：6.0.1（100663297）；外層套件：CubismSdkForWeb-5-r.5。
manifest 56/56 檔案存在且 SHA-256 吻合。來源及授權見 asset-inventory.json。

## 參數

42 個參數均為 Core type 0（Normal），數值型。SDK Core 原始檔未複製入 Git。

| 真實 ID | min | max | default |
| --- | --- | --- | --- |
| ParamAngleX | -30 | 30 | 0 |
| ParamAngleY | -30 | 30 | 0 |
| ParamAngleZ | -30 | 30 | 0 |
| ParamTere | 0 | 1 | 0 |
| ParamFaceForm | 0 | 1 | 0 |
| ParamEyeLOpen | 0 | 2 | 1 |
| ParamEyeLSmile | 0 | 1 | 0 |
| ParamEyeROpen | 0 | 2 | 1 |
| ParamEyeRSmile | 0 | 1 | 0 |
| ParamEyeForm | -1 | 1 | 0 |
| ParamEyeBallForm | -1 | 0 | 0 |
| ParamTear | 0 | 1 | 0 |
| ParamEyeBallX | -1 | 1 | 0 |
| ParamEyeBallY | -1 | 1 | 0 |
| ParamBrowLY | -1 | 1 | 0 |
| ParamBrowRY | -1 | 1 | 0 |
| ParamBrowLX | -1 | 1 | 0 |
| ParamBrowRX | -1 | 1 | 0 |
| ParamBrowLAngle | -1 | 1 | 0 |
| ParamBrowRAngle | -1 | 1 | 0 |
| ParamBrowLForm | -1 | 1 | 0 |
| ParamBrowRForm | -1 | 1 | 0 |
| ParamMouthForm | -1 | 1 | 1 |
| ParamMouthOpenY | 0 | 1 | 0 |
| ParamScarf | -1 | 1 | 0 |
| ParamBodyAngleX | -10 | 10 | 0 |
| ParamBodyAngleY | -10 | 10 | 0 |
| ParamBodyAngleZ | -10 | 10 | 0 |
| ParamBodyUpper | -10 | 10 | 0 |
| ParamBreath | 0 | 1 | 0 |
| ParamBustY | -1 | 1 | 0 |
| ParamArmLA | -1 | 1 | 0 |
| ParamArmRA | -1 | 1 | 0 |
| ParamArmLB | -1 | 5 | 0 |
| ParamArmRB | -1 | 5 | 0 |
| ParamHandChangeR | 0 | 1 | 0 |
| ParamHandAngleR | -1 | 1 | 0 |
| ParamHandDhangeL | 0 | 1 | 0 |
| ParamHandAngleL | -1 | 1 | 0 |
| ParamHairFront | -1 | 1 | 0 |
| ParamHairSide | -1 | 1 | 0 |
| ParamHairBack | -1 | 1 | 0 |

注意：`ParamHandDhangeL` 是實檔拼字，不能自行改成 Change。

## 掛載動作

| 群組／索引 | 檔案 | 秒數 | Loop | fade in／out | 聲音引用 |
| --- | --- | --- | --- | --- | --- |
| Idle / 0 | motions/haru_g_idle.motion3.json | 10 | True | 0.5 / 0.5 | 無 |
| Idle / 1 | motions/haru_g_m15.motion3.json | 5.33 | True | 0.5 / 0.5 | 無 |
| TapBody / 0 | motions/haru_g_m26.motion3.json | 4.97 | True | 0.5 / 0.5 | sounds/haru_talk_13.wav |
| TapBody / 1 | motions/haru_g_m06.motion3.json | 4.53 | True | 0.5 / 0.5 | sounds/haru_Info_14.wav |
| TapBody / 2 | motions/haru_g_m20.motion3.json | 6.03 | True | 0.5 / 0.5 | sounds/haru_normal_6.wav |
| TapBody / 3 | motions/haru_g_m09.motion3.json | 4.03 | True | 0.5 / 0.5 | sounds/haru_Info_04.wav |

六個 motion 均寫全部 42 個 parameter channel；「Idle」並不表示只控制呼吸。
TapBody 的 Sound 僅記錄引用，這輪沒有播放或驗證音訊，不可接回第二音訊 owner。
所有掛載 motion 的 Loop=true，不能以完成 callback 作唯一活動終結依據。
模型目錄其他 motion 檔見 JSON hash 清單；未被 model3 掛載者不當作現有可選動作。

## 表情

| 表情 | 寫入 ID／blend／值 |
| --- | --- |
| F01 | ParamMouthForm / Add / 0.27 |
| F02 | ParamBrowLY / Add / -1；ParamBrowRY / Add / -1；ParamBrowLForm / Add / 1；ParamBrowRForm / Add / 1；ParamMouthOpenY / Add / 1；ParamEyeForm / Add / 0.54 |
| F03 | ParamBrowLY / Add / -1；ParamBrowRY / Add / -1；ParamBrowLX / Add / -1；ParamBrowRX / Add / -1；ParamBrowRAngle / Add / -1；ParamBrowLForm / Add / -1；ParamBrowRForm / Add / -1；ParamMouthForm / Add / -2；ParamMouthOpenY / Add / 1；ParamEyeForm / Add / -1 |
| F04 | ParamEyeLOpen / Multiply / 0.8；ParamEyeROpen / Multiply / 0.8；ParamBrowLY / Add / -0.56；ParamBrowRY / Add / -0.56；ParamBrowRX / Add / -1；ParamBrowLAngle / Add / 0.35；ParamBrowRAngle / Add / 0.35；ParamBrowLForm / Add / -0.74；ParamBrowRForm / Add / -0.74；ParamMouthForm / Add / -1.76；ParamEyeForm / Add / 1 |
| F05 | ParamEyeLOpen / Multiply / 0；ParamEyeLSmile / Add / 1；ParamEyeROpen / Multiply / 0；ParamEyeRSmile / Add / 1；ParamBrowLY / Add / 0.32；ParamBrowRY / Add / 0.32 |
| F06 | ParamEyeLOpen / Multiply / 2；ParamEyeROpen / Multiply / 2；ParamBrowLY / Add / 1；ParamBrowRY / Add / 1；ParamMouthForm / Add / -1；ParamEyeBallForm / Add / -0.65 |
| F07 | ParamEyeLOpen / Multiply / 0.89；ParamEyeROpen / Multiply / 0.89；ParamBrowLY / Add / -0.56；ParamBrowRY / Add / -0.56；ParamBrowLX / Add / -1；ParamBrowRX / Add / -1；ParamBrowLAngle / Add / 0.35；ParamBrowRAngle / Add / 0.35；ParamBrowLForm / Add / -0.74；ParamBrowRForm / Add / -0.74；ParamMouthForm / Add / -0.46；ParamTere / Add / 1 |
| F08 | ParamEyeLOpen / Multiply / 0.8；ParamEyeROpen / Multiply / 0.8；ParamBrowLForm / Add / -0.33；ParamBrowRForm / Add / -0.33；ParamMouthForm / Add / -1.76 |

Core emotion 現有映射：neutral F01、happy F05、angry F03、surprised F06、sad F08。
F02／F04／F07 在模型存在，但未作新情緒入口或能力承諾。
F02／F03 寫 ParamMouthOpenY，需在 V02／P01 與真音訊 mouth channel 仲裁。

## 支援矩陣

| 活動 | 模型／renderer 現況 |
| --- | --- |
| 待機 | 2 個掛載 loop，renderer 會自行挑選 |
| 注意／視線 | body.look → onDrag；有眼球及頭部參數，需 mask 仲裁 |
| 情緒 | 5 個 emotion 映射，F01–F08 實檔齊備 |
| 說話嘴型 | 有 mouth 參數；目前 body.speech 不驅動模型，不算音訊同步 |
| 點頭／閱讀／揮手 | 有頭／臂參數，但無精確活動映射；待 V02 製作及預覽，不先宣稱支援 |
| 走路／坐起／拿筆記本 | 未取得專屬動作及接地／位移資料，unsupported；外觀全身可見不等於可步行 |
