from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPOSITORY = Path(__file__).resolve().parents[2]


def probe(tmp_path: Path, code: str) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env={
            "PATH": os.defpath,
            "PYTHONPATH": str(REPOSITORY / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "SIRO_DATA_DIR": str(tmp_path / "unopened-data"),
        },
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert not result.stderr, result.stderr
    output: dict[str, Any] = json.loads(result.stdout)
    assert not (tmp_path / "unopened-data").exists()
    return output


def test_busy_gateway_rejects_before_optional_kokoro_import(tmp_path: Path) -> None:
    result = probe(
        tmp_path,
        """import importlib.abc, json, sys
from siro.adapters import data_ownership as ownership
imports, owners = [], []
class ForbidSDK(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname in {'kokoro_onnx', 'onnxruntime'}:
            imports.append(fullname)
            raise ImportError('controlled optional SDK failure')
        return None
def busy(database):
    owners.append('acquire')
    raise ownership.DataOwnerBusyError()
ownership.exclusive_data_owner = busy
sys.meta_path.insert(0, ForbidSDK())
try:
    from siro.services.presentation.gateway import main
    main()
except (ImportError, SystemExit) as error:
    print(json.dumps({'type':type(error).__name__, 'message':str(error),
                      'imports':imports, 'owners':owners}))
""",
    )
    assert result == {
        "type": "SystemExit",
        "message": "SIRO data is already in use",
        "imports": [],
        "owners": ["acquire"],
    }


STUB_SDK = """import asyncio, importlib.abc, importlib.util, json, sys, threading
events = []
main_thread = threading.get_ident()
block_create = False
entered, release, finished = threading.Event(), threading.Event(), threading.Event()
class StubKokoro:
    def __init__(self, model, voices):
        events.append(['construct', threading.get_ident(), model, voices])
    def get_voice_style(self, name):
        import numpy as np
        events.append(['voice', name])
        return np.array([0.0, 1.0], dtype=np.float32)
    def create(self, text, *, voice, speed, is_phonemes):
        import numpy as np
        events.append(['create', threading.get_ident(), text, voice.tolist(), speed, is_phonemes])
        if block_create:
            entered.set()
            if not release.wait(3):
                raise TimeoutError('controlled render was not released')
        finished.set()
        return np.array([0.25, -0.25], dtype=np.float32), 24000
class StubLoader(importlib.abc.Loader):
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        events.append(['import', threading.get_ident()])
        module.Kokoro = StubKokoro
class StubFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == 'kokoro_onnx':
            return importlib.util.spec_from_loader(fullname, StubLoader())
        if fullname == 'onnxruntime':
            raise AssertionError('real inference SDK must never load in this synthetic test')
        return None
sys.meta_path.insert(0, StubFinder())
from siro.services.audio import tts
class StubG2P:
    def __init__(self, *, version):
        events.append(['g2p', version])
    def __call__(self, text):
        return 'synthetic-phonemes', None
tts.zh.ZHG2P = StubG2P
speaker = tts.KokoroLocalTTS('synthetic-model', 'synthetic-voices', {'synthetic-voice':1.0})
"""


def test_pure_audio_helpers_and_construction_do_not_import_sdk(tmp_path: Path) -> None:
    result = probe(
        tmp_path,
        STUB_SDK
        + """plan = tts.plan_speech('hello')
print(json.dumps({'events':events, 'segments':plan['segments'],
                  'model_loaded':speaker._model is not None,
                  'onnx_loaded':'onnxruntime' in sys.modules}))
""",
    )
    assert result == {
        "events": [],
        "segments": ["hello。"],
        "model_loaded": False,
        "onnx_loaded": False,
    }


def test_render_imports_sdk_on_worker_and_keeps_existing_cache_and_arguments(
    tmp_path: Path,
) -> None:
    result = probe(
        tmp_path,
        STUB_SDK
        + """async def render_twice():
    first = await speaker.render('hello', rate=1.2, pitch=0.3, energy=0.5)
    second = await speaker.render('again', rate=0.1, pitch=-0.3, energy=0.5)
    return [first[:4].decode(), second[:4].decode()]
headers = asyncio.run(render_twice())
print(json.dumps({'events':events, 'headers':headers, 'main_thread':main_thread,
                  'onnx_loaded':'onnxruntime' in sys.modules}))
""",
    )
    assert result["headers"] == ["RIFF", "RIFF"]
    assert result["onnx_loaded"] is False
    imports = [event for event in result["events"] if event[0] == "import"]
    constructors = [event for event in result["events"] if event[0] == "construct"]
    calls = [event for event in result["events"] if event[0] == "create"]
    assert len(imports) == len(constructors) == 1
    assert constructors[0][2:] == ["synthetic-model", "synthetic-voices"]
    assert [event for event in result["events"] if event[0] == "g2p"] == [["g2p", "1.0"]]
    assert len(calls) == 2
    assert calls[0][2:] == ["synthetic-phonemes", [0.0, 1.0], 1.2, True]
    assert calls[1][2:] == ["synthetic-phonemes", [0.0, 1.0], 0.65, True]
    assert all(event[1] != result["main_thread"] for event in imports + constructors + calls)


def test_sdk_failure_retains_type_and_occurs_only_on_owned_render(tmp_path: Path) -> None:
    result = probe(
        tmp_path,
        """import asyncio, importlib.abc, json, sys, threading
phase, imports = 'module-import', []
main_thread = threading.get_ident()
class SyntheticSDKError(RuntimeError):
    pass
class FailingSDK(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname in {'kokoro_onnx', 'onnxruntime'}:
            imports.append([fullname, threading.get_ident()])
            raise SyntheticSDKError('controlled SDK unavailable')
        return None
sys.meta_path.insert(0, FailingSDK())
try:
    from siro.services.audio.tts import KokoroLocalTTS
    phase = 'construction'
    speaker = KokoroLocalTTS('synthetic-model', 'synthetic-voices')
    phase = 'render'
    asyncio.run(speaker.render('hello', rate=1.0, pitch=0.0, energy=0.5))
except SyntheticSDKError as error:
    print(json.dumps({'phase':phase, 'type':type(error).__name__, 'message':str(error),
                      'imports':imports, 'main_thread':main_thread}))
""",
    )
    assert result["phase"] == "render"
    assert result["type"] == "SyntheticSDKError"
    assert result["message"] == "controlled SDK unavailable"
    assert len(result["imports"]) == 1
    assert result["imports"][0][0] == "kokoro_onnx"
    assert result["imports"][0][1] != result["main_thread"]


def test_render_cancellation_keeps_original_task_semantics_and_worker_can_finish(
    tmp_path: Path,
) -> None:
    result = probe(
        tmp_path,
        STUB_SDK
        + """block_create = True
async def cancel_render():
    task = asyncio.create_task(speaker.render('hello', rate=1.0, pitch=0.0, energy=0.5))
    try:
        if not await asyncio.to_thread(entered.wait, 3):
            raise TimeoutError('controlled render did not start')
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return True
        raise AssertionError('cancelled render returned audio')
    finally:
        release.set()
cancelled = asyncio.run(cancel_render())
print(json.dumps({'cancelled':cancelled, 'finished':finished.is_set(),
                  'events':events, 'main_thread':main_thread}))
""",
    )
    assert result["cancelled"] is True
    assert result["finished"] is True
    imports = [event for event in result["events"] if event[0] == "import"]
    calls = [event for event in result["events"] if event[0] == "create"]
    assert len(imports) == len(calls) == 1
    assert all(event[1] != result["main_thread"] for event in imports + calls)
