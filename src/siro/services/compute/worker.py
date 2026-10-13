"""Loopback JSON-lines compute worker used for L2 protocol verification."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorkerResult:
    chunks: tuple[str, ...]
    digest: str


class ComputeWorkerServer:
    def __init__(self, *, max_input_bytes: int = 1_000_000, fault: str | None = None) -> None:
        self.max_input_bytes = max_input_bytes
        self.fault = fault
        self.artifacts: set[Path] = set()

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        artifact: Path | None = None
        try:
            request = json.loads(await asyncio.wait_for(reader.readline(), timeout=3))
            payload = bytes.fromhex(request["payload_hex"])
            if len(payload) > self.max_input_bytes:
                await self._send(writer, {"type": "error", "reason": "input_limit"})
                return
            with tempfile.NamedTemporaryFile(prefix="siro-job-", delete=False) as handle:
                handle.write(payload)
                artifact = Path(handle.name)
            self.artifacts.add(artifact)
            words = payload.decode("utf-8").split()
            for index, word in enumerate(words):
                await self._send(
                    writer,
                    {
                        "type": "chunk",
                        "job_id": request["job_id"],
                        "epoch": request["epoch"],
                        "index": index,
                        "text": word,
                    },
                )
                if self.fault == "crash_after_chunk":
                    return
            await self._send(
                writer,
                {
                    "type": "result",
                    "job_id": request["job_id"],
                    "epoch": request["epoch"],
                    "digest": hashlib.sha256(payload).hexdigest(),
                },
            )
        except (TimeoutError, ValueError, KeyError, json.JSONDecodeError):
            await self._send(writer, {"type": "error", "reason": "invalid_request"})
        finally:
            if artifact is not None:
                artifact.unlink(missing_ok=True)
                self.artifacts.discard(artifact)
            writer.close()
            await writer.wait_closed()

    @staticmethod
    async def _send(writer: asyncio.StreamWriter, value: dict[str, object]) -> None:
        writer.write(json.dumps(value).encode() + b"\n")
        await writer.drain()


async def run_job(host: str, port: int, *, job_id: str, epoch: int, payload: bytes) -> WorkerResult:
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(
        json.dumps({"job_id": job_id, "epoch": epoch, "payload_hex": payload.hex()}).encode()
        + b"\n"
    )
    await writer.drain()
    chunks: list[str] = []
    digest: str | None = None
    try:
        while line := await asyncio.wait_for(reader.readline(), timeout=3):
            message = json.loads(line)
            if message.get("type") == "error":
                raise ValueError(str(message.get("reason")))
            if message.get("job_id") != job_id or message.get("epoch") != epoch:
                raise ValueError("worker result identity mismatch")
            if message["type"] == "chunk":
                if message["index"] != len(chunks):
                    raise ValueError("worker stream index mismatch")
                chunks.append(str(message["text"]))
            elif message["type"] == "result":
                digest = str(message["digest"])
                break
        if digest != hashlib.sha256(payload).hexdigest():
            raise ConnectionError("worker ended without a valid result")
        return WorkerResult(tuple(chunks), digest)
    finally:
        writer.close()
        await writer.wait_closed()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    arguments = parser.parse_args()
    worker = ComputeWorkerServer()

    async def serve() -> None:
        server = await asyncio.start_server(worker.handle, arguments.host, arguments.port)
        async with server:
            await server.serve_forever()

    asyncio.run(serve())
