# T15 驗收證據

日期：2026-09-25｜結果：PASS（L1 + Groq L2）

句界緩衝、200 字內分段、Groq Orpheus streaming HTTP transport、speech/subtitle ID、播放 ACK、播放時鐘口型、cancel 與 HTTP 失敗文字降級已實作；JSON tool payload 不會朗讀。合成完成仍保持 queued，只有 playback final ACK 才標記 finished。

Owner 已接受 `canopylabs/orpheus-v1-english` 模型條款。Opt-in 真實測試從 Orpheus streaming endpoint 取得 RIFF/WAV，再交給 Groq Whisper transcription；關鍵英文詞正確回聽，結果 PASS。官方目前只支援英文與沙烏地阿拉伯語，中文維持文字降級，未宣稱中文 TTS。
