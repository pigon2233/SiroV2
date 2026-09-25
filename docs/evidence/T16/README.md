# T16 驗收證據

日期：2026-09-25｜結果：L1 PASS，L3 BLOCKED-EXTERNAL

speech onset 會清除 playback 並取消 player/TTS/LLM；generation fence 拒絕 cancel/reconnect 後遲到的 audio。100 次 completion/cancel 競爭與 reconnect 舊音不復活測試通過。STT/TTS/device faults 均保留文字模式。`docs/AUDIO_SUPPORT.md` 明列 headset、speaker、half-duplex 與 text 支援狀態。

尚缺 A08 的至少 20 次真人打斷，以及 speaker AEC 品質量測；因此不宣稱全雙工或完成 L3。
