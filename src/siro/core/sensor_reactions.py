"""How SIRO reacts to the ESP32 node: greet on arrival, go quiet in the dark, listen on a press.

Pure rules over already-validated sensor events; the gateway performs the effects.
"""

from __future__ import annotations

from datetime import datetime, timedelta

GREETING_GAP = timedelta(minutes=30)
DARK_LUX = 5.0
# Hysteresis: a dim room that flickers around the threshold must not toggle quiet mode.
BRIGHT_LUX = 15.0


class SensorReactions:
    """`handle` returns the effects for one event: `greet`, `quiet_on`, `quiet_off` or `listen`."""

    def __init__(
        self,
        *,
        greeting_gap: timedelta = GREETING_GAP,
        dark_lux: float = DARK_LUX,
        bright_lux: float = BRIGHT_LUX,
    ) -> None:
        self._gap = greeting_gap
        self._dark = dark_lux
        self._bright = max(bright_lux, dark_lux)
        self._quiet = False
        self._last_greeting: datetime | None = None

    @property
    def quiet(self) -> bool:
        return self._quiet

    def handle(self, event: str, lux: float | None, now: datetime) -> list[str]:
        if event == "light_update" and lux is not None:
            if not self._quiet and lux <= self._dark:
                self._quiet = True
                return ["quiet_on"]
            if self._quiet and lux >= self._bright:
                self._quiet = False
                return ["quiet_off"]
            return []
        if self._quiet:
            return []
        if event == "motion_detected":
            if self._last_greeting is not None and now - self._last_greeting < self._gap:
                return []
            self._last_greeting = now
            return ["greet"]
        if event == "button_pressed":
            return ["listen"]
        return []
