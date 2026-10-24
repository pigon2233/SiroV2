"""Release healthcheck: start the gateway from the bundle in cwd and make it answer, then stop it.

Run with cwd = the staged bundle (it holds src/siro). Synthetic data only: the database is
copied to a temp dir and the gateway listens on a spare localhost port. Exit 0 = healthy
answer + graceful stop (uvicorn logs 'Application shutdown complete' then re-raises SIGTERM, so exit -15 is normal; websocket told to reconnect with 1012, data lock freed).
"""
from __future__ import annotations

import asyncio, json, os, signal, socket, sqlite3, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

import websockets  # type: ignore[import-not-found]

bundle = Path.cwd()
source_db = Path(os.environ["SIRO_DRILL_HC_DB"])
report_path = os.environ.get("SIRO_DRILL_HC_REPORT")
report: dict[str, object] = {"bundle": str(bundle)}


def spare_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def get(port: int, path: str, data: bytes | None = None, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(request, timeout=3) as response:
        return json.loads(response.read())


def start(data_dir: Path, port: int) -> subprocess.Popen[bytes]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(bundle / "src"), "SIRO_DATA_DIR": str(data_dir), "SIRO_GATEWAY_PORT": str(port)}
    for name in ("SIRO_OLLAMA_MODEL", "SIRO_OPENAI_API_KEY", "SIRO_OPENAI_MODEL", "SIRO_RUNTIME_PROFILE"):
        env.pop(name, None)
    return subprocess.Popen(
        [sys.executable, "-c", "from siro.services.presentation.gateway import main; main()"],
        cwd=data_dir, env=env, stdout=open(data_dir / "out.log", "wb"), stderr=subprocess.STDOUT,
    )


def wait_ready(process: subprocess.Popen[bytes], port: int, seconds: float = 20) -> dict | None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and process.poll() is None:
        try:
            state = get(port, "/health/ready")
            if state.get("state") == "healthy":
                return state
        except OSError:
            time.sleep(0.2)
    return None


async def hold_websocket(port: int) -> tuple[object, object]:
    origin = f"http://127.0.0.1:{port}"
    token = get(port, "/v1/session", data=b"", headers={"Origin": origin})["token"]
    ws = await websockets.connect(f"ws://127.0.0.1:{port}/ws/control", origin=origin)
    await ws.send(json.dumps({"type": "authenticate", "token": token}))
    await asyncio.wait_for(ws.recv(), 3)
    return ws, token


async def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        data_dir = Path(td)
        with sqlite3.connect(source_db) as src, sqlite3.connect(data_dir / "siro.db") as dst:
            src.backup(dst)
        port = spare_port()
        process = start(data_dir, port)
        ready = wait_ready(process, port)
        report["ready"] = ready
        if ready is None:
            process.kill()
            report["log_tail"] = (data_dir / "out.log").read_text(errors="replace")[-1500:]
            return finish(1)
        report["live"] = get(port, "/health/live")
        # Only one process may own the data: a second gateway on the same dir must refuse.
        second = start(data_dir, spare_port())
        try:
            report["second_owner_exit"] = second.wait(timeout=15)
        except subprocess.TimeoutExpired:
            second.kill()
            report["second_owner_exit"] = "still running (lock not enforced)"
        ws, _ = await hold_websocket(port)
        started = time.monotonic()
        process.send_signal(signal.SIGTERM)
        try:
            await ws.wait_closed()  # type: ignore[attr-defined]
            report["ws_close_code"] = ws.close_code  # type: ignore[attr-defined]
        except Exception as error:  # noqa: BLE001
            report["ws_close_code"] = f"error:{error!r}"
        try:
            report["exit_code"] = process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            report["exit_code"] = "killed after 20s"
        report["stop_seconds"] = round(time.monotonic() - started, 2)
        log = (data_dir / "out.log").read_text(errors="replace")
        report["log_shutdown_lines"] = [line for line in log.splitlines() if "hutdown" in line or "hutting" in line]
        report["clean_shutdown_logged"] = any("Application shutdown complete" in line for line in report["log_shutdown_lines"])  # type: ignore[attr-defined]
        try:
            get(port, "/health/live")
            report["port_closed"] = False
        except OSError:
            report["port_closed"] = True
        p3 = spare_port()
        third = start(data_dir, p3)
        report["restart_after_stop_ready"] = wait_ready(third, p3) is not None
        third.send_signal(signal.SIGTERM)
        third.wait(timeout=20)
        report["restart_after_stop_exit"] = third.returncode
        ok = (
            report["exit_code"] in (0, -signal.SIGTERM) and report["clean_shutdown_logged"] is True
            and report["ws_close_code"] == 1012 and report["port_closed"] is True
            and report["second_owner_exit"] not in (0, "still running (lock not enforced)")
            and report["restart_after_stop_ready"] is True
        )
        return finish(0 if ok else 1)


def finish(code: int) -> int:
    if report_path:
        Path(report_path).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, default=str))
    return code


sys.exit(asyncio.run(main()))
