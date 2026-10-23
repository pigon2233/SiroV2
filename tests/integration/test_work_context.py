"""CP-P05: scoped work context; seen, guessed and unknown stay apart and expire or revoke."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from siro.ports.models import Privacy
from siro.ports.vision import VisualObservation
from siro.services.context.work_context import AppSnapshot, ScopeStore, WorkContext
from siro.services.presentation.gateway import create_app

NOW = datetime(2026, 10, 23, 9, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


class FakeVision:
    async def analyze(self, image_png: bytes) -> VisualObservation:
        return VisualObservation("dark screen", "fake", 0.9, 10, 10)


def make(tmp_path: Path | None = None) -> tuple[WorkContext, Clock]:
    clock = Clock()
    scope = ScopeStore(tmp_path / "scope.json" if tmp_path else None)
    return WorkContext(scope, clock=clock, vision=FakeVision()), clock


def test_everything_is_off_by_default_and_unknown_is_unknown() -> None:
    context, _ = make()
    assert context.ingest_app(AppSnapshot("Code")) is None
    situation = context.situation()
    assert situation.status == "unknown" and situation.hint is None and context.may_interrupt()


def test_editor_is_only_a_guess_and_asks_instead_of_claiming() -> None:
    context, _ = make()
    context.update_scope({"app_metadata": True})
    seen = context.ingest_app(AppSnapshot("Visual Studio Code", "secret-plan.md"))
    assert seen is not None and seen.kind == "seen" and seen.subject == "editor"
    assert "secret-plan" not in repr(context.status())  # the title is never stored
    situation = context.situation()
    assert situation.hint is not None and "推測" in situation.hint
    assert situation.question == "你是在寫程式嗎？"  # noqa: RUF001
    assert context.may_interrupt()


def test_focus_and_fullscreen_are_left_alone() -> None:
    context, _ = make()
    context.update_scope({"app_metadata": True})
    context.ingest_app(AppSnapshot("Code", focus_mode=True))
    assert not context.may_interrupt()
    context.ingest_app(AppSnapshot("vlc", fullscreen=True))
    assert not context.may_interrupt()
    context.ingest_app(AppSnapshot("vlc"))
    assert context.may_interrupt()


def test_observations_expire_and_revoking_scope_makes_them_unusable_at_once() -> None:
    context, clock = make()
    context.update_scope({"app_metadata": True})
    context.ingest_app(AppSnapshot("Code"))
    clock.now += timedelta(minutes=3)
    assert context.situation().status == "unknown"
    context.ingest_app(AppSnapshot("Code"))
    assert context.situation().status == "known"
    context.update_scope({"app_metadata": False})
    assert context.situation().status == "unknown"
    assert context.prompt_lines(Privacy.LOCAL_ONLY) == ()
    context.update_scope({"app_metadata": True})  # a new revision; nothing old comes back
    assert context.situation().status == "unknown"


def test_lock_screen_and_sensitive_windows_leave_nothing() -> None:
    context, _ = make()
    context.update_scope({"app_metadata": True})
    context.ingest_app(AppSnapshot("Code"))
    assert context.ingest_app(AppSnapshot("Firefox", "Bank login 登入")) is None
    assert context.situation().status == "unknown"  # the earlier editor reading is dropped too
    context.ingest_app(AppSnapshot("Code"))
    assert context.ingest_app(AppSnapshot("LockApp", locked=True)) is None
    assert context.situation().status == "unknown"


def test_owner_statement_needs_no_scope_and_correction_stops_the_guess() -> None:
    context, _ = make()
    shared = context.share("正在整理報稅資料")
    assert shared.kind == "stated" and "報稅" in (context.situation().hint or "")
    context.update_scope({"app_metadata": True})
    guess = context.ingest_app(AppSnapshot("nvim"))
    assert guess is not None
    assert context.correct(guess.observation_id)
    assert not context.correct(guess.observation_id)  # the source is gone
    assert context.ingest_app(AppSnapshot("nvim")) is not None
    assert "寫程式" not in (context.situation().hint or "")  # corrected: not guessed again
    assert context.retract(shared.observation_id)
    assert context.situation().hint is None


def test_cloud_models_never_receive_context_and_expired_statements_vanish() -> None:
    context, clock = make()
    context.share("在寫論文", timedelta(minutes=5))
    assert context.prompt_lines(Privacy.CLOUD_ALLOWED) == ()
    assert any("論文" in line for line in context.prompt_lines(Privacy.LOCAL_ONLY))
    clock.now += timedelta(minutes=6)
    assert context.prompt_lines(Privacy.LOCAL_ONLY) == ()


def test_scope_survives_restart_and_a_damaged_file_means_off(tmp_path: Path) -> None:
    context, _ = make(tmp_path)
    context.update_scope({"screen": True})
    again, _ = make(tmp_path)
    assert again.source_enabled("screen") and not again.source_enabled("app_metadata")
    (tmp_path / "scope.json").write_text("{broken", encoding="utf-8")
    assert not make(tmp_path)[0].source_enabled("screen")


@pytest.mark.asyncio
async def test_screen_look_is_gated_and_dropped_if_switched_off_mid_capture() -> None:
    context, _ = make()

    async def capture() -> bytes | None:
        return b"png"

    assert not await context.observe_screen(capture)  # off
    context.update_scope({"screen": True})
    assert await context.observe_screen(capture)
    seen = context.situation().observations[0]
    assert seen.source == "screen" and seen.kind == "seen"

    async def slow() -> bytes | None:
        context.update_scope({"screen": False})
        await asyncio.sleep(0)
        return b"png"

    context.update_scope({"screen": True})
    assert not await context.observe_screen(slow)
    assert context.situation().status == "unknown"


def test_gateway_endpoints_scope_and_adapter_stop(tmp_path: Path) -> None:
    origin = "http://testserver"
    context, _ = make(tmp_path)
    app = create_app(allowed_origins={origin}, work_context=context)
    with TestClient(app) as client:
        assert client.get("/v1/work-context").status_code == 401
        token = client.post("/v1/session", headers={"origin": origin}).json()["token"]
        auth = {"authorization": f"Bearer {token}"}
        report = {"app_name": "Code", "window_title": "x"}
        assert client.post("/v1/work-context/app", json=report, headers=auth).status_code == 409
        scope = client.put("/v1/work-context/scope", json={"app_metadata": True}, headers=auth)
        assert scope.json()["scope"]["app_metadata"] is True
        body = client.post("/v1/work-context/app", json=report, headers=auth).json()
        assert body["status"] == "known" and body["question"]
        shared = client.post("/v1/work-context/shared", json={"text": "寫週報"}, headers=auth)
        assert shared.status_code == 200
        guess = next(o for o in shared.json()["observations"] if o["source"] == "app_metadata")
        action = f"/v1/work-context/{guess['id']}/retract"
        assert client.post(action, headers=auth).status_code == 200
        assert client.post(action, headers=auth).status_code == 404
        off = client.put("/v1/work-context/scope", json={"app_metadata": False}, headers=auth)
        assert off.json()["scope"]["app_metadata"] is False
        assert client.post("/v1/work-context/app", json=report, headers=auth).status_code == 409


def test_foreground_report_parsing_rejects_garbage() -> None:
    from siro.services.context.windows_providers import parse_foreground, parse_screen

    ok = parse_foreground('{"app":"Code","title":"t","locked":false,"fullscreen":true}')
    assert ok is not None and ok.fullscreen and not ok.locked
    assert parse_foreground(None) is None and parse_foreground("nope") is None
    assert parse_foreground('{"app":1,"title":"x"}') is None
    assert parse_screen("!!!") is None and parse_screen("cG5n") == b"png"


@pytest.mark.asyncio
async def test_app_observer_runs_powershell_only_while_switched_on() -> None:
    from siro.services.context.windows_providers import AppObserver

    context, _ = make()
    runs: list[str] = []

    async def run(script: str) -> str | None:
        runs.append(script)
        return '{"app":"nvim","title":"x","locked":false,"fullscreen":false}'

    observer = AppObserver(context, run)
    assert not await observer.sample() and runs == []  # off: nothing is even asked
    context.update_scope({"app_metadata": True})
    assert await observer.sample() and len(runs) == 1
    assert context.situation().observations[0].subject == "editor"


@pytest.mark.asyncio
async def test_situation_reaches_a_local_prompt_but_never_a_cloud_one(tmp_path: Path) -> None:
    from test_activity_monitor import ScriptedModel, companion

    context, _ = make()
    context.share("正在整理報稅資料")
    model = ScriptedModel(["好"])
    seen: list[str] = []
    stream = model.stream

    async def spy(request, cancellation):  # type: ignore[no-untyped-def]
        seen.append(repr(request))
        async for chunk in stream(request, cancellation):
            yield chunk

    model.stream = spy  # type: ignore[method-assign]
    controller, _ = await companion(tmp_path, model, {})
    controller._situation_lines = context.prompt_lines
    await controller.respond("s1", "你好")
    assert any("報稅" in text and "source:work-context" in text for text in seen)

    assert context.prompt_lines(Privacy.CLOUD_ALLOWED) == ()
