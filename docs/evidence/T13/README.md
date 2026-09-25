# T13 驗收證據

日期：2026-09-25｜結果：PASS（L1 + local L2）

32-byte big-endian `SRA1` header、PCM s16le mono、20 ms frame 與 16/24/48 kHz 協商已固定於 schema。Python 與 Node 使用同一 golden fixture。`/ws/audio/input`、`/ws/audio/output` 共用 gateway 認證，分離通道並強制每 session 單一 playback owner；ring buffer 對 missing、out-of-order、overflow 回傳明確狀態。

證據：`schemas/audio/frame.v1.schema.json`、`tests/fixtures/audio/frame.v1.json`、`tests/contract/audio_golden.mjs`、`tests/contract/test_audio_protocol.py`、`tests/integration/test_gateway.py`。
