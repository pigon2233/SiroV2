#include <Arduino.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <ArduinoMqttClient.h>
#include <WiFi.h>
#include <Wire.h>
#include <time.h>

#include "face.h"
#include "secrets.h"
#include "ota.h"  // After secrets.h: it reads SIRO_OTA_BASE_URL.
#include "sensor_telemetry.h"

#ifndef SIRO_HAS_OLED
#define SIRO_HAS_OLED 1  // Set to 0 in secrets.h to rule the display out as PIR noise.
#endif
#ifndef SIRO_OLED_ADDRESS
#define SIRO_OLED_ADDRESS 0x3C
#endif

// Sensors, display and local state run in loop() and never wait for the network. Wi-Fi, NTP,
// MQTT, the HTTP fallback and OTA live in netTask() on the other core and only exchange the
// snapshot below, so a dead router or broker cannot make the PIR miss a pulse.
struct Snapshot {
  bool pirReady = false;
  bool motion = false;
  bool buttonDown = false;
  bool lightValid = false;
  uint32_t pressCount = 0;
  float lux = 0.0f;
  uint32_t seq = 0;  // Bumped whenever motion/button changes (publish immediately).
  // Diagnostics for the last 10 s window.
  uint32_t diagSeq = 0;
  uint32_t pirRawEdges = 0;
  uint32_t pirHighPct = 0;
  bool pirRaw = false;
  uint32_t pirPulses = 0;
  uint32_t maxSampleGapMs = 0;
};

enum LinkState : uint8_t { LinkDown = 0, LinkMqtt = 1, LinkHttp = 2 };

WiFiClient network;
MqttClient mqtt(network);
String prefix = String("siro/devices/") + SIRO_DEVICE_ID + "/";
#if SIRO_HAS_LED
String lastCommandId;
#endif
constexpr time_t minimumSyncedTime = 1700000000;
constexpr uint32_t sensorIntervalMs = 10000UL;
constexpr uint32_t wifiRetryBaseMs = 5000UL;
constexpr uint32_t wifiRetryMaxMs = 60000UL;
constexpr uint32_t mqttRetryBaseMs = 5000UL;
constexpr uint32_t mqttRetryMaxMs = 30000UL;

PirMotionSampler pir(0);
ButtonSampler button;
SiroFace face;
portMUX_TYPE snapshotLock = portMUX_INITIALIZER_UNLOCKED;
Snapshot shared;
volatile uint8_t linkState = LinkDown;
volatile bool wifiUp = false;

// loop()-only state.
uint32_t lastLightRead = 0;
bool lightSensorReady = false;
bool lastPirRaw = false;
uint32_t pirRawEdges = 0;
uint32_t pirHighSamples = 0;
uint32_t pirSamples = 0;
uint32_t lastDiag = 0;
uint32_t lastLoopMs = 0;
uint32_t maxLoopGapMs = 0;
float lastLux = 0.0f;
bool lightValid = false;

Snapshot readShared() {
  portENTER_CRITICAL(&snapshotLock);
  const Snapshot copy = shared;
  portEXIT_CRITICAL(&snapshotLock);
  return copy;
}

bool startLightSensor() {
  Wire.beginTransmission(SIRO_BH1750_ADDRESS);
  Wire.write(0x10);  // BH1750 continuous high-resolution measurement.
  return Wire.endTransmission() == 0;
}

bool readLightSensor(float &lux) {
  const uint8_t received = Wire.requestFrom(static_cast<uint8_t>(SIRO_BH1750_ADDRESS),
                                            static_cast<uint8_t>(2));
  if (received != 2) return false;
  const uint16_t raw = (static_cast<uint16_t>(Wire.read()) << 8) |
                       static_cast<uint16_t>(Wire.read());
  lux = luxFromBh1750Raw(raw);
  return true;
}

// ---------------------------------------------------------------- network task ----

void publishJson(const String &topic, JsonDocument &document, bool retain, uint8_t qos) {
  String payload;
  serializeJson(document, payload);
  mqtt.beginMessage(topic, payload.length(), retain, qos, false);
  mqtt.print(payload);
  mqtt.endMessage();
}

void publishState(const Snapshot &snap) {
  JsonDocument state;
  state["observed_at_epoch"] = time(nullptr);
#if SIRO_HAS_LED
  state["properties"]["power"] = digitalRead(SIRO_LED_PIN) == HIGH;
#endif
  state["properties"]["button_down"] = snap.buttonDown;
  state["properties"]["button_press_count"] = snap.pressCount;
  if (snap.pirReady) state["properties"]["motion"] = snap.motion;
  if (snap.lightValid) state["properties"]["illuminance"] = snap.lux;
  publishJson(prefix + "state", state, true, 1);
}

void publishDiag(const Snapshot &snap) {
  JsonDocument diag;
  diag["pir_raw_edges"] = snap.pirRawEdges;
  diag["pir_high_pct"] = snap.pirHighPct;
  diag["oled"] = SIRO_HAS_OLED;
  diag["fw"] = SIRO_FW_VERSION;
  diag["pir_raw"] = snap.pirRaw ? 1 : 0;
  diag["pir_filtered"] = snap.motion ? 1 : 0;
  diag["pir_ready"] = snap.pirReady ? 1 : 0;
  diag["pir_pulses_10s"] = snap.pirPulses;
  diag["pir_max_sample_gap_ms"] = snap.maxSampleGapMs;
  diag["wifi"] = wifiUp ? 1 : 0;
  diag["mqtt"] = linkState == LinkMqtt ? 1 : 0;
  diag["uptime_s"] = millis() / 1000UL;
  diag["free_heap"] = ESP.getFreeHeap();
  publishJson(prefix + "diag", diag, false, 0);  // Diagnostics are best-effort.
}

#if SIRO_HAS_LED
void publishAck(const String &commandId, const char *status) {
  JsonDocument ack;
  ack["command_id"] = commandId;
  ack["status"] = status;
  publishJson(prefix + "ack", ack, false, 1);
}

void onMessage(int size) {
  String payload;
  while (mqtt.available() && size-- > 0) payload += static_cast<char>(mqtt.read());
  if (mqtt.messageRetain()) return;  // Never execute a replayed retained command.
  JsonDocument command;
  if (deserializeJson(command, payload)) return;
  String commandId = command["command_id"] | "";
  long expiresAt = command["expires_at_epoch"] | 0;
  if (commandId.length() == 0 || expiresAt <= time(nullptr)) {
    publishAck(commandId, "expired_or_invalid");
    return;
  }
  if (commandId == lastCommandId) {
    publishAck(commandId, "duplicate");
    return;
  }
  if (String(command["action"] | "") != "light.set" ||
      !command["desired_state"]["power"].is<bool>()) {
    publishAck(commandId, "unsupported");
    return;
  }
  digitalWrite(SIRO_LED_PIN, command["desired_state"]["power"].as<bool>() ? HIGH : LOW);
  lastCommandId = commandId;
  publishAck(commandId, "applied");
  publishState(readShared());  // Ack alone is not success; gateway confirms this state readback.
}
#endif

// One bounded connect attempt (short TCP/MQTT timeouts); the caller backs off on failure.
bool tryConnectMqtt() {
  mqtt.setId(SIRO_DEVICE_ID);
  mqtt.setUsernamePassword(SIRO_MQTT_USERNAME, SIRO_MQTT_PASSWORD);
  mqtt.setConnectionTimeout(2000);
  mqtt.setKeepAliveInterval(15000);
  mqtt.beginWill(prefix + "availability", 7, true, 1);
  mqtt.print("offline");
  mqtt.endWill();
#if SIRO_HAS_LED
  mqtt.onMessage(onMessage);
#endif
  if (!mqtt.connect(SIRO_MQTT_HOST, SIRO_MQTT_PORT)) return false;
  mqtt.beginMessage(prefix + "availability", 6, true, 1, false);
  mqtt.print("online");
  mqtt.endMessage();
#if SIRO_HAS_LED
  mqtt.subscribe(prefix + "command", 1);
#endif
  publishState(readShared());  // Current snapshot, not just the next change.
  return true;
}

// HTTP fallback uses the legacy receiver contract: POST /event {"device","event"[,"lux"]}.
bool postHttpEvent(const char *event, bool withLux, float lux) {
  if (WiFi.status() != WL_CONNECTED) return false;
  JsonDocument body;
  body["device"] = SIRO_HTTP_DEVICE_ID;
  body["event"] = event;
  if (withLux) body["lux"] = lux;
  String payload;
  serializeJson(body, payload);
  HTTPClient http;
  http.setTimeout(2000);
  if (!http.begin(SIRO_HTTP_FALLBACK_URL)) return false;
  http.addHeader("Content-Type", "application/json");
  const int status = http.POST(payload);
  http.end();
  return status >= 200 && status < 300;
}

void netTask(void *) {
  HttpFallbackSync httpSync;
  bool wasWifiUp = false;
  bool mqttUp = false;
  bool inFallback = false;
  uint8_t wifiFailures = 0;
  uint8_t mqttFailures = 0;
  uint32_t nextWifiTry = millis() + wifiRetryBaseMs;  // Let the first WiFi.begin() finish.
  uint32_t nextMqttTry = 0;
  uint32_t mqttDownSince = millis();
  uint32_t lastStatePublish = 0;
  uint32_t lastOtaCheck = 0;
  uint32_t seenSeq = 0;
  uint32_t seenDiagSeq = 0;
  bool otaCheckedOnce = false;
  for (;;) {
    const uint32_t now = millis();
    const bool wifi = WiFi.status() == WL_CONNECTED;
    wifiUp = wifi;
    if (!wifi) {
      if (mqttUp) mqttDownSince = now;
      mqttUp = false;
      linkState = LinkDown;
      wasWifiUp = false;
      if (static_cast<int32_t>(now - nextWifiTry) >= 0) {
        WiFi.reconnect();  // Auto-reconnect is on; this just nudges it with a growing pause.
        nextWifiTry = now + reconnectDelayMs(wifiFailures, wifiRetryBaseMs, wifiRetryMaxMs);
        if (wifiFailures < 8) ++wifiFailures;
      }
      vTaskDelay(pdMS_TO_TICKS(200));
      continue;
    }
    if (!wasWifiUp) {
      wasWifiUp = true;
      wifiFailures = 0;
      configTime(0, 0, "pool.ntp.org");  // Re-arm SNTP; it syncs in the background.
      nextMqttTry = now;
    }
    const bool timeOk = time(nullptr) > minimumSyncedTime;
    if (mqtt.connected()) {
      if (!mqttUp) {
        mqttUp = true;
        mqttFailures = 0;
        inFallback = false;
        lastStatePublish = now;
      }
      mqtt.poll();
      otaConfirm();
      const Snapshot snap = readShared();
      if (snap.seq != seenSeq || sensorIntervalElapsed(now, lastStatePublish, sensorIntervalMs)) {
        seenSeq = snap.seq;
        lastStatePublish = now;
        publishState(snap);
      }
      if (snap.diagSeq != seenDiagSeq) {
        seenDiagSeq = snap.diagSeq;
        publishDiag(snap);
      }
      if (!otaCheckedOnce || sensorIntervalElapsed(now, lastOtaCheck, SIRO_OTA_CHECK_INTERVAL_MS)) {
        otaCheckedOnce = true;
        lastOtaCheck = now;
        otaCheckAndUpdate();  // Blocks only this task; sensors keep sampling.
      }
      linkState = LinkMqtt;
    } else {
      if (mqttUp) mqttDownSince = now;
      mqttUp = false;
      // MQTT needs a real clock for observed_at; without one, retry later (state is not lost).
      if (timeOk && static_cast<int32_t>(now - nextMqttTry) >= 0) {
        if (tryConnectMqtt()) {
          mqttUp = true;
          mqttFailures = 0;
          inFallback = false;
          lastStatePublish = millis();
          seenSeq = readShared().seq;
          linkState = LinkMqtt;
        } else {
          nextMqttTry = millis() + reconnectDelayMs(mqttFailures, mqttRetryBaseMs, mqttRetryMaxMs);
          if (mqttFailures < 8) ++mqttFailures;
        }
      }
      if (!mqttUp && sensorIntervalElapsed(now, mqttDownSince, SIRO_MQTT_FALLBACK_AFTER_MS)) {
        const Snapshot snap = readShared();
        if (!inFallback) {
          inFallback = true;
          httpSync.enter(snap.pressCount);  // Push the current motion snapshot right away.
        }
        linkState = LinkHttp;
        if (httpSync.motionDue(now, snap.pirReady, snap.motion)) {
          httpSync.motionResult(now, snap.motion,
                                postHttpEvent(snap.motion ? "motion_detected" : "motion_cleared",
                                              false, 0.0f));
        }
        if (httpSync.buttonDue(now, snap.pressCount)) {
          httpSync.buttonResult(now, postHttpEvent("button_pressed", false, 0.0f));
        }
        if (httpSync.lightDue(now, snap.lightValid)) {
          httpSync.lightResult(now, postHttpEvent("light_update", true, snap.lux));
        }
      } else if (!mqttUp) {
        linkState = LinkDown;
      }
    }
    vTaskDelay(pdMS_TO_TICKS(20));
  }
}

// -------------------------------------------------------------------- sensors ----

void setup() {
  otaBootCheck();
#if SIRO_HAS_LED
  pinMode(SIRO_LED_PIN, OUTPUT);
#endif
  pinMode(SIRO_PIR_PIN, INPUT);
  pinMode(SIRO_BUTTON_PIN, INPUT_PULLUP);
  button.reset(digitalRead(SIRO_BUTTON_PIN) == LOW);
  Serial.begin(115200);
  pir.reset(millis());
  Wire.begin(SIRO_I2C_SDA_PIN, SIRO_I2C_SCL_PIN);
  Wire.setClock(400000);  // OLED frames are ~1 KB; 100 kHz would stall the sensors.
#if SIRO_HAS_OLED
  face.begin(SIRO_OLED_ADDRESS);
#endif
  lightSensorReady = startLightSensor();
  lastLightRead = millis();
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(SIRO_WIFI_SSID, SIRO_WIFI_PASSWORD);
  network.setTimeout(2);  // Seconds: bounds the TCP connect of MQTT attempts.
  configTime(0, 0, "pool.ntp.org");
  xTaskCreatePinnedToCore(netTask, "net", 16384, nullptr, 1, nullptr, 0);
}

void loop() {
  otaWatchdog();
  const uint32_t now = millis();
  if (lastLoopMs != 0 && now - lastLoopMs > maxLoopGapMs) maxLoopGapMs = now - lastLoopMs;
  lastLoopMs = now;
  const bool pirRaw = digitalRead(SIRO_PIR_PIN) == HIGH;
  if (pirRaw != lastPirRaw) ++pirRawEdges;
  lastPirRaw = pirRaw;
  ++pirSamples;
  if (pirRaw) ++pirHighSamples;
  const bool motionChanged = pir.update(now, pirRaw);
  const bool buttonChanged = button.update(now, digitalRead(SIRO_BUTTON_PIN) == LOW);
  bool lightChanged = false;
  if (sensorIntervalElapsed(now, lastLightRead, sensorIntervalMs)) {
    lastLightRead = now;
    if (!lightSensorReady) {
      lightSensorReady = startLightSensor();
    } else {
      float value = 0.0f;
      const bool hadLight = lightValid;
      lightValid = readLightSensor(value);
      if (lightValid) {
        if (hadLight && fabsf(value - lastLux) > fmaxf(80.0f, lastLux * 0.5f)) {
          face.react(FaceMood::Squint, now, 2500);
        }
        lastLux = value;
      } else {
        lightSensorReady = false;
      }
      lightChanged = true;
    }
  }
  if (motionChanged && pir.ready() && pir.motion()) face.react(FaceMood::Surprised, now, 3000);
  if (buttonChanged && button.down()) face.react(FaceMood::Happy, now, 2500);
  const bool diagDue = sensorIntervalElapsed(now, lastDiag, sensorIntervalMs);
  if (motionChanged || buttonChanged || lightChanged || diagDue) {
    portENTER_CRITICAL(&snapshotLock);
    shared.pirReady = pir.ready();
    shared.motion = pir.motion();
    shared.buttonDown = button.down();
    shared.pressCount = button.pressCount();
    shared.lightValid = lightValid;
    shared.lux = lastLux;
    if (motionChanged || buttonChanged) ++shared.seq;
    if (diagDue) {
      lastDiag = now;
      shared.pirRawEdges = pirRawEdges;
      shared.pirHighPct = pirSamples ? (100UL * pirHighSamples / pirSamples) : 0;
      shared.pirRaw = pirRaw;
      shared.pirPulses = pir.pulsesInWindow(now);
      shared.maxSampleGapMs = maxLoopGapMs;
      ++shared.diagSeq;
    }
    portEXIT_CRITICAL(&snapshotLock);
    if (diagDue) {
      pirRawEdges = pirHighSamples = pirSamples = 0;
      maxLoopGapMs = 0;
    }
  }
  const uint8_t link = linkState;
  face.update(now, wifiUp, link == LinkMqtt ? FaceLink::Mqtt : (link == LinkHttp ? FaceLink::Http : FaceLink::Down),
              lightValid, lastLux);
  delay(10);
}
