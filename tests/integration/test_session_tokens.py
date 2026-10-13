from __future__ import annotations

from dataclasses import dataclass

import httpx
import pytest

from siro.services.presentation.gateway import GatewayState, SessionTokens, create_app

_ORIGIN = "http://127.0.0.1:8000"


@dataclass
class FakeClock:
    now: float = 0

    def __call__(self) -> float:
        return self.now


def test_default_token_lifetime_expires_at_exact_deadline() -> None:
    clock = FakeClock()
    tokens = SessionTokens(clock=clock)
    token, ttl = tokens.issue()
    assert ttl == 300
    assert tokens.valid(token)
    assert not tokens.valid("unknown")
    clock.now = 299.999
    assert tokens.valid(token)
    clock.now = 300
    assert not tokens.valid(token)
    assert token not in tokens._tokens


def test_issue_reaps_all_expired_tokens_without_prior_validation() -> None:
    clock = FakeClock()
    tokens = SessionTokens(max_tokens=2, clock=clock)
    first, _ = tokens.issue()
    second, _ = tokens.issue()
    clock.now = 300
    fresh, ttl = tokens.issue()
    assert ttl == 300
    assert set(tokens._tokens) == {fresh}
    assert tokens.valid(fresh)
    assert not tokens.valid(first)
    assert not tokens.valid(second)


def test_default_capacity_preserves_all_128_active_tokens() -> None:
    tokens = SessionTokens(clock=FakeClock())
    active = [tokens.issue()[0] for _ in range(128)]
    retained = dict(tokens._tokens)
    with pytest.raises(SessionTokens.CapacityExceeded):
        tokens.issue()
    assert tokens._tokens == retained
    assert len(set(active)) == 128
    assert all(tokens.valid(token) for token in active)


@pytest.mark.parametrize("max_tokens", [0, -1])
def test_token_capacity_must_be_positive(max_tokens: int) -> None:
    with pytest.raises(ValueError, match="capacity must be positive"):
        SessionTokens(max_tokens=max_tokens)


def test_overlapping_renewals_preserve_other_active_tokens() -> None:
    clock = FakeClock()
    tokens = SessionTokens(max_tokens=2, clock=clock)
    first, _ = tokens.issue()
    clock.now = 100
    second, _ = tokens.issue()
    clock.now = 299
    retained = dict(tokens._tokens)
    with pytest.raises(SessionTokens.CapacityExceeded):
        tokens.issue()
    assert tokens._tokens == retained
    assert tokens.valid(first) and tokens.valid(second)
    clock.now = 300
    third, _ = tokens.issue()
    assert not tokens.valid(first)
    assert tokens.valid(second) and tokens.valid(third)
    assert set(tokens._tokens) == {second, third}
    assert tokens._tokens[second] == 400


def test_repeated_renewal_retention_stays_bounded() -> None:
    clock = FakeClock()
    tokens = SessionTokens(max_tokens=2, clock=clock)
    for _ in range(1000):
        token, ttl = tokens.issue()
        assert ttl == 300
        assert tokens.valid(token)
        assert 1 <= len(tokens._tokens) <= 2
        assert all(expiry > clock.now for expiry in tokens._tokens.values())
        clock.now += 240


@pytest.mark.asyncio
async def test_real_session_route_capacity_expiry_and_existing_bearers() -> None:
    clock = FakeClock()
    tokens = SessionTokens(max_tokens=2, clock=clock)
    app = create_app(tokens=tokens)
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50100))
    async with httpx.AsyncClient(transport=transport, base_url=_ORIGIN) as client:
        active = []
        for _ in range(2):
            response = await client.post("/v1/session", headers={"origin": _ORIGIN})
            assert response.status_code == 200
            assert response.json()["expires_in_seconds"] == 300
            active.append(response.json()["token"])
        full = await client.post("/v1/session", headers={"origin": _ORIGIN})
        assert full.status_code == 429
        assert full.json() == {"detail": "too many active sessions"}
        for token in active:
            snapshot = await client.get(
                "/v1/snapshot", headers={"authorization": f"Bearer {token}"}
            )
            assert snapshot.status_code == 200
        for authorization in (None, "Bearer unknown", f"bearer {active[0]}"):
            headers = {} if authorization is None else {"authorization": authorization}
            assert (await client.get("/v1/snapshot", headers=headers)).status_code == 401
        clock.now = 300
        refreshed = await client.post("/v1/session", headers={"origin": _ORIGIN})
        assert refreshed.status_code == 200
        fresh = refreshed.json()["token"]
        assert fresh not in active
        assert set(tokens._tokens) == {fresh}
        assert (
            await client.get("/v1/snapshot", headers={"authorization": f"Bearer {fresh}"})
        ).status_code == 200
        for token in active:
            assert (
                await client.get("/v1/snapshot", headers={"authorization": f"Bearer {token}"})
            ).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("host", "origin"),
    [
        ("127.0.0.1", None),
        ("127.0.0.1", "null"),
        ("127.0.0.1", "https://evil.invalid"),
        ("192.0.2.1", _ORIGIN),
    ],
)
async def test_real_session_route_checks_origin_and_loopback_before_capacity(
    host: str, origin: str | None
) -> None:
    tokens = SessionTokens(max_tokens=1, clock=FakeClock())
    existing, _ = tokens.issue()
    retained = dict(tokens._tokens)
    app = create_app(tokens=tokens)
    transport = httpx.ASGITransport(app=app, client=(host, 50100))
    async with httpx.AsyncClient(transport=transport, base_url=_ORIGIN) as client:
        headers = {} if origin is None else {"origin": origin}
        denied = await client.post("/v1/session", headers=headers)
        assert denied.status_code == 403
    assert tokens._tokens == retained
    assert tokens.valid(existing)


@pytest.mark.asyncio
async def test_expired_bearer_rejects_turn_and_speech_before_accepting_work() -> None:
    clock = FakeClock()
    tokens = SessionTokens(clock=clock)
    expired, _ = tokens.issue()
    clock.now = 300
    state = GatewayState()
    accepted: list[str] = []

    async def turn(session: str, text: str, input_mode: str) -> None:
        accepted.append("turn")

    class Speech:
        async def render(self, text: str, *, rate: float, pitch: float, energy: float) -> bytes:
            accepted.append("speech")
            return b"RIFFsynthetic"

    app = create_app(tokens=tokens, state=state, on_turn=turn, text_to_speech=Speech())
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50100))
    async with httpx.AsyncClient(transport=transport, base_url=_ORIGIN) as client:
        headers = {"origin": _ORIGIN, "authorization": f"Bearer {expired}"}
        for path in ("/v1/conversations/browser/turns", "/v1/audio/speech"):
            response = await client.post(path, headers=headers, json={"text": "synthetic"})
            assert response.status_code == 401
            assert response.json() == {"detail": "session token is invalid or expired"}
        assert accepted == []
        assert state.active_turns == {}
        fresh, _ = tokens.issue()
        headers["authorization"] = f"Bearer {fresh}"
        assert (
            await client.post(
                "/v1/conversations/browser/turns", headers=headers, json={"text": "synthetic"}
            )
        ).status_code == 200
        assert (
            await client.post("/v1/audio/speech", headers=headers, json={"text": "synthetic"})
        ).status_code == 200
    assert accepted == ["turn", "speech"]
