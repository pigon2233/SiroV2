"""Windows foreground-window and screen providers, reached through PowerShell (also from WSL).

Each call is one short PowerShell run, made only while the owner's switch is on. Where
PowerShell is not reachable there is no provider and the context simply stays unknown.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
from collections.abc import Awaitable, Callable
from contextlib import suppress

from siro.services.context.work_context import AppSnapshot, WorkContext

WSL_POWERSHELL = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
RUN_SECONDS = 10.0
MAX_OUTPUT = 4 * 1024 * 1024
Runner = Callable[[str], Awaitable[str | None]]

_NATIVE = (
    "Add-Type -MemberDefinition '"
    "[StructLayout(LayoutKind.Sequential)] public struct R{public int L,T,Rt,B;}"
    '[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();'
    '[DllImport("user32.dll")] public static extern int GetWindowThreadProcessId(IntPtr h,out int p);'  # noqa: E501
    '[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h,out R r);'
    '[DllImport("user32.dll",CharSet=CharSet.Unicode)] '
    "public static extern int GetWindowText(IntPtr h,System.Text.StringBuilder s,int n);"
    "' -Name N -Namespace W;"
)
FOREGROUND_SCRIPT = (
    "$ErrorActionPreference='Stop';Add-Type -AssemblyName System.Windows.Forms;"
    + _NATIVE
    + "$h=[W.N]::GetForegroundWindow();"
    'if($h -eq [IntPtr]::Zero){\'{"app":"","title":"","locked":true,"fullscreen":false}\';exit}'
    "$p=0;[void][W.N]::GetWindowThreadProcessId($h,[ref]$p);"
    "$n=(Get-Process -Id $p).ProcessName;$s=New-Object System.Text.StringBuilder 256;"
    "[void][W.N]::GetWindowText($h,$s,256);$r=New-Object W.N+R;[void][W.N]::GetWindowRect($h,[ref]$r);"  # noqa: E501
    "$b=[System.Windows.Forms.Screen]::FromHandle($h).Bounds;"
    "$f=($r.L -le $b.X -and $r.T -le $b.Y -and $r.Rt -ge ($b.X+$b.Width) -and $r.B -ge ($b.Y+$b.Height));"  # noqa: E501
    "$l=($n -in 'LockApp','LogonUI');"
    "ConvertTo-Json -Compress @{app=$n;title=$s.ToString();locked=$l;fullscreen=($f -and -not $l)}"
)
SCREEN_SCRIPT = (
    "$ErrorActionPreference='Stop';Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
    "$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
    "$i=New-Object System.Drawing.Bitmap($b.Width,$b.Height);"
    "$g=[System.Drawing.Graphics]::FromImage($i);$g.CopyFromScreen($b.Location,"
    "[System.Drawing.Point]::Empty,$b.Size);"
    "$w=640;$h=[int]($b.Height*$w/$b.Width);$t=New-Object System.Drawing.Bitmap($w,$h);"
    "$q=[System.Drawing.Graphics]::FromImage($t);$q.DrawImage($i,0,0,$t.Width,$t.Height);"
    "$m=New-Object System.IO.MemoryStream;$t.Save($m,[System.Drawing.Imaging.ImageFormat]::Png);"
    "[Convert]::ToBase64String($m.ToArray())"
)


def powershell_path() -> str | None:
    if os.environ.get("WSL_DISTRO_NAME") and os.path.exists(WSL_POWERSHELL):
        return WSL_POWERSHELL
    return shutil.which("powershell.exe") or shutil.which("powershell")


def encoded(script: str) -> str:
    # -EncodedCommand keeps the quotes in the script away from the argument parser.
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


def powershell_runner() -> Runner | None:
    executable = powershell_path()
    if executable is None or not (os.name == "nt" or os.environ.get("WSL_DISTRO_NAME")):
        return None

    async def run(script: str) -> str | None:
        process = await asyncio.create_subprocess_exec(
            executable,
            "-NoProfile",
            "-NonInteractive",
            "-EncodedCommand",
            encoded(script),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            out, _ = await asyncio.wait_for(process.communicate(), RUN_SECONDS)
        except (TimeoutError, asyncio.CancelledError):
            with suppress(ProcessLookupError):
                process.kill()
            raise
        if process.returncode != 0 or len(out) > MAX_OUTPUT:
            return None
        return out.decode("utf-8", errors="replace").strip()

    return run


def parse_foreground(text: str | None) -> AppSnapshot | None:
    if not text:
        return None
    try:
        data = json.loads(text.splitlines()[-1])
    except (ValueError, IndexError):
        return None
    if not isinstance(data, dict):
        return None
    app, title = data.get("app"), data.get("title")
    if not isinstance(app, str) or not isinstance(title, str):
        return None
    return AppSnapshot(
        app,
        title,
        locked=data.get("locked") is True,
        fullscreen=data.get("fullscreen") is True,
    )


def parse_screen(text: str | None) -> bytes | None:
    if not text:
        return None
    try:
        return base64.b64decode(text.splitlines()[-1], validate=True)
    except (ValueError, IndexError):
        return None


class AppObserver:
    """Polls the foreground window only while the owner keeps app metadata switched on."""

    def __init__(self, context: WorkContext, run: Runner, *, interval: float = 15.0) -> None:
        self._context = context
        self._run = run
        self._interval = interval
        self._task: asyncio.Task[None] | None = None

    async def sample(self) -> bool:
        if not self._context.source_enabled("app_metadata"):
            return False
        snapshot = parse_foreground(await self._run(FOREGROUND_SCRIPT))
        if snapshot is None:
            return False
        # Re-check: the switch may have gone off while PowerShell was running.
        return self._context.ingest_app(snapshot) is not None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="siro-app-observer")

    async def close(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            with suppress(Exception):  # a failed sample is simply no observation
                await self.sample()


def screen_capture(run: Runner) -> Callable[[], Awaitable[bytes | None]]:
    async def capture() -> bytes | None:
        return parse_screen(await run(SCREEN_SCRIPT))

    return capture
