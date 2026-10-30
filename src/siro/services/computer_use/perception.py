"""What SIRO may see of the desktop: sanitized observations, privacy blocklist, control allowlist.

Raw captures come from the Windows shell. Screen content is Sensitive (SECURITY_PRIVACY §3):
a blocked window never leaves with its pixels, and titles are scrubbed of secret-looking text.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass

ALLOW_ENV = "SIRO_COMPUTER_ALLOWED_PROCESSES"  # comma list, e.g. "game.exe,notepad.exe"
MAX_AGE_SECONDS = 3.0
_SECRET = re.compile(
    r"sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."
)
BLOCKED_PROCESSES = frozenset(
    {
        "keepass.exe",
        "keepassxc.exe",
        "1password.exe",
        "bitwarden.exe",
        "lastpass.exe",
        "dashlane.exe",
        "authy.exe",
        "winscp.exe",
        "putty.exe",
        "mstsc.exe",
        "taskmgr.exe",
        "regedit.exe",
        "mmc.exe",
        "credwiz.exe",
        "consent.exe",
        "lockapp.exe",
    }
)
BLOCKED_TITLE = re.compile(
    r"password|passcode|credential|one-time|2fa|otp|private key|wallet|seed phrase|"
    r"密碼|驗證碼|銀行|網銀|錢包|私鑰|登入|sign in|log ?in|bank",
    re.I,
)


@dataclass(frozen=True, slots=True)
class Observation:
    seq: int
    taken_at: float
    window_title: str
    process: str
    window_rect: tuple[int, int, int, int] | None  # left, top, width, height (physical px)
    screen: tuple[int, int]
    fingerprint: str  # coarse screen hash from the shell; equal fingerprints = no visible change
    image_png_b64: str | None = None
    image_size: tuple[int, int] | None = None  # pixels of the screenshot as sent
    # Screen area the screenshot covers: only the foreground window is ever sent, not the desktop.
    image_rect: tuple[int, int, int, int] | None = None
    focus_is_secret: bool = False
    blocked_reason: str | None = None
    window_id: str | None = None
    pid: int | None = None


def allowed_processes(env: Mapping[str, str] | None = None) -> frozenset[str]:
    raw = (os.environ if env is None else env).get(ALLOW_ENV, "")
    return frozenset(p.strip().lower() for p in raw.split(",") if p.strip())


def is_fresh(observation: Observation, now: float, max_age: float = MAX_AGE_SECONDS) -> bool:
    return 0 <= now - observation.taken_at <= max_age


def _rect(value: object) -> tuple[int, int, int, int] | None:
    if (
        isinstance(value, (list, tuple))
        and len(value) == 4
        and all(isinstance(v, int) and not isinstance(v, bool) for v in value)
        and value[2] > 0
        and value[3] > 0
    ):
        return (value[0], value[1], value[2], value[3])
    return None


def sanitize(raw: Mapping[str, object], *, seq: int, now: float) -> Observation:
    """Turn an untrusted shell report into an Observation; drop pixels of blocked windows."""
    title = _SECRET.sub("[redacted]", str(raw.get("title", ""))[:200])
    process = str(raw.get("process", "")).strip().lower()[:80]
    screen_raw = raw.get("screen")
    screen = (
        (int(screen_raw[0]), int(screen_raw[1]))
        if isinstance(screen_raw, (list, tuple))
        and len(screen_raw) == 2
        and all(isinstance(v, int) and v > 0 for v in screen_raw)
        else (0, 0)
    )
    image = raw.get("image_png_b64")
    image = image if isinstance(image, str) and len(image) <= 8_000_000 else None
    size_raw = raw.get("image_size")
    image_size = (
        (int(size_raw[0]), int(size_raw[1]))
        if isinstance(size_raw, (list, tuple))
        and len(size_raw) == 2
        and all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in size_raw)
        else None
    )
    if image is not None and image_size is None:
        image = None  # coordinates could not be mapped back to the screen
    image_rect = _rect(raw.get("image_rect")) or (0, 0, screen[0], screen[1])
    reason: str | None = None
    if screen == (0, 0):
        reason = "bad_screen_report"
    elif not process:
        reason = "unknown_window"
    elif process in BLOCKED_PROCESSES:
        reason = "blocked_process"
    elif BLOCKED_TITLE.search(title):
        reason = "blocked_title"
    secret_focus = raw.get("focus_is_secret") is True
    window_id = raw.get("window_id")
    if not isinstance(window_id, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", window_id):
        window_id = None
    pid = raw.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or not 0 < pid <= 0xFFFFFFFF:
        pid = None
    if secret_focus:
        reason = reason or "secret_field_focused"
    if reason:
        image = image_size = None
        title = "" if reason in {"blocked_title", "blocked_process"} else title
    return Observation(
        seq=seq,
        taken_at=now,
        window_title=title,
        process=process,
        window_rect=_rect(raw.get("rect")),
        screen=screen,
        fingerprint=str(raw.get("fingerprint", ""))[:64],
        image_png_b64=image,
        image_size=image_size,
        image_rect=image_rect if image is not None else None,
        focus_is_secret=secret_focus,
        blocked_reason=reason,
        window_id=window_id,
        pid=pid,
    )


def image_to_screen(observation: Observation, x: int, y: int) -> tuple[int, int]:
    """Map a point in the screenshot's pixels to physical screen pixels."""
    size = observation.image_size
    if size is None:
        return x, y
    left, top, width, height = observation.image_rect or (0, 0, *observation.screen)
    return left + round(x * width / size[0]), top + round(y * height / size[1])


def rect_in_image(observation: Observation) -> tuple[int, int, int, int] | None:
    """The focused window rect expressed in screenshot pixels (what the model sees)."""
    rect, size = observation.window_rect, observation.image_size
    if rect is None or size is None:
        return rect
    left, top, width, height = observation.image_rect or (0, 0, *observation.screen)
    if width <= 0 or height <= 0:
        return rect
    fx, fy = size[0] / width, size[1] / height
    x0 = max(0, round((rect[0] - left) * fx))
    y0 = max(0, round((rect[1] - top) * fy))
    x1 = min(size[0], round((rect[0] + rect[2] - left) * fx))
    y1 = min(size[1], round((rect[1] + rect[3] - top) * fy))
    return (x0, y0, max(0, x1 - x0), max(0, y1 - y0))
