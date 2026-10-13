"""Single-job skill worker process; invoked only by WorkerSupervisor."""

from __future__ import annotations

import importlib
import json
import os
import resource
import sys
from collections.abc import Callable
from typing import cast


def main() -> int:
    memory_bytes = int(os.environ["SIRO_WORKER_MEMORY_MB"]) * 1024 * 1024
    cpu_seconds = int(os.environ["SIRO_WORKER_CPU_SECONDS"])
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
    root = os.environ["SIRO_SKILL_ROOT"]
    sys.path.insert(0, root)
    module_name, function_name = (
        os.environ["SIRO_SKILL_ENTRYPOINT"].removeprefix("python:").split(":", 1)
    )
    function = cast(
        Callable[[dict[str, object]], object],
        getattr(importlib.import_module(module_name), function_name),
    )
    request_path = os.environ.get("SIRO_SKILL_REQUEST")
    if request_path is None:
        payload = sys.stdin.buffer.read(65537)
    else:
        with open(request_path, "rb") as handle:
            payload = handle.read(65537)
    if len(payload) > 65536:
        raise ValueError("worker input exceeded its byte limit")
    request = json.loads(payload)
    if not isinstance(request, dict):
        raise ValueError("worker input must be an object")
    response = function({str(key): value for key, value in request.items()})
    sys.stdout.write(json.dumps(response, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
