#!/usr/bin/env python3
"""Run an authenticated LAN MQTT broker for the ESP32 node (Windows host).

Credentials come from SIRO_MQTT_BROKER_USERNAME/PASSWORD, or from the MQTT lines of the
git-ignored firmware/esp32/include/secrets.h. Nothing is printed or written to the repo.
Requires amqtt and argon2-cffi (e.g. a separate venv); bind with SIRO_MQTT_BROKER_BIND.
"""

from __future__ import annotations

import asyncio
import os
import re
import signal
import tempfile
from pathlib import Path

from amqtt.broker import Broker  # type: ignore[import-untyped]
from argon2 import PasswordHasher

SECRETS = Path(__file__).resolve().parents[1] / "firmware" / "esp32" / "include" / "secrets.h"


def credentials() -> tuple[str, str]:
    username = os.environ.get("SIRO_MQTT_BROKER_USERNAME")
    password = os.environ.get("SIRO_MQTT_BROKER_PASSWORD")
    if username and password:
        return username, password
    text = SECRETS.read_text(encoding="utf-8")
    values = dict(re.findall(r'#define SIRO_MQTT_(USERNAME|PASSWORD) "([^"]+)"', text))
    if "USERNAME" not in values or "PASSWORD" not in values:
        raise SystemExit("MQTT credentials are not configured")
    return values["USERNAME"], values["PASSWORD"]


async def main() -> None:
    username, password = credentials()
    bind = os.environ.get("SIRO_MQTT_BROKER_BIND", "0.0.0.0:1883")
    with tempfile.TemporaryDirectory() as directory:
        password_file = Path(directory) / "passwords"
        password_file.write_text(f"{username}:{PasswordHasher().hash(password)}\n")
        broker = Broker(
            {
                "listeners": {"default": {"type": "tcp", "bind": bind}},
                "plugins": {
                    "amqtt.plugins.authentication.FileAuthPlugin": {
                        "password_file": str(password_file)
                    }
                },
            }
        )
        await broker.start()
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for name in ("SIGINT", "SIGTERM"):
            try:
                loop.add_signal_handler(getattr(signal, name), stop.set)
            except NotImplementedError:  # Windows loops lack signal handlers.
                signal.signal(getattr(signal, name), lambda *_: loop.call_soon_threadsafe(stop.set))
        print(f"ESP32 MQTT broker listening on {bind}", flush=True)
        await stop.wait()
        await broker.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
