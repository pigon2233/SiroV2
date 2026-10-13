#!/usr/bin/env python3
"""Run the reversible Linux A17 service/audio/gateway integration check."""

from __future__ import annotations

import asyncio
import io
import json
import math
import socket
import struct
import tempfile
import wave
from pathlib import Path

import httpx

from siro.adapters.browser import ScopedBrowserDriver
from siro.adapters.services import (
    CriticalInstallApproval,
    SystemdUserServiceDriver,
    SystemdUserUnitInstaller,
)

UNIT = "siro-t25-a17.service"


def test_wav(seconds: float = 6.0, sample_rate: int = 48_000) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        frames = (
            struct.pack("<h", round(900 * math.sin(2 * math.pi * 440 * index / sample_rate)))
            for index in range(round(seconds * sample_rate))
        )
        audio.writeframes(b"".join(frames))
    return output.getvalue()


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


async def wait_for_service(url: str) -> None:
    async with httpx.AsyncClient(timeout=1) as client:
        for _ in range(30):
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.1)
    raise RuntimeError("test service did not become ready")


async def gateway_state() -> tuple[str, int]:
    async with httpx.AsyncClient(timeout=2) as client:
        health = await client.get("http://127.0.0.1:8000/health/live")
        renderer = await client.get("http://127.0.0.1:8000/live2d/")
        health.raise_for_status()
        renderer.raise_for_status()
        return str(health.json()["state"]), len(renderer.content)


async def run() -> dict[str, object]:
    port = free_port()
    unit_directory = Path.home() / ".config/systemd/user"
    unit_path = unit_directory / UNIT
    if unit_path.exists():
        raise RuntimeError(f"refusing to replace existing test unit: {unit_path}")
    content = (
        "[Unit]\nDescription=SIRO reversible T25 A17 test service\n"
        "[Service]\nType=simple\n"
        f"ExecStart=/usr/bin/python3 -m http.server {port} --bind 127.0.0.1\n"
        "NoNewPrivileges=yes\nPrivateTmp=yes\nProtectSystem=strict\nProtectHome=yes\n"
        "[Install]\nWantedBy=default.target\n"
    )
    driver = SystemdUserServiceDriver(frozenset({UNIT}))
    installer = SystemdUserUnitInstaller(unit_directory, driver)
    pending = installer.approval_request("a17-install", UNIT, content)
    approval = CriticalInstallApproval(
        pending.action_id, pending.unit, pending.content_sha256, "owner-authorized-t25-test"
    )
    before = await gateway_state()
    try:
        await installer.install("a17-install", UNIT, content, approval)
        gateway_origin = "http://127.0.0.1:8000"
        async with ScopedBrowserDriver((gateway_origin,), headless=False) as browser:
            await browser.navigate(gateway_origin)
            audio_link = await browser.select("link", "執行 20 次真人打斷與 AEC 欄位測試")
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio_file:
                audio_path = Path(audio_file.name)
                audio_file.write(test_wav())
            try:
                player = await asyncio.create_subprocess_exec(
                    "pw-play",
                    str(audio_path),
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                started = await driver.start("a17-start", UNIT)
                await wait_for_service(f"http://127.0.0.1:{port}/")
                stopped = await driver.stop("a17-stop", UNIT)
                ui_readback = await browser.click(audio_link)
                during = await gateway_state()
                audio_was_independent = player.returncode is None
                _, player_stderr = await player.communicate()
                if player.returncode:
                    raise RuntimeError(
                        f"PipeWire playback failed: {player_stderr.decode(errors='replace')[:300]}"
                    )
            finally:
                audio_path.unlink(missing_ok=True)
        return {
            "service_started": started.active_state,
            "service_stopped": stopped.active_state,
            "audio_was_playing_after_service_stop": audio_was_independent,
            "browser_readback": ui_readback.title,
            "gateway_before": before,
            "gateway_after_service_stop": during,
        }
    finally:
        stop = await asyncio.create_subprocess_exec(
            "systemctl",
            "--user",
            "stop",
            UNIT,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await stop.wait()
        unit_path.unlink(missing_ok=True)
        await driver.reload()


def main() -> None:
    result = asyncio.run(run())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
