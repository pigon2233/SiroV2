"""Owner reminders: "30分鐘後提醒我…", "明天八點提醒我…" (Asia/Taipei), kept across restarts.

Parsing is local and rule-based; nothing here needs a model. Pending reminders live in one
small JSON file in the data directory and a loop fires each one when it is due.
"""
# ruff: noqa: RUF001

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

LOGGER = logging.getLogger(__name__)
TAIPEI = ZoneInfo("Asia/Taipei")
MAX_KEPT = 100
MAX_TEXT = 200
LATE_AFTER = timedelta(minutes=2)
DROP_AFTER = timedelta(days=1)
MAX_PENDING = 50

_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5}
_DIGITS |= {"六": 6, "七": 7, "八": 8, "九": 9}
_NUM = r"(?:\d+|[零〇一二兩三四五六七八九十]+)"
_RELATIVE = re.compile(
    rf"(?:(?P<half>半)個?(?P<hu>小時|鐘頭)|(?P<n>{_NUM})(?:個半|個)?(?P<unit>秒鐘|秒|分鐘|分|小時|鐘頭|天)(?P<ban>半)?)"
    r"(?:之)?後"
)
_DAYS = {"今天": 0, "今日": 0, "今晚": 0, "今早": 0, "明天": 1, "明日": 1, "明早": 1, "明晚": 1}
_DAYS |= {"後天": 2, "大後天": 3}
_ABSOLUTE = re.compile(
    r"(?P<day>大後天|後天|明天|明日|明早|明晚|今天|今日|今晚|今早)?"
    r"(?P<period>凌晨|早上|早晨|上午|中午|下午|晚上|半夜)?"
    rf"(?P<h>{_NUM})(?:點|時|:|：)(?:(?P<half>半)|(?P<m>{_NUM})分?)?"
)
_FILLER = re.compile(r"提醒我|提醒|叫我|通知我|幫我|請|麻煩|記得|要記得|SIRO|希洛|，|,|。|！|!|\s")


def _to_int(raw: str) -> int | None:
    if raw.isdigit():
        return int(raw)
    if "十" in raw:
        head, _, tail = raw.partition("十")
        tens = _DIGITS.get(head, 1) if head else 1
        if (head and head not in _DIGITS) or (tail and tail not in _DIGITS):
            return None
        return tens * 10 + (_DIGITS[tail] if tail else 0)
    if len(raw) == 1 and raw in _DIGITS:
        return _DIGITS[raw]
    return None


@dataclass(frozen=True, slots=True)
class Reminder:
    reminder_id: str
    text: str
    due: datetime  # UTC
    created: datetime
    status: str = "pending"  # pending | fired | cancelled | missed

    def to_json(self) -> dict[str, str]:
        return {
            "id": self.reminder_id,
            "text": self.text,
            "due": self.due.isoformat(),
            "created": self.created.isoformat(),
            "status": self.status,
        }

    @staticmethod
    def from_json(raw: object) -> Reminder | None:
        if not isinstance(raw, dict):
            return None
        try:
            return Reminder(
                str(raw["id"]),
                str(raw["text"])[:MAX_TEXT],
                datetime.fromisoformat(str(raw["due"])),
                datetime.fromisoformat(str(raw["created"])),
                str(raw.get("status", "pending")),
            )
        except (KeyError, ValueError):
            return None


def parse_reminder(text: str, now: datetime) -> tuple[datetime, str] | None:
    """The due time (UTC) and what to be reminded of, or None when no time is given."""
    local = now.astimezone(TAIPEI)
    due: datetime | None = None
    match = _RELATIVE.search(text)
    if match is not None:
        if match["half"]:
            delta = timedelta(hours=0.5)
        else:
            n = _to_int(match["n"])
            if n is None:
                return None
            unit = match["unit"]
            if unit in {"秒鐘", "秒"}:
                delta = timedelta(seconds=n)
            elif unit in {"分鐘", "分"}:
                delta = timedelta(minutes=n)
            elif unit == "天":
                delta = timedelta(days=n) + (timedelta(hours=12) if match["ban"] else timedelta())
            else:
                delta = timedelta(hours=n) + (
                    timedelta(minutes=30) if match["ban"] or "個半" in match[0] else timedelta()
                )
        due = local + delta
    else:
        match = _ABSOLUTE.search(text)
        if match is None:
            return None
        hour = _to_int(match["h"])
        minute = 30 if match["half"] else (_to_int(match["m"]) if match["m"] else 0)
        if hour is None or minute is None or hour > 24 or minute > 59:
            return None
        due = _absolute(local, match, hour, minute)
        if due is None:
            return None
    start, end = match.span()
    rest = _FILLER.sub("", text[:start] + text[end:]).strip("：:、")
    return due.astimezone(UTC), (rest or "該做你交代的事了")[:MAX_TEXT]


def _absolute(local: datetime, match: re.Match[str], hour: int, minute: int) -> datetime | None:
    day_word, period = match["day"], match["period"]
    if day_word is None and period is None:
        # "八點" alone: the next time the clock shows it, morning or evening.
        candidates = [hour] if hour >= 13 else [hour, (hour + 12) % 24]
    else:
        if period is None and day_word in {"今晚", "明晚"}:
            period = "晚上"
        elif period is None and day_word in {"今早", "明早"}:
            period = "早上"
        if (period in {"下午", "晚上"} and hour < 12) or (period == "中午" and hour < 11):
            hour += 12
        elif period in {"凌晨", "半夜"} and hour == 12:
            hour = 0
        candidates = [hour]
    offset = _DAYS.get(day_word or "", 0)
    base = local.replace(second=0, microsecond=0) + timedelta(days=offset)
    best: datetime | None = None
    for candidate in candidates:
        day = base + timedelta(days=1 if candidate == 24 else 0)
        moment = day.replace(hour=candidate % 24, minute=minute)
        if moment <= local and day_word is None:
            moment += timedelta(days=1)
        # An explicit day that is already past is returned as is so the caller can say so.
        if best is None or (moment > local and (best <= local or moment < best)):
            best = moment
    return best


def _when(due: datetime, now: datetime) -> str:
    local, today = due.astimezone(TAIPEI), now.astimezone(TAIPEI)
    days = (local.date() - today.date()).days
    label = {0: "今天", 1: "明天", 2: "後天"}.get(days, f"{local.month}月{local.day}日")
    return f"{label} {local:%H:%M}"


_TIME_HINT = re.compile(
    r"明天|明早|明晚|後天|大後天|下週|下周|下禮拜|週[一二三四五六日末]|星期|禮拜|[0-9一二三四五六七八九十]+(?:點|號|日)|"
    r"早上|上午|中午|下午|晚上|今晚|等一下|待會|稍後|[0-9一二兩三四五六七八九十]+(?:分鐘|小時|天)後"
)
_INTENT_RULES = (
    "你是 SIRO 的行程助理。判斷使用者這句話是否提到一件『未來、有明確時間』且值得事先"
    "提醒他的事（面試、會議、考試、吃藥、出門、截止日等）。只是閒聊、過去的事、"
    "沒有時間的事都不要提醒。只輸出一行 JSON，不要其他文字："
    '{"remind":true或false,"when":"YYYY-MM-DD HH:MM","text":"提醒內容(15字內)"}。'
    "when 是台北時間；只講『早上』沒有幾點就用 08:00，『下午』用 14:00，『晚上』用 19:00；"
    "事件本身的前 30 分鐘到 1 小時才是提醒時間較合適時，請直接給提醒時間。"
)


def may_hold_event(text: str) -> bool:
    """Cheap filter so the model is only asked when a message mentions some time."""
    return len(text) <= 300 and _TIME_HINT.search(text) is not None


def intent_prompt(text: str, now: datetime) -> str:
    local = now.astimezone(TAIPEI)
    weekday = "一二三四五六日"[local.weekday()]
    return (
        f"{_INTENT_RULES}\n現在是台北時間 {local:%Y-%m-%d %H:%M}（週{weekday}）。\n使用者說：{text}"
    )


def parse_intent(raw: str, now: datetime) -> tuple[datetime, str] | None:
    """The due time (UTC) and text from the model's JSON line, or None for no reminder."""
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
        if data.get("remind") is not True:
            return None
        due = datetime.strptime(str(data["when"]).strip(), "%Y-%m-%d %H:%M").replace(tzinfo=TAIPEI)
    except (ValueError, KeyError, AttributeError):
        return None
    text = " ".join(str(data.get("text", "")).split())[:MAX_TEXT]
    due = due.astimezone(UTC)
    if not text or due <= now or due - now > timedelta(days=366):
        return None
    return due, text


def reminders_enabled() -> bool:
    setting = os.environ.get("SIRO_REMINDER_ENABLED", "1")
    if setting not in {"0", "1"}:
        raise ValueError("SIRO_REMINDER_ENABLED must be 0 or 1")
    return setting == "1"


class ReminderService:
    def __init__(
        self,
        path: Path,
        fire: Callable[[Reminder, bool], Awaitable[None]],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        interval: float = 5.0,
    ) -> None:
        self._path = path
        self._fire = fire
        self._clock = clock
        self._interval = interval
        self._items: list[Reminder] = self._load()
        self._task: asyncio.Task[None] | None = None
        self._wake = asyncio.Event()

    def _load(self) -> list[Reminder]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        items = (Reminder.from_json(item) for item in raw) if isinstance(raw, list) else ()
        return [item for item in items if item is not None]

    def _save(self) -> None:
        pending = [i for i in self._items if i.status == "pending"]
        done = [i for i in self._items if i.status != "pending"][-MAX_KEPT:]
        self._items = [*done, *pending]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps([i.to_json() for i in self._items], ensure_ascii=False), encoding="utf-8"
        )
        tmp.replace(self._path)

    def pending(self) -> list[Reminder]:
        return sorted((i for i in self._items if i.status == "pending"), key=lambda i: i.due)

    def add(self, text: str, due: datetime) -> Reminder:
        item = Reminder(str(uuid4()), text, due, self._clock())
        self._items.append(item)
        self._save()
        self._wake.set()
        return item

    def cancel(self, reminder_id: str) -> bool:
        for index, item in enumerate(self._items):
            if item.reminder_id == reminder_id and item.status == "pending":
                self._items[index] = Reminder(*(*_fields(item)[:4], "cancelled"))
                self._save()
                return True
        return False

    def handle(self, text: str) -> str | None:
        """A spoken reply when the message is a reminder command, else None (normal chat)."""
        if "提醒" not in text and not ("取消" in text and "鬧鐘" in text):
            return None
        now = self._clock()
        if "取消" in text or "刪除" in text or "不用提醒" in text:
            return self._cancel_by_text(text)
        parsed = parse_reminder(text, now)
        if parsed is None:
            if any(w in text for w in ("哪些", "列出", "清單", "查看", "還有什麼", "有什麼")):
                return self._list_reply(now)
            return None
        due, what = parsed
        if due <= now:
            return "這個時間已經過了，要提醒我的時間再說一次好嗎？"
        if len(self.pending()) >= MAX_PENDING:
            return "待辦的提醒太多了，先取消幾個再說吧。"
        self.add(what, due)
        return f"好，{_when(due, now)}我會提醒你：{what}"

    def add_from_intent(self, due: datetime, text: str) -> str | None:
        """Store a model-inferred reminder; None when it duplicates a pending one."""
        if len(self.pending()) >= MAX_PENDING:
            return None
        if any(abs(i.due - due) < timedelta(minutes=5) and i.text == text for i in self.pending()):
            return None
        self.add(text, due)
        return f"我幫你記下了，{_when(due, self._clock())}會提醒你：{text}"

    def _list_reply(self, now: datetime) -> str:
        items = self.pending()
        if not items:
            return "目前沒有待辦的提醒。"
        lines = [f"{n}. {_when(i.due, now)} {i.text}" for n, i in enumerate(items, 1)]
        return "待辦的提醒：" + "；".join(lines)

    def _cancel_by_text(self, text: str) -> str:
        items = self.pending()
        if not items:
            return "目前沒有待辦的提醒可以取消。"
        if any(w in text for w in ("全部", "所有")):
            for item in items:
                self.cancel(item.reminder_id)
            return f"已取消全部 {len(items)} 個提醒。"
        number = re.search(rf"第\s*({_NUM})\s*(?:個|筆|項)?", text)
        if number is not None:
            index = _to_int(number[1])
            if index is not None and 1 <= index <= len(items):
                self.cancel(items[index - 1].reminder_id)
                return f"已取消提醒：{items[index - 1].text}"
        stripped = _FILLER.sub("", re.sub(r"取消|刪除|不用|的|那個|這個|吧", "", text))
        hits = [i for i in items if stripped and (stripped in i.text or i.text in stripped)]
        target = hits if hits else (items if len(items) == 1 else [])
        if len(target) != 1:
            return "有好幾個提醒，說「取消第幾個提醒」或「取消全部提醒」。" + self._list_reply(
                self._clock()
            )
        self.cancel(target[0].reminder_id)
        return f"已取消提醒：{target[0].text}"

    async def fire_due(self) -> int:
        now = self._clock()
        fired = 0
        for item in [i for i in self.pending() if i.due <= now]:
            late = now - item.due
            status = "missed" if late > DROP_AFTER else "fired"
            self._replace(item, status)
            if status == "missed":
                continue
            try:
                await self._fire(item, late > LATE_AFTER)
            except Exception:
                LOGGER.exception("reminder delivery failed")
            fired += 1
        return fired

    def _replace(self, item: Reminder, status: str) -> None:
        index = self._items.index(item)
        self._items[index] = Reminder(*(*_fields(item)[:4], status))
        self._save()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="siro-reminders")

    async def close(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _loop(self) -> None:
        while True:
            try:
                await self.fire_due()
            except Exception:  # one bad pass must not end reminders for good
                LOGGER.exception("reminder pass failed")
            self._wake.clear()
            with suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), self._interval)


def _fields(item: Reminder) -> tuple[str, str, datetime, datetime, str]:
    return item.reminder_id, item.text, item.due, item.created, item.status


def spoken_text(item: Reminder, late: bool) -> tuple[str, str]:
    """(chat/bubble text, spoken text) for a due reminder."""
    prefix = "（晚了一點）" if late else ""
    return f"⏰ 提醒：{item.text}", f"{prefix}爸爸，提醒你，{item.text}。"
