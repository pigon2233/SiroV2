from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


def executable(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def desktop_project(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    project = tmp_path / '專案 space %f $literal `literal` "quote" \\backslash'
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    for name in ("start-desktop", "install-desktop"):
        executable(scripts / name, ROOT.joinpath("scripts", name).read_text())
    home = tmp_path / "home"
    home.mkdir()
    environment = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "XDG_DATA_HOME": str(tmp_path / "menu"),
        "SIRO_TEST_UV_LOG": str(tmp_path / "uv.log"),
        "SIRO_TEST_GJS_LOG": str(tmp_path / "gjs.log"),
        "SIRO_TEST_OUTPUT": str(tmp_path / "menu-result.json"),
    }
    # The command is deliberately absent from PATH, like a desktop login session.
    executable(
        home / ".local/bin/uv",
        "#!/bin/bash\n"
        'printf "%s\\n" "$@" >> "$SIRO_TEST_UV_LOG"\n'
        '[[ "$1" == run && "$2" == --no-sync && "$3" == python ]] || exit 99\n'
        "shift 3\n"
        f'exec {shlex.quote(sys.executable)} "$@"\n',
    )
    return project, environment


def run_script(
    project: Path, environment: dict[str, str], name: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", str(project / "scripts" / name)],
        cwd="/",
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )


def install(project: Path, environment: dict[str, str]) -> Path:
    result = run_script(project, environment, "install-desktop")
    assert result.returncode == 0, result.stderr
    return Path(environment["XDG_DATA_HOME"]) / "applications/org.siro.Companion.desktop"


@pytest.mark.parametrize("token_budget", ["0", "1"])
def test_menu_uses_external_python_without_login_shell_or_provider_secrets(
    desktop_project: tuple[Path, dict[str, str]],
    token_budget: str,
) -> None:
    project, environment = desktop_project
    runtime = str(project / 'target %U $cash `tick` "quoted" \\literal/runtime')
    environment.update(
        UV_PROJECT_ENVIRONMENT="/synthetic/external-venv",
        UV_PYTHON="3.12",
        CARGO_TARGET_DIR=runtime.rsplit("/", 1)[0],
        SIRO_RUNTIME_BINARY=runtime,
        UV_CACHE_DIR=str(project / "cache"),
        SIRO_OPENAI_API_KEY="synthetic-secret-must-not-be-persisted",  # pragma: allowlist secret
        SIRO_OPENAI_MODEL="synthetic-model-must-not-be-persisted",
        GROQ_API_KEY="synthetic-groq-key-must-not-be-persisted",  # pragma: allowlist secret
        SIRO_RELEASE_SIGNING_KEY="synthetic-signing-key-must-not-be-persisted",
        SIRO_CONTEXT_TOKEN_BUDGET_ENABLED=token_budget,
        SIRO_DATA_DIR=str(project / "external data"),
        SIRO_LOG_DIR=str(project / "external logs"),
        SIRO_LIVE2D_DIST=str(project / "external renderer"),
        SIRO_GATEWAY_PORT="18765",
        SIRO_OLLAMA_MODEL="qwen3:4b",
        SIRO_QWEN_VOICE_PROFILE=str(project / "selected B profile.json"),
    )
    executable(
        project / "scripts/start-companion",
        f"#!{sys.executable}\n"
        "import json, os\n"
        "from pathlib import Path\n"
        "keys=['PATH','UV_PROJECT_ENVIRONMENT','UV_PYTHON','CARGO_TARGET_DIR',"
        "'SIRO_RUNTIME_BINARY','UV_CACHE_DIR','SIRO_OPENAI_API_KEY',"
        "'SIRO_CONTEXT_TOKEN_BUDGET_ENABLED','SIRO_DATA_DIR','SIRO_LOG_DIR',"
        "'SIRO_LIVE2D_DIST','SIRO_GATEWAY_PORT','SIRO_OLLAMA_MODEL','GROQ_API_KEY','SIRO_QWEN_VOICE_PROFILE']\n"
        "Path(os.environ['SIRO_TEST_OUTPUT']).write_text("
        "json.dumps({key:os.environ.get(key) for key in keys}))\n",
    )
    entry = install(project, environment)
    contents = entry.read_text()
    assert "synthetic-secret" not in contents
    assert "synthetic-model" not in contents
    assert "synthetic-signing" not in contents
    assert "synthetic-groq" not in contents
    assert "--no-sync" in Path(environment["SIRO_TEST_UV_LOG"]).read_text()
    assert not (project / ".venv").exists()
    # Gio is the native desktop launcher, so this verifies both Desktop Entry
    # escaping and Exec parsing rather than a shell approximation of them.
    gio = shutil.which("gio")
    assert gio is not None, "Gio is required by the native GTK desktop host"
    clean_environment = {
        key: value for key, value in environment.items() if key.startswith("SIRO_TEST_")
    }
    clean_environment.update(HOME=environment["HOME"], PATH="/usr/bin:/bin", LANG="C.UTF-8")
    launched = subprocess.run(
        [gio, "launch", str(entry)],
        env=clean_environment,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert launched.returncode == 0, launched.stderr
    output = Path(environment["SIRO_TEST_OUTPUT"])
    for _ in range(100):
        if output.exists():
            break
        time.sleep(0.02)
    actual = json.loads(output.read_text())
    assert actual["UV_PROJECT_ENVIRONMENT"] == sys.prefix
    assert actual["UV_PYTHON"] == sys.executable
    assert actual["SIRO_RUNTIME_BINARY"] == runtime
    assert actual["CARGO_TARGET_DIR"] == environment["CARGO_TARGET_DIR"]
    assert actual["UV_CACHE_DIR"] == environment["UV_CACHE_DIR"]
    assert actual["SIRO_OPENAI_API_KEY"] is None
    assert actual["GROQ_API_KEY"] is None
    assert actual["SIRO_OLLAMA_MODEL"] == "qwen3:4b"
    assert actual["SIRO_QWEN_VOICE_PROFILE"] == environment["SIRO_QWEN_VOICE_PROFILE"]
    assert actual["SIRO_CONTEXT_TOKEN_BUDGET_ENABLED"] == token_budget
    for name in ("SIRO_DATA_DIR", "SIRO_LOG_DIR", "SIRO_LIVE2D_DIST", "SIRO_GATEWAY_PORT"):
        assert actual[name] == environment[name]
    for name in ("SIRO_DATA_DIR", "SIRO_LOG_DIR", "SIRO_LIVE2D_DIST"):
        assert not Path(environment[name]).exists()
    assert actual["PATH"].split(os.pathsep)[0] == str(Path(environment["HOME"]) / ".local/bin")


@pytest.mark.parametrize(
    "unsafe", ["bad\nExec=malicious", "bad\rvalue", "bad\tvalue", "bad\x7fvalue"]
)
def test_menu_rejects_control_characters_before_overwriting_entry(
    desktop_project: tuple[Path, dict[str, str]], unsafe: str
) -> None:
    project, environment = desktop_project
    entry = install(project, environment)
    original = entry.read_bytes()
    environment["SIRO_RUNTIME_BINARY"] = unsafe
    result = run_script(project, environment, "install-desktop")
    assert result.returncode != 0
    assert "控制字元" in result.stderr
    assert entry.read_bytes() == original


def test_menu_without_uv_exits_with_setup_instruction(
    desktop_project: tuple[Path, dict[str, str]],
) -> None:
    project, environment = desktop_project
    Path(environment["HOME"]).joinpath(".local/bin/uv").unlink()
    result = run_script(project, environment, "install-desktop")
    assert result.returncode == 2
    assert "uv" in result.stderr
    assert not Path(environment["XDG_DATA_HOME"]).exists()


@pytest.mark.parametrize("invalid", ["", "false", "true", "2", "0\nExec=malicious"])
def test_menu_rejects_invalid_explicit_token_policy_without_overwriting_entry(
    desktop_project: tuple[Path, dict[str, str]], invalid: str
) -> None:
    project, environment = desktop_project
    entry = install(project, environment)
    original = entry.read_bytes()
    assert "SIRO_CONTEXT_TOKEN_BUDGET_ENABLED" not in entry.read_text()
    environment["SIRO_CONTEXT_TOKEN_BUDGET_ENABLED"] = invalid
    result = run_script(project, environment, "install-desktop")
    assert result.returncode != 0
    assert "SIRO_CONTEXT_TOKEN_BUDGET_ENABLED" in result.stderr
    assert entry.read_bytes() == original


def test_installer_runs_actual_selected_uv_environment_without_repo_venv(tmp_path: Path) -> None:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("SIRO_")}
    environment.update(
        XDG_DATA_HOME=str(tmp_path / "native-menu"),
        UV_PROJECT_ENVIRONMENT=sys.prefix,
        UV_PYTHON=sys.executable,
    )
    result = run_script(ROOT, environment, "install-desktop")
    assert result.returncode == 0, result.stderr
    entry = Path(environment["XDG_DATA_HOME"]) / "applications/org.siro.Companion.desktop"
    contents = entry.read_text()
    assert f"UV_PROJECT_ENVIRONMENT={sys.prefix}" in contents
    assert f"UV_PYTHON={sys.executable}" in contents
    assert "SIRO_CONTEXT_TOKEN_BUDGET_ENABLED" not in contents
    assert "SIRO_OLLAMA_MODEL" not in contents


@pytest.mark.parametrize("invalid", ["", " ", "\nInjected", "qwen3:4b\nExec=malicious"])
def test_menu_rejects_empty_or_control_local_model_without_overwriting_entry(
    desktop_project: tuple[Path, dict[str, str]], invalid: str
) -> None:
    project, environment = desktop_project
    entry = install(project, environment)
    original = entry.read_bytes()
    environment["SIRO_OLLAMA_MODEL"] = invalid
    result = run_script(project, environment, "install-desktop")
    assert result.returncode != 0
    assert entry.read_bytes() == original


@pytest.mark.parametrize("port", ["1024", "65535"])
def test_menu_preserves_explicit_gateway_port_boundaries(
    desktop_project: tuple[Path, dict[str, str]], port: str
) -> None:
    project, environment = desktop_project
    environment["SIRO_GATEWAY_PORT"] = port
    entry = install(project, environment)
    assert f'"SIRO_GATEWAY_PORT={port}"' in entry.read_text()


@pytest.mark.parametrize(
    "invalid",
    [
        "0",
        "1023",
        "65536",
        "8000x",
        "-8000",
        "8e3",
        " 8000",
        "08000",
        "\uff18\uff10\uff10\uff10",
        "9" * 5000,
        "8000\nExec=malicious",
    ],
)
def test_menu_rejects_invalid_gateway_port_without_overwriting_entry(
    desktop_project: tuple[Path, dict[str, str]], invalid: str
) -> None:
    project, environment = desktop_project
    entry = install(project, environment)
    original = entry.read_bytes()
    assert "SIRO_GATEWAY_PORT" not in entry.read_text()
    environment["SIRO_GATEWAY_PORT"] = invalid
    result = run_script(project, environment, "install-desktop")
    assert result.returncode != 0
    assert "SIRO_GATEWAY_PORT" in result.stderr
    assert entry.read_bytes() == original


@pytest.fixture
def backend() -> Iterator[tuple[str, list[tuple[str, str | None, str | None]], dict[str, str]]]:
    requests: list[tuple[str, str | None, str | None]] = []
    state = {"model": "configured-synthetic", "desktop_status": "200"}

    class Handler(BaseHTTPRequestHandler):
        def handle_request(self) -> None:
            requests.append(
                (self.path, self.headers.get("Origin"), self.headers.get("Authorization"))
            )
            payload: dict[str, object]
            if self.path == "/v1/session":
                payload, status = {"token": "synthetic-short-lived-token"}, 200
            elif self.path == "/v1/runtime":
                payload, status = {"routes": {"model": state["model"]}}, 200
            else:
                payload, status = {}, int(state["desktop_status"])
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = handle_request
        do_POST = handle_request

        def log_message(self, *_args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests, state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def native_stub(project: Path, environment: dict[str, str]) -> None:
    binaries = project / "native-bin"
    executable(
        binaries / "gjs",
        '#!/bin/bash\nprintf "%s\\n" "$@" > "$SIRO_TEST_GJS_LOG"\n',
    )
    environment["PATH"] = str(binaries) + ":" + environment["PATH"]


def test_desktop_external_environment_preserves_origin_token_and_host_invocation(
    desktop_project: tuple[Path, dict[str, str]],
    backend: tuple[str, list[tuple[str, str | None, str | None]], dict[str, str]],
) -> None:
    project, environment = desktop_project
    native_stub(project, environment)
    base, requests, _ = backend
    environment.update(SIRO_DESKTOP_URL=base + "/desktop", UV_PROJECT_ENVIRONMENT="/external/venv")
    result = run_script(project, environment, "start-desktop")
    assert result.returncode == 0, result.stderr
    assert requests == [
        ("/v1/session", base, None),
        ("/v1/runtime", None, "Bearer synthetic-short-lived-token"),
        ("/desktop", None, None),
    ]
    assert Path(environment["SIRO_TEST_GJS_LOG"]).read_text() == "-m\ndesktop/host.js\n"
    assert Path(environment["SIRO_TEST_UV_LOG"]).read_text() == "run\n--no-sync\npython\n-\n"
    assert "synthetic-short-lived-token" not in result.stdout + result.stderr
    assert not (project / ".venv").exists()


@pytest.mark.parametrize("bus_running", [False, True])
def test_wsl_desktop_selects_chewing_and_passes_ibus_to_native_host(
    desktop_project: tuple[Path, dict[str, str]],
    backend: tuple[str, list[tuple[str, str | None, str | None]], dict[str, str]],
    bus_running: bool,
) -> None:
    project, environment = desktop_project
    native_stub(project, environment)
    binaries = project / "native-bin"
    executable(
        binaries / "ibus",
        "#!/bin/bash\n"
        'if [[ "$1" == list-engine ]]; then echo "  chewing - Chewing"; exit 0; fi\n'
        'if [[ "$1" == engine && $# == 1 ]]; then '
        'if [[ "$SIRO_TEST_BUS_RUNNING" == 1 ]]; then echo xkb:us::eng; exit 0; '
        "else exit 1; fi; fi\n"
        'if [[ "$1" == engine && "$2" == chewing ]]; then '
        'echo chewing >> "$SIRO_TEST_IME_LOG"; exit 0; fi\n'
        "exit 1\n",
    )
    executable(binaries / "ibus-daemon", '#!/bin/bash\necho daemon >> "$SIRO_TEST_IME_LOG"\n')
    executable(
        binaries / "gjs",
        '#!/bin/bash\nprintf "%s\\n" "$GTK_IM_MODULE" "$XMODIFIERS" > "$SIRO_TEST_GJS_LOG"\n',
    )
    base, _, _ = backend
    environment.update(
        SIRO_DESKTOP_URL=base + "/desktop",
        WSL_DISTRO_NAME="Ubuntu",
        SIRO_TEST_BUS_RUNNING="1" if bus_running else "0",
        SIRO_TEST_IME_LOG=str(project / "ime.log"),
    )
    result = run_script(project, environment, "start-desktop")
    assert result.returncode == 0, result.stderr
    assert Path(environment["SIRO_TEST_GJS_LOG"]).read_text() == "ibus\n@im=ibus\n"
    assert Path(environment["SIRO_TEST_IME_LOG"]).read_text().splitlines() == (
        ["chewing"] if bus_running else ["daemon", "chewing"]
    )


@pytest.mark.parametrize(
    "modified",
    [
        "{base}/desktop?token=synthetic",
        "{base}/desktop#fragment",
        "{base}/desktop/other",
        "http://example.invalid/desktop",
        "http://synthetic:credential@127.0.0.1/desktop",  # pragma: allowlist secret
        "https://127.0.0.1/desktop",
    ],
)
def test_desktop_rejects_modified_url_before_network_or_native_host(
    desktop_project: tuple[Path, dict[str, str]],
    backend: tuple[str, list[tuple[str, str | None, str | None]], dict[str, str]],
    modified: str,
) -> None:
    project, environment = desktop_project
    native_stub(project, environment)
    base, requests, _ = backend
    environment["SIRO_DESKTOP_URL"] = modified.format(base=base)
    result = run_script(project, environment, "start-desktop")
    assert result.returncode != 0
    assert "exact loopback" in result.stderr
    assert not requests
    assert not Path(environment["SIRO_TEST_GJS_LOG"]).exists()


@pytest.mark.parametrize("model,status", [("offline", "200"), ("configured-synthetic", "503")])
def test_desktop_refuses_offline_service_or_missing_renderer(
    desktop_project: tuple[Path, dict[str, str]],
    backend: tuple[str, list[tuple[str, str | None, str | None]], dict[str, str]],
    model: str,
    status: str,
) -> None:
    project, environment = desktop_project
    native_stub(project, environment)
    base, _, state = backend
    state.update(model=model, desktop_status=status)
    environment["SIRO_DESKTOP_URL"] = base + "/desktop"
    result = run_script(project, environment, "start-desktop")
    assert result.returncode != 0
    assert not Path(environment["SIRO_TEST_GJS_LOG"]).exists()
    assert "synthetic-short-lived-token" not in result.stdout + result.stderr
