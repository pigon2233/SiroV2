# T14 驗收證據

日期：2026-09-25｜結果：PASS（L1 + Groq L2）

Energy VAD、1 秒 partial、silence/max-duration endpoint、語言提示、device-disconnect 與單一 user turn 已實作。短句、長句、靜音、低能量背景噪音及拔除皆有 deterministic 結果。Groq `whisper-large-v3-turbo` 使用官方 transcription endpoint；以 OpenAI Whisper repository 的 `jfk.flac` 真實送出並正確辨識關鍵句。

命令：載入 ignored `.env.local` 後，以 `GROQ_API_KEY` 執行 `tests/real/test_speech_providers.py::test_groq_whisper_transcribes_openai_public_fixture`，結果 1 passed。金鑰、原始使用者錄音與回應未寫入 Git。
