"""Text-only Ollama latency probe."""
from __future__ import annotations

import json
import time
import urllib.request


def main() -> None:
    body = json.dumps(
        {
            "model": "gemma4:e4b",
            "stream": False,
            "think": False,
            "options": {"num_predict": 40},
            "messages": [{"role": "user", "content": "Say hi in three words."}],
        }
    ).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            data = response.read()
        content = (json.loads(data).get("message") or {}).get("content", "")
        print(f"text_ok_s={time.perf_counter() - started:.2f} content={content[:120]!r}")
    except Exception as error:  # noqa: BLE001
        print(f"text_fail_s={time.perf_counter() - started:.2f} {type(error).__name__}: {error}")


if __name__ == "__main__":
    main()
