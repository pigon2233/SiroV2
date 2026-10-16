"""Small async JSON HTTP transport used by provider adapters."""

from __future__ import annotations

import asyncio
import json
import urllib.request
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

import httpx

from siro.ports.models import CancellationToken


class ProviderResponseInvalid(ValueError):
    """A provider returned malformed data or an explicit error response."""


def _decode_json_response(payload: str | bytes) -> object:
    try:
        return json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    # Keep payload-bearing decoder exceptions out of the exception chain.
    raise ProviderResponseInvalid("provider returned invalid JSON or text encoding")


class JsonTransport(Protocol):
    async def post(
        self, url: str, payload: dict[str, object], headers: dict[str, str], timeout: float
    ) -> dict[str, object]: ...


class StreamingJsonTransport(Protocol):
    def stream_lines(
        self,
        url: str,
        payload: dict[str, object],
        headers: dict[str, str],
        timeout: float,
        cancellation: CancellationToken,
    ) -> AsyncIterator[str]: ...


@dataclass(frozen=True, slots=True)
class HttpxStreamingTransport:
    async def stream_lines(
        self,
        url: str,
        payload: dict[str, object],
        headers: dict[str, str],
        timeout: float,
        cancellation: CancellationToken,
    ) -> AsyncIterator[str]:
        request_headers = {"User-Agent": "siro-core/0.1", **headers}
        async with (
            httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client,
            client.stream("POST", url, json=payload, headers=request_headers) as response,
        ):
            response.raise_for_status()
            iterator = response.aiter_lines().__aiter__()
            while not cancellation.cancelled:
                next_line: asyncio.Future[str] = asyncio.ensure_future(anext(iterator))
                cancelled = asyncio.create_task(cancellation.wait())
                done, _ = await asyncio.wait(
                    (next_line, cancelled), return_when=asyncio.FIRST_COMPLETED
                )
                if cancelled in done:
                    next_line.cancel()
                    await asyncio.gather(next_line, return_exceptions=True)
                    return
                cancelled.cancel()
                await asyncio.gather(cancelled, return_exceptions=True)
                try:
                    yield next_line.result()
                except StopAsyncIteration:
                    return


@dataclass(frozen=True, slots=True)
class UrllibJsonTransport:
    async def post(
        self, url: str, payload: dict[str, object], headers: dict[str, str], timeout: float
    ) -> dict[str, object]:
        return await asyncio.to_thread(self._post, url, payload, headers, timeout)

    @staticmethod
    def _post(
        url: str, payload: dict[str, object], headers: dict[str, str], timeout: float
    ) -> dict[str, object]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "siro-core/0.1",
                **headers,
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            decoded = _decode_json_response(response.read())
        if not isinstance(decoded, dict):
            raise ValueError("provider returned a non-object JSON response")
        return decoded
