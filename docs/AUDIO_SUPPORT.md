# Audio support matrix

| Mode | Input/output | Echo control | Current status |
|---|---|---|---|
| Headset | microphone + headphones | Physical isolation | Device visible; automated fault tests pass; 20 human interruptions pending |
| Speaker | microphone + speakers | Requires PipeWire/WebRTC AEC supplied by the selected client | Device visible; AEC quality has not been measured, so full duplex is not claimed |
| Half duplex | microphone or playback, alternating | Playback is muted while listening | Supported fallback |
| Text | no audio device required | N/A | Always available; used when STT/TTS fails |

The audio coordinator cancels player, TTS and LLM work on speech onset. A generation number rejects late audio and buffered frames after cancel or reconnect. Groq Whisper is the verified remote STT. Groq Orpheus is wired as an English/Arabic TTS adapter but remains unavailable until the account administrator accepts its model terms. Audio sent to Groq can be retained for abuse monitoring for up to 30 days unless the account has Zero Data Retention enabled; users must opt into remote speech processing.
