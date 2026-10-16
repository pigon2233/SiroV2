"""Actual main/HTTP cancellation of idle browser retains other session ownership."""
import importlib.util
import os
from pathlib import Path
import uvicorn
from fastapi.testclient import TestClient
from siro.ports.models import ModelChunk, ToolCall
from siro.services.presentation import gateway

def test_http_cancel_completed_turn_closes_only_its_idle_browser(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[4]
    spec = importlib.util.spec_from_file_location("rt012_fixture", root / "tests/integration/test_browser_sessions.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = module.origin.__wrapped__()
    origin = next(source)
    for key in tuple(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", "candidate")
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    captured = {}
    original = gateway.create_app
    def capture(**kwargs):
        captured.update(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(gateway, "create_app", capture)
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: None)
    try:
        gateway.main()
        class Model:
            name = "independent-local"
            async def stream(self, request, cancellation):
                if request.messages[-1].role == "user":
                    yield ModelChunk("tool_request", tool_call=ToolCall("nav", "browser.navigate+read", {"url":origin}))
                else:
                    yield ModelChunk("text", "complete")
                yield ModelChunk("finished")
        captured["on_turn"].__self__._model = Model()
        pool = captured["on_shutdown"].__self__
        with TestClient(original(**captured)) as client:
            token = client.post("/v1/session", headers={"origin":"http://127.0.0.1:8000"}).json()["token"]
            headers = {"authorization":f"Bearer {token}"}
            turns = {}
            for session in ("A", "B"):
                response = client.post(f"/v1/conversations/{session}/turns", headers=headers, json={"text":f"navigate {session}"})
                assert response.status_code == 200
                turns[session] = response.json()["turn_id"]
                assert client.get(f"/v1/agent-runs/{session}", headers=headers).json()["state"] == "completed"
            drivers = {k:e.driver for k,e in pool._sessions.items()}
            assert set(drivers) == {"A", "B"}
            response = client.post(f"/v1/turns/{turns['A']}/cancel", headers=headers, json={"reason":"owner stop"})
            assert response.status_code == 200
            assert set(pool._sessions) == {"B"}
            assert drivers["A"]._browser is None and drivers["A"]._playwright is None
            assert drivers["B"]._browser is not None
        assert not pool._sessions and drivers["B"]._browser is None
    finally:
        source.close()
