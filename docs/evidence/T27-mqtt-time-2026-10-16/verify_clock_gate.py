"""Compile actual firmware clock/setup/loop functions with host-only Arduino stubs.

This is control-flow verification, not a PlatformIO build or hardware evidence.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "firmware/esp32/src/main.cpp"


def function(source: str, signature: str) -> str:
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def main() -> None:
    source = SOURCE.read_text()
    threshold = re.search(r"constexpr time_t minimumSyncedTime = \d+;", source)
    assert threshold is not None
    functions = "\n".join(
        function(source, name) for name in ["bool waitForTimeSync()", "void setup()", "void loop()"]
    )
    harness = r"""
#include <cassert>
#include <cstdint>
#include <ctime>
#include <limits>
uint32_t ticks;
uint64_t elapsed, syncAfter;
time_t clockValue;
bool configured, connected;
int connects, restarts, polls, logs;
constexpr int SIRO_LED_PIN = 2, OUTPUT = 1, WL_CONNECTED = 3;
constexpr const char *SIRO_WIFI_SSID = "synthetic", *SIRO_WIFI_PASSWORD = "fixture";
uint32_t millis() { return ticks; }
void delay(uint32_t ms) { ticks += ms; elapsed += ms; }
time_t fakeTime(time_t *) { return elapsed >= syncAfter ? 1800000000 : clockValue; }
#define time fakeTime
void pinMode(int, int) {}
void configTime(int, int, const char *) { configured = true; }
struct SerialStub { void begin(int) {} void println(const char *) { ++logs; } } Serial;
struct WiFiStub {
  void begin(const char *, const char *) {}
  int status() { return WL_CONNECTED; }
} WiFi;
struct EspStub { void restart() { ++restarts; } } ESP;
struct MqttStub { bool connected() { return ::connected; } void poll() { ++polls; } } mqtt;
void connectMqtt() {
  assert(configured);
  assert(fakeTime(nullptr) > 1700000000);
  ++connects;
  connected = true;
}
"""
    cases = r"""
void reset() {
  ticks = 0; elapsed = 0; syncAfter = std::numeric_limits<uint64_t>::max();
  clockValue = 0; configured = connected = false;
  connects = restarts = polls = logs = 0;
}
int main() {
  reset(); clockValue = minimumSyncedTime + 1;
  assert(waitForTimeSync()); assert(elapsed == 0);
  reset(); syncAfter = 1000;
  assert(waitForTimeSync()); assert(elapsed == 1000);
  reset(); clockValue = minimumSyncedTime;
  assert(!waitForTimeSync()); assert(elapsed == 30000);
  reset(); ticks = UINT32_MAX - 100;
  assert(!waitForTimeSync()); assert(elapsed == 30000);
  reset(); syncAfter = 1000;
  setup(); assert(configured && connects == 1 && restarts == 0 && elapsed == 1000);
  reset(); setup();
  assert(configured && connects == 0 && restarts == 1 && logs == 1 && elapsed == 30000);
  loop(); assert(connects == 0 && polls == 0);
  clockValue = minimumSyncedTime + 1;
  loop(); assert(connects == 1 && polls == 1);
  clockValue = 0;
  loop(); assert(connects == 1 && polls == 1);
}
"""
    with tempfile.TemporaryDirectory(prefix="siro-clock-gate-") as temporary:
        cpp = Path(temporary) / "clock_gate.cpp"
        executable = Path(temporary) / "clock_gate"
        cpp.write_text(harness + threshold.group() + "\n" + functions + "\n" + cases)
        subprocess.run(
            ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(executable)],
            check=True,
        )
        subprocess.run([str(executable)], check=True)
    print(
        json.dumps(
            {"result": "pass", "scenarios": 9, "firmware_build": False, "hardware_verified": False}
        )
    )


if __name__ == "__main__":
    main()
