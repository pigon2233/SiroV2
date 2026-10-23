"""Digest-pinned Qwen3 embeddings through literal-loopback Ollama only."""

from __future__ import annotations

from urllib.parse import urlsplit

import httpx

from siro.ports.embeddings import EmbeddingProfile, RetrievalUnavailable, normalized


class OllamaEmbedder:
    def __init__(
        self,
        profile: EmbeddingProfile,
        *,
        base_url: str = "http://127.0.0.1:11434",
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 60,
    ) -> None:
        parts = urlsplit(base_url)
        if (
            parts.scheme != "http"
            or parts.hostname not in ("127.0.0.1", "::1")
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
            or parts.path not in ("", "/")
        ):
            raise ValueError("embedding requires a literal loopback HTTP endpoint")
        if not 0 < timeout <= 120:
            raise ValueError("embedding timeout must be bounded")
        self._profile = profile
        self._url = base_url.rstrip("/")
        self._transport = transport
        self._timeout = timeout

    @property
    def profile(self) -> EmbeddingProfile:
        return self._profile

    async def _verify(self, client: httpx.AsyncClient) -> None:
        response = await client.get(f"{self._url}/api/tags")
        response.raise_for_status()
        matches = [m for m in response.json()["models"] if m.get("name") == self.profile.model]
        if len(matches) != 1 or matches[0].get("digest") != self.profile.digest:
            raise RetrievalUnavailable("embedding model digest changed or missing")

    async def embed(self, texts: tuple[str, ...], *, query: bool) -> tuple[tuple[float, ...], ...]:
        if (
            not 1 <= len(texts) <= 32
            or (query and len(texts) != 1)
            or any(not t.strip() or len(t.encode("utf-8")) > 16384 for t in texts)
        ):
            raise RetrievalUnavailable("embedding input bounds exceeded")
        inputs = [
            "Instruct: Retrieve personal memories relevant to the user's question.\nQuery:" + t
            if query
            else t
            for t in texts
        ]
        try:
            async with httpx.AsyncClient(
                trust_env=False,
                follow_redirects=False,
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                await self._verify(client)
                response = await client.post(
                    f"{self._url}/api/embed",
                    json={
                        "model": self.profile.model,
                        "input": inputs,
                        "truncate": False,
                        "dimensions": self.profile.dimensions,
                        "keep_alive": "5m",
                    },
                )
                response.raise_for_status()
                body = response.json()
                vectors = body["embeddings"]
                if body.get("model") != self.profile.model or len(vectors) != len(texts):
                    raise RetrievalUnavailable("embedding response mismatch")
                result = tuple(normalized(v, self.profile.dimensions) for v in vectors)
                await self._verify(client)
                return result
        except RetrievalUnavailable:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError, OverflowError):
            # Provider bodies and plaintext input must not escape into errors/logs.
            raise RetrievalUnavailable("local embedding request failed") from None
