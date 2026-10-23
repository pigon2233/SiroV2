from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

from siro.services.tools.execution import execute_bounded_argv


@pytest.mark.asyncio
async def test_large_dual_pipe_output_is_bounded_without_deadlock(tmp_path: Path) -> None:
    baseline = current_rss()
    peak = baseline
    stopped = asyncio.Event()

    async def measure() -> None:
        nonlocal peak
        while not stopped.is_set():
            peak = max(peak, current_rss())
            await asyncio.sleep(0.001)

    monitor = asyncio.create_task(measure())
    try:
        result = await execute_bounded_argv(
            (
                sys.executable,
                "-c",
                "import os; block=b'x'*65536; "
                "[(os.write(1,block),os.write(2,block)) for _ in range(800)]",
            ),
            cwd=tmp_path,
            environment=os.environ.copy(),
            timeout=20,
        )
    finally:
        stopped.set()
        await monitor
    retained = len(str(result["stdout"]).encode()) + len(str(result["stderr"]).encode())
    assert retained == 65536
    assert result["truncated"] is True
    assert result["returncode"] == 0
    assert peak - baseline < 32 * 1024 * 1024


def current_rss() -> int:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    raise AssertionError("RSS unavailable")


@pytest.mark.asyncio
async def test_nonzero_exit_preserves_observation_and_exact_limit(tmp_path: Path) -> None:
    result = await execute_bounded_argv(
        (sys.executable, "-c", "import os; os.write(1,b'abc'); os.write(2,b'def'); exit(7)"),
        cwd=tmp_path,
        environment=os.environ.copy(),
        timeout=5,
        output_limit=6,
    )
    assert result["stdout"] == "abc"
    assert result["stderr"] == "def"
    assert result["returncode"] == 7
    assert result["truncated"] is False
    assert result["cwd"] == str(tmp_path)


@pytest.mark.asyncio
@pytest.mark.parametrize("flood", [False, True])
async def test_timeout_reaps_direct_child(tmp_path: Path, flood: bool) -> None:
    child_code = "import os,time; open('child.pid','w').write(str(os.getpid())); "
    child_code += "exec(\"while True: os.write(1,b'x'*65536)\")" if flood else "time.sleep(30)"
    with pytest.raises(TimeoutError):
        await execute_bounded_argv(
            (
                sys.executable,
                "-c",
                child_code,
            ),
            cwd=tmp_path,
            environment=os.environ.copy(),
            timeout=1,
        )

    pid = int((tmp_path / "child.pid").read_text())
    assert not Path(f"/proc/{pid}").exists(), "timed-out direct child must be reaped"


@pytest.mark.asyncio
async def test_detach_preserves_existing_result(tmp_path: Path) -> None:
    result = await execute_bounded_argv(
        (sys.executable, "-c", "pass"),
        cwd=tmp_path,
        environment=os.environ.copy(),
        timeout=5,
        detach=True,
    )
    assert result["state"] == "started"
    assert isinstance(result["pid"], int)
    assert "stdout" not in result


@pytest.mark.parametrize("profile", ["legacy", "candidate"])
@pytest.mark.parametrize("mutate_profile", [False, True])
def test_production_main_routes_real_argv_and_preserves_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str, mutate_profile: bool
) -> None:
    import json
    from collections.abc import AsyncIterator
    from unittest.mock import AsyncMock

    import uvicorn
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from siro.adapters.models import ollama
    from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, ToolCall
    from siro.services.presentation.gateway import main

    class Model:
        name = "synthetic-main-provider"

        def __init__(self) -> None:
            self.requests: list[ModelRequest] = []

        async def stream(
            self, request: ModelRequest, cancellation: CancellationToken
        ) -> AsyncIterator[ModelChunk]:
            self.requests.append(request)
            if len(self.requests) == 1:
                if mutate_profile:
                    monkeypatch.setenv(
                        "SIRO_RUNTIME_PROFILE", "legacy" if profile == "candidate" else "candidate"
                    )
                yield ModelChunk(
                    "tool_request",
                    tool_call=ToolCall(
                        "main-call",
                        "computer.execute",
                        {
                            "argv": [
                                sys.executable,
                                "-c",
                                "import os; os.write(1,b'out'); os.write(2,b'err'); exit(7)",
                            ],
                            "cwd": str(tmp_path),
                        },
                    ),
                )
            else:
                yield ModelChunk("text", "done")
            yield ModelChunk("finished")

    from siro.services.tools import execution

    bounded = AsyncMock(wraps=execute_bounded_argv)
    monkeypatch.setattr(execution, "execute_bounded_argv", bounded)
    model = Model()
    for name in tuple(os.environ):
        if name.startswith("SIRO_") or name == "GROQ_API_KEY":
            monkeypatch.delenv(name)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    # Synthetic provider has no native tokenizer; this fixture tests executor lifecycle.
    monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "0")
    monkeypatch.setenv("SIRO_OLLAMA_MODEL", "synthetic")
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", profile)
    monkeypatch.setattr(ollama, "OllamaAdapter", lambda **kwargs: model)

    def run(app: FastAPI, **kwargs: object) -> None:
        with TestClient(app) as client:
            token = client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"}).json()[
                "token"
            ]
            response = client.post(
                "/v1/conversations/main/turns",
                headers={"Authorization": f"Bearer {token}"},
                json={"text": "run synthetic check"},
            )
            assert response.status_code == 200

    monkeypatch.setattr(uvicorn, "run", run)
    main()
    assert len(model.requests) == 2
    assert bounded.await_count == (1 if profile == "candidate" else 0)
    if profile == "candidate":
        observation = json.loads(model.requests[1].messages[-1].content)
        # The gateway opts in to the sampled network record; nothing else may change.
        assert observation.pop("network_sample")["status"] in {"sampled", "unsupported"}
        assert observation == {
            "argv": [
                sys.executable,
                "-c",
                "import os; os.write(1,b'out'); os.write(2,b'err'); exit(7)",
            ],
            "cwd": str(tmp_path),
            "returncode": 7,
            "stdout": "out",
            "stderr": "err",
            "truncated": False,
        }
    else:
        assert model.requests[1].messages == ()
        assert "'returncode': 7" in model.requests[1].prompt
        assert "'stdout': 'out'" in model.requests[1].prompt
