"""Synthetic executor-only cancellation measurement; no private runtime data."""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from siro.services.tools.execution import ExecutionCancelled, ExecutionContext, execute_bounded_argv

CODE = """
import os,signal,time
child=os.fork()
if child==0:
 signal.signal(signal.SIGTERM,signal.SIG_IGN)
 open('child','w').write(str(os.getpid()))
else:
 open('parent','w').write(str(os.getpid()))
while True: time.sleep(.01)
"""


def running(pid):
    p = Path(f"/proc/{pid}/stat")
    try:
        return p.read_text().split(") ", 1)[1][0] != "Z"
    except (FileNotFoundError, ProcessLookupError):
        return False


async def main():
    rows = []
    for i in range(3):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            ctx = ExecutionContext("synthetic-run", "synthetic-session", "synthetic-epoch")
            task = asyncio.create_task(
                execute_bounded_argv(
                    (sys.executable, "-c", CODE),
                    cwd=cwd,
                    environment=os.environ.copy(),
                    timeout=30,
                    context=ctx,
                )
            )
            async with asyncio.timeout(3):
                while not all(
                    (cwd / n).exists() and (cwd / n).read_text().strip()
                    for n in ["parent", "child"]
                ):
                    await asyncio.sleep(0.005)
            parent, child = [int((cwd / n).read_text()) for n in ["parent", "child"]]
            started = asyncio.get_running_loop().time()
            ctx.cancellation.cancel()
            try:
                await task
            except ExecutionCancelled:
                pass
            elapsed = asyncio.get_running_loop().time() - started
            row = {
                "attempt": i + 1,
                "cleanup_seconds": elapsed,
                "direct_child_reaped": not Path(f"/proc/{parent}").exists(),
                "descendant_stopped": not running(child),
            }
            assert elapsed < 2 and row["direct_child_reaped"] and row["descendant_stopped"]
            rows.append(row)
    Path(__file__).with_name("measurement.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps(rows, indent=2))


asyncio.run(main())
