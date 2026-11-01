"""One-shot local Ollama vision latency probe (synthetic JPEG, no secrets)."""
from __future__ import annotations

import base64
import io
import json
import time
import urllib.request

from PIL import Image


def main() -> None:
    image = Image.new("RGB", (960, 540), (20, 40, 80))
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=70)
    b64 = base64.b64encode(buf.getvalue()).decode()
    body = json.dumps(
        {
            "model": "gemma4:e4b",
            "stream": False,
            "think": False,
            "options": {"temperature": 0.1, "num_predict": 80, "num_ctx": 2048},
            "messages": [
                {
                    "role": "user",
                    "content": 'Reply JSON only: {"kind":"wait","seen":"blue","confidence":0.5}',
                    "images": [b64],
                }
            ],
        }
    ).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            data = response.read()
        elapsed = time.perf_counter() - started
        payload = json.loads(data)
        content = (payload.get("message") or {}).get("content", "")
        print(f"ok_s={elapsed:.2f} bytes={len(data)}")
        print(f"content={content[:240]!r}")
    except Exception as error:  # noqa: BLE001
        elapsed = time.perf_counter() - started
        print(f"fail_s={elapsed:.2f} {type(error).__name__}: {error}")


if __name__ == "__main__":
    main()
