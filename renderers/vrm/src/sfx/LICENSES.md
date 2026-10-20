# Gesture sound effects

All files: mono, 44.1 kHz, 16-bit WAV. Processing for every file: stereo downmix, highpass 120 Hz,
lowpass 9 kHz, leading/trailing silence trimmed, 3 ms fade in, 40 ms fade out, gain set towards
-30 LUFS with sample peak capped at -12 dBFS (done with ffmpeg + numpy; the master volume in sfx.js
sets the final level).

| File | Source | Author | Licence |
|---|---|---|---|
| clap.wav | "Single hand clap by one person", https://etc.usf.edu/clipaudio/files/553.mp3 (one clap cut at 1.02 s) | ClipAudio, FCIT, University of South Florida | Free for non-commercial educational use with credit (https://etc.usf.edu/clipaudio/) |
| poke.wav | impactSoft_medium_000.ogg, https://kenney.nl/assets/impact-sounds | Kenney (kenney.nl) | CC0 1.0 |
| thump.wav | footstep_carpet_000.ogg, https://kenney.nl/assets/impact-sounds | Kenney (kenney.nl) | CC0 1.0 |
| rustle.wav | cloth1.ogg, https://kenney.nl/assets/rpg-audio | Kenney (kenney.nl) | CC0 1.0 |
| paper_out.wav | bookOpen.ogg, https://kenney.nl/assets/rpg-audio | Kenney (kenney.nl) | CC0 1.0 |
| paper_read.wav | bookFlip1.ogg, https://kenney.nl/assets/rpg-audio | Kenney (kenney.nl) | CC0 1.0 |
| paper_away.wav | bookClose.ogg, https://kenney.nl/assets/rpg-audio | Kenney (kenney.nl) | CC0 1.0 |

The clap is not CC0: do not ship it in a commercial product without replacing it.
