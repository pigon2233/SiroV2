"""The TTS player drives the character's mouth from the audio it actually plays."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")

ORIGIN = "http://siro.test"
INDEX = Path("src/siro/services/presentation/static/index.html")

# Built without markup: an about:blank frame is same-origin, so the page can listen inside it.
SETUP = """
window.__mouth = [];
const frame = document.createElement('iframe');
frame.id = 'companion';
document.body.append(frame);
frame.contentWindow.addEventListener('message', event => window.__mouth.push(event.data));
var ttsAudio;
__FUNCTIONS__
// 0.5 s silence, then 1 s of a 220 Hz tone pulsing like syllables, as a 16-bit mono WAV.
window.wav = () => {
  const rate = 16000, samples = rate * 1.5, data = new DataView(new ArrayBuffer(44 + samples * 2));
  const text = (at, value) => [...value].forEach((c, i) => data.setUint8(at + i, c.charCodeAt(0)));
  text(0, 'RIFF'); data.setUint32(4, 36 + samples * 2, true); text(8, 'WAVEfmt ');
  data.setUint32(16, 16, true); data.setUint16(20, 1, true); data.setUint16(22, 1, true);
  data.setUint32(24, rate, true); data.setUint32(28, rate * 2, true); data.setUint16(32, 2, true);
  data.setUint16(34, 16, true); text(36, 'data'); data.setUint32(40, samples * 2, true);
  for (let i = 0; i < samples; i++) {
    const t = i / rate, on = t >= 0.5 ? Math.abs(Math.sin((t - 0.5) * Math.PI * 4)) : 0;
    data.setInt16(44 + i * 2, Math.round(on * 12000 * Math.sin(2 * Math.PI * 220 * t)), true);
  }
  return new Blob([data.buffer], {type: 'audio/wav'});
};
"""


def test_envelope_follows_loudness_and_mouth_closes_when_playback_ends() -> None:
    html = INDEX.read_text(encoding="utf-8")
    functions = html[html.index("const MOUTH_RATE") : html.index("async function playTts(")]
    setup = SETUP.replace("__FUNCTIONS__", functions)
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    with playwright_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page()
            page.route(
                f"{ORIGIN}/**",
                lambda route: route.fulfill(body="mouth sync", content_type="text/html"),
            )
            page.goto(f"{ORIGIN}/")
            page.add_script_tag(content=setup)
            envelope = page.evaluate("speechEnvelope(wav())")
            assert envelope is not None and len(envelope) == 90
            silent = [level for level, _tone in envelope[:28]]
            voiced = [level for level, _tone in envelope[32:]]
            assert max(silent) == 0
            assert max(voiced) > 0.8
            assert sum(voiced) / len(voiced) > 0.3

            # Played through a stand-in audio element: the mouth opens with the sound and closes
            # once this audio stops being the current one.
            page.evaluate(
                """() => {
                  window.fake = {paused: false, currentTime: 0};
                  ttsAudio = fake;
                  syncMouth(fake, wav(), () => true);
                }"""
            )
            page.wait_for_function("__mouth.length > 0")
            page.evaluate("fake.currentTime = 0.875")  # a syllable peak
            page.wait_for_function(
                "__mouth.some(m => m.type === 'siro.speech.mouth' && m.level > 0.5)"
            )
            assert all(m["v"] == 1 and 0 <= m["tone"] <= 1 for m in page.evaluate("__mouth"))
            page.evaluate("ttsAudio = undefined")
            page.wait_for_function("__mouth.at(-1).level === 0")
            count = page.evaluate("__mouth.length")
            page.wait_for_timeout(300)
            assert page.evaluate("__mouth.length") == count
        finally:
            browser.close()


def test_mouth_sync_is_skipped_without_a_renderer_frame() -> None:
    html = INDEX.read_text(encoding="utf-8")
    functions = html[html.index("const MOUTH_RATE") : html.index("async function playTts(")]
    assert "postMessage" in functions
    # Playback starts without waiting for the envelope; sync runs beside it.
    assert "syncMouth(audio, blob, current);" in html
    assert html.index("syncMouth(audio, blob, current);") < html.index("audio.play()")
