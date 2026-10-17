"""Small async JSON HTTP transport used by provider adapters."""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.request
from collections.abc import AsyncIterator
from contextlib import suppress
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
        if cancellation.cancelled:
            return
        request_headers = {"User-Agent": "siro-core/0.1", **headers}
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            request = client.build_request("POST", url, json=payload, headers=request_headers)
            opening = asyncio.create_task(client.send(request, stream=True))
            cancelled = asyncio.create_task(cancellation.wait())
            response: httpx.Response | None = None
            next_line: asyncio.Future[str] | None = None
            try:
                await asyncio.wait((opening, cancelled), return_when=asyncio.FIRST_COMPLETED)
                # The flag also covers a same-tick response/error before the watcher wakes.
                if cancellation.cancelled:
                    return
                response = opening.result()
                if response.is_error:
                    # Status only: never log provider bodies, URLs, credentials or prompts.
                    logging.getLogger(__name__).warning(
                        "model provider HTTP failure status=%d", response.status_code
                    )
                response.raise_for_status()
                iterator = response.aiter_lines().__aiter__()
                while not cancellation.cancelled:
                    next_line = asyncio.ensure_future(anext(iterator))
                    await asyncio.wait((next_line, cancelled), return_when=asyncio.FIRST_COMPLETED)
                    if cancellation.cancelled:
                        return
                    try:
                        line = next_line.result()
                    except StopAsyncIteration:
                        return
                    next_line = None
                    yield line
            finally:
                owned = tuple(task for task in (opening, cancelled, next_line) if task is not None)
                for task in owned:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*owned, return_exceptions=True)
                # Opening can finish in the same tick cancellation wins. Still close it.
                if response is None and not opening.cancelled():
                    with suppress(Exception):
                        response = opening.result()
                if response is not None:
                    await response.aclose()


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
