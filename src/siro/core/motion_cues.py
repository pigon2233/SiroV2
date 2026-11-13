"""Reply motion cues: inline tags stripped before chat and speech, plus a rule fallback.

The model may write short tags the persona prompt asks for. They are presentation only.
``SIRO_MOTION_CUES=0`` turns the channel off: no prompt clause, no stripping, no cues.
Anything other than ``0`` leaves it on. No classifier is called; rules cover replies
that omit tags. Cue names are an allow-list, so a tag cannot invent a body command.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

CueKind = Literal["gesture", "emotion", "look", "posture"]

GESTURES = frozenset(
    {
        "wave",
        "bow",
        "bye",
        "nod",
        "shake",
        "think",
        "attention",
        "clap",
        "stretch",
        "notebook",
        "point",
        "reach",
        "sigh",
        "hum",
    }
)
EMOTIONS = frozenset({"happy", "sad", "angry", "surprised", "relaxed", "neutral"})
LOOKS = frozenset({"user", "chat", "left", "right", "up", "down", "away", "pointer"})
POSTURES = frozenset(
    {"lean", "shrug", "tilt", "nod", "shake", "attentive", "point", "reach", "think"}
)
LOOK_XY: dict[str, tuple[float, float]] = {
    "user": (0.0, 0.05),
    "chat": (-0.45, 0.55),
    "left": (-0.8, 0.1),
    "right": (0.8, 0.1),
    "up": (0.0, 0.65),
    "down": (0.0, -0.45),
    "away": (0.55, 0.3),
    "pointer": (0.15, 0.1),
}
_MAX_CUES = 8
_TAG = re.compile(
    r"\[\[\s*([gelp])\s*:\s*([^\s:\]]+?)\s*(?::\s*([^\s:\]]+)\s*)?(?::\s*([^\s:\]]+)\s*)?\]\]",
    re.IGNORECASE,
)
# A tail that could still grow into a cue: "[", "[[", "[[g:wa", "[[e:happy:0.6]".
_PARTIAL = re.compile(
    r"\[(?:\[\s*(?:[gelp](?:\s*:\s*[^\s:\]]{0,32}(?:\s*:\s*[^\s:\]]{0,16}){0,2}\s*)?)?)?\]?$",
    re.IGNORECASE,
)
_CLAUSE = re.compile(r"[，。！？、,.!?~～…\n]+")  # noqa: RUF001
_SPEECH: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "bye",
        re.compile(
            r"(再見|掰掰|拜拜|晚安|下次見|明天見|\bbye\b|see you|good ?night)",
            re.I,
        ),
        "both",
    ),
    (
        "wave",
        re.compile(
            r"^(你好|您好|嗨|哈囉|早安|午安|早啊|hello|hi\b|hey\b|good morning)",
            re.I,
        ),
        "head",
    ),
    (
        "bow",
        re.compile(
            r"(謝謝|感謝|多謝|抱歉|對不起|不好意思|請多指教|thank|sorry)",
            re.I,
        ),
        "both",
    ),
    (
        "shake",
        re.compile(r"^(不是|不對|不行|不可以|不會吧|才不|no\b|nope)", re.I),
        "head",
    ),
    (
        "think",
        re.compile(r"^(嗯+|讓我想想|我想想|想一下|這個嘛|hmm+|let me think)", re.I),
        "head",
    ),
    (
        "nod",
        re.compile(r"^(對|是的|沒錯|好啊|好的|當然|可以|yes\b|sure\b|ok\b|okay\b)", re.I),
        "head",
    ),
)
_POINT = re.compile(r"(你看|看這裡|看這裡|左邊|左边|右側|右邊|右边|那邊|那边)")
_LEFT = re.compile(r"(左邊|左边)")
_RIGHT = re.compile(r"(右邊|右边|右側)")
_SHRUG = re.compile(r"^(不知道|不確定|不确定|也許|也许|可能吧|我不清楚|not sure|maybe\b)", re.I)
_FEELING: tuple[tuple[str, re.Pattern[str], float], ...] = (
    ("happy", re.compile(r"^(太好了|好開心|好开心|哈哈|耶)"), 0.55),
    ("sad", re.compile(r"^(好難過|好难过|唉)"), 0.45),
    ("angry", re.compile(r"^(氣死|气死|太過分|太过分)"), 0.5),
    ("surprised", re.compile(r"^(哇|天啊|咦)"), 0.5),
)

MOTION_PROMPT = (
    "- Motion cues, never spoken: when a reply needs a gesture, emotion, look or posture, "
    "place one tag immediately after the sentence it belongs to. Tags are removed before "
    "the owner reads or hears the reply; never pronounce, quote, or explain them. "
    "Forms: [[g:wave]] [[e:happy:0.6]] [[l:chat]] [[p:lean]]. "
    "Gestures: wave, bow, bye, nod, shake, think, attention, clap, stretch, notebook, "
    "point, reach. Emotions: happy, sad, angry, surprised, relaxed, neutral, intensity 0 to 1. "
    "Look: user, chat, left, right, up, down, away. "
    "Postures: lean, shrug, tilt, nod, shake, attentive, point, reach, think. "
    "Omit tags when the words are enough.\n"
)


def motion_cues_enabled(env: Mapping[str, str] | None = None) -> bool:
    """``0`` disables the channel. Unset and every other value leave it on."""

    source = os.environ if env is None else env
    return source.get("SIRO_MOTION_CUES", "1") != "0"


def motion_prompt(enabled: bool) -> str:
    return MOTION_PROMPT if enabled else ""


def research_capability(name: str) -> bool:
    """Tools that mean she is looking something up, not operating the computer."""

    return name.startswith("browser.") or name == "claude.ask"


@dataclass(frozen=True, slots=True)
class MotionCue:
    kind: CueKind
    name: str
    intensity: float = 1.0
    x: float = 0.0
    y: float = 0.0


def body_message(cue: MotionCue) -> dict[str, object]:
    """One cue as an existing body.v1 message. Posture uses body.gesture."""

    if cue.kind == "emotion":
        return {"v": 1, "type": "body.emotion", "name": cue.name, "intensity": cue.intensity}
    if cue.kind == "look":
        return {"v": 1, "type": "body.look", "x": cue.x, "y": cue.y}
    return {"v": 1, "type": "body.gesture", "name": cue.name, "intensity": cue.intensity}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _number(token: str | None) -> float | None:
    if token is None:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def _intensity(token: str | None, default: float) -> float:
    value = _number(token)
    if token is None or value is None:
        return default
    return _clamp(value, 0.0, 1.0)


def _hold_len(text: str) -> int:
    """How many trailing characters might still be the start of a cue tag."""

    best = 0
    start = max(0, len(text) - 64)
    for index in range(start, len(text)):
        if text[index] != "[":
            continue
        tail = text[index:]
        if _PARTIAL.fullmatch(tail) and len(tail) > best:
            best = len(tail)
    return best


def _cue_from(kind: str, name: str, extra: str | None, _extra2: str | None) -> MotionCue | None:
    key = kind.lower()
    label = name.lower()
    if key == "g" and label in GESTURES:
        return MotionCue("gesture", label, _intensity(extra, 0.8))
    if key == "e" and label in EMOTIONS:
        return MotionCue("emotion", label, _intensity(extra, 0.6))
    if key == "p" and label in POSTURES:
        return MotionCue("posture", label, _intensity(extra, 0.7))
    if key == "l":
        if label in LOOKS:
            named_x, named_y = LOOK_XY[label]
            return MotionCue("look", label, 1.0, named_x, named_y)
        parsed_x = _number(name)
        parsed_y = _number(extra)
        if parsed_x is None or parsed_y is None:
            return None
        return MotionCue(
            "look", "point", 1.0, _clamp(parsed_x, -1.0, 1.0), _clamp(parsed_y, -1.0, 1.0)
        )
    return None


def _tidy(text: str, *, ended_space: bool) -> tuple[str, bool]:
    if ended_space:
        text = text.lstrip(" \t")
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+([，。！？、,.!?])", r"\1", text)  # noqa: RUF001
    return text, text.endswith(" ")


def fallback_cues(text: str) -> tuple[MotionCue, ...]:
    """One gesture from the same patterns the renderer used to apply, else a small pose."""

    clauses = [part.strip() for part in _CLAUSE.split(text) if part.strip()]
    if clauses:
        head, tail = clauses[0], clauses[-1]
        for name, pattern, where in _SPEECH:
            if pattern.search(head) or (where == "both" and pattern.search(tail)):
                return (MotionCue("gesture", name, 0.8),)
    if _POINT.search(text):
        look = "left" if _LEFT.search(text) else "right" if _RIGHT.search(text) else "user"
        x, y = LOOK_XY[look]
        return (MotionCue("gesture", "point", 0.75), MotionCue("look", look, 1.0, x, y))
    if clauses and _SHRUG.search(clauses[0]):
        return (MotionCue("posture", "shrug", 0.65),)
    if clauses:
        for emotion, pattern, intensity in _FEELING:
            if pattern.search(clauses[0]):
                return (MotionCue("emotion", emotion, intensity),)
    return ()


class MotionStream:
    """Streaming tag stripper. ``push`` returns only text that is safe to show and speak."""

    def __init__(self) -> None:
        self._buf = ""
        self._pending: list[MotionCue] = []
        self._cues: list[MotionCue] = []
        self._inline = False
        self._closed = False
        self._ended_space = False
        self.spoken = ""

    def push(self, chunk: str) -> str:
        if self._closed or not chunk:
            return ""
        self._buf += chunk
        parts: list[str] = []
        while True:
            match = _TAG.search(self._buf)
            if match is not None:
                parts.append(self._buf[: match.start()])
                cue = _cue_from(match.group(1), match.group(2), match.group(3), match.group(4))
                self._buf = self._buf[match.end() :]
                if cue is not None and len(self._cues) < _MAX_CUES:
                    self._inline = True
                    self._cues.append(cue)
                    self._pending.append(cue)
                continue
            hold = _hold_len(self._buf)
            if hold == len(self._buf) and hold:
                break
            parts.append(self._buf[:-hold] if hold else self._buf)
            self._buf = self._buf[-hold:] if hold else ""
            break
        return self._emit("".join(parts))

    def finish(self) -> str:
        if self._closed:
            return ""
        self._closed = True
        if "[[" in self._buf and _PARTIAL.fullmatch(self._buf):
            self._buf = ""
        tail = self._emit(self._buf)
        self._buf = ""
        if not self._inline:
            for cue in fallback_cues(self.spoken):
                if len(self._cues) >= _MAX_CUES:
                    break
                self._cues.append(cue)
                self._pending.append(cue)
        return tail

    def drain(self) -> tuple[MotionCue, ...]:
        found = tuple(self._pending)
        self._pending.clear()
        return found

    @property
    def cues(self) -> tuple[MotionCue, ...]:
        return tuple(self._cues)

    def _emit(self, text: str) -> str:
        if not text:
            return ""
        cleaned, self._ended_space = _tidy(text, ended_space=self._ended_space)
        self.spoken += cleaned
        return cleaned
