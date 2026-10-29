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

WiFiClient network;
MqttClient mqtt(network);
String prefix = String("siro/devices/") + SIRO_DEVICE_ID + "/";
#if SIRO_HAS_LED
String lastCommandId;
#endif
constexpr time_t minimumSyncedTime = 1700000000;
constexpr uint32_t sensorIntervalMs = 10000UL;
constexpr uint32_t mqttRetryMs = 5000UL;
PirMotionSampler pir(0);
ButtonSampler button;
SiroFace face;
uint32_t lastLightRead = 0;
uint32_t lastStatePublish = 0;
bool lightSensorReady = false;
bool lightValid = false;
bool connectedOnce = false;
float lastLux = 0.0f;
bool mqttUp = false;
bool lastPirRaw = false;
uint32_t pirRawEdges = 0;
uint32_t pirHighSamples = 0;
uint32_t pirSamples = 0;
uint32_t lastDiag = 0;
uint32_t mqttDownSince = 0;
uint32_t lastMqttAttempt = 0;
uint32_t lastHttpLight = 0;
uint32_t lastOtaCheck = 0;
bool otaCheckedOnce = false;

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

bool waitForTimeSync() {
  const uint32_t started = millis();
  while (time(nullptr) <= minimumSyncedTime) {
    if (millis() - started >= 30000UL) return false;
    otaWatchdog();
    face.update(millis(), true, FaceLink::Down, false, 0.0f);
    delay(50);
  }
  return true;
}

void publishJson(const String &topic, JsonDocument &document, bool retain) {
  String payload;
  serializeJson(document, payload);
  mqtt.beginMessage(topic, payload.length(), retain, 1, false);
  mqtt.print(payload);
  mqtt.endMessage();
}

void publishState() {
  JsonDocument state;
  state["observed_at_epoch"] = time(nullptr);
#if SIRO_HAS_LED
  state["properties"]["power"] = digitalRead(SIRO_LED_PIN) == HIGH;
#endif
  state["properties"]["button_down"] = button.down();
  state["properties"]["button_press_count"] = button.pressCount();
  if (pir.ready()) state["properties"]["motion"] = pir.motion();
  if (lightValid) state["properties"]["illuminance"] = lastLux;
  publishJson(prefix + "state", state, true);
  lastStatePublish = millis();
}

#if SIRO_HAS_LED
void publishAck(const String &commandId, const char *status) {
  JsonDocument ack;
  ack["command_id"] = commandId;
  ack["status"] = status;
  publishJson(prefix + "ack", ack, false);
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
  publishState();  // Ack alone is not success; gateway confirms this state readback.
}
#endif

// One bounded connect attempt; returns false so loop() can fall back to HTTP.
bool tryConnectMqtt() {
  mqtt.setId(SIRO_DEVICE_ID);
  mqtt.setUsernamePassword(SIRO_MQTT_USERNAME, SIRO_MQTT_PASSWORD);
  mqtt.beginWill(prefix + "availability", 7, true, 1);
  mqtt.print("offline");
  mqtt.endWill();
#if SIRO_HAS_LED
  mqtt.onMessage(onMessage);
#endif
  if (!mqtt.connect(SIRO_MQTT_HOST, SIRO_MQTT_PORT)) return false;
  if (connectedOnce) {
    pir.invalidate();
    lightValid = false;
  }
  mqtt.beginMessage(prefix + "availability", 6, true, 1, false);
  mqtt.print("online");
  mqtt.endMessage();
#if SIRO_HAS_LED
  mqtt.subscribe(prefix + "command", 1);
#endif
  publishState();
  connectedOnce = true;
  return true;
}

// HTTP fallback uses the legacy receiver contract: POST /event {"device","event"[,"lux"]}.
void postHttpEvent(const char *event, bool withLux) {
  if (WiFi.status() != WL_CONNECTED) return;
  JsonDocument body;
  body["device"] = SIRO_HTTP_DEVICE_ID;
  body["event"] = event;
  if (withLux) body["lux"] = lastLux;
  String payload;
  serializeJson(body, payload);
  HTTPClient http;
  http.setTimeout(2000);
  if (!http.begin(SIRO_HTTP_FALLBACK_URL)) return;
  http.addHeader("Content-Type", "application/json");
  http.POST(payload);
  http.end();
}

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
  WiFi.begin(SIRO_WIFI_SSID, SIRO_WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    otaWatchdog();
    face.update(millis(), false, FaceLink::Down, false, 0.0f);
    delay(50);
  }
  configTime(0, 0, "pool.ntp.org");
  if (!waitForTimeSync()) {
    Serial.println("NTP synchronization timed out; MQTT remains disconnected.");
    ESP.restart();
    return;
  }
  mqttDownSince = millis();
  lastMqttAttempt = mqttDownSince - mqttRetryMs;
}

void loop() {
  otaWatchdog();
  if (time(nullptr) <= minimumSyncedTime) {
    face.update(millis(), true, FaceLink::Down, false, 0.0f);
    delay(50);
    return;
  }
  if (WiFi.status() != WL_CONNECTED) ESP.restart();
  const uint32_t now = millis();
  if (mqtt.connected()) {
    mqttUp = true;
    mqtt.poll();
  } else {
    if (mqttUp) mqttDownSince = now;
    mqttUp = false;
    if (now - lastMqttAttempt >= mqttRetryMs) {
      lastMqttAttempt = now;
      if (tryConnectMqtt()) mqttUp = true;
    }
  }
  if (mqttUp) {
    otaConfirm();
    if (!otaCheckedOnce || now - lastOtaCheck >= SIRO_OTA_CHECK_INTERVAL_MS) {
      otaCheckedOnce = true;
      lastOtaCheck = now;
      otaCheckAndUpdate();
    }
  }
  const bool httpFallback = !mqttUp && now - mqttDownSince >= SIRO_MQTT_FALLBACK_AFTER_MS;
  const bool pirRaw = digitalRead(SIRO_PIR_PIN) == HIGH;
  if (pirRaw != lastPirRaw) ++pirRawEdges;
  lastPirRaw = pirRaw;
  ++pirSamples;
  if (pirRaw) ++pirHighSamples;
  const bool motionChanged = pir.update(now, pirRaw);
  const bool buttonChanged = button.update(now, digitalRead(SIRO_BUTTON_PIN) == LOW);
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
    }
  }
  if (motionChanged && pir.ready() && pir.motion()) face.react(FaceMood::Surprised, now, 3000);
  if (buttonChanged && button.down()) face.react(FaceMood::Happy, now, 2500);
  face.update(now, WiFi.status() == WL_CONNECTED,
              mqttUp ? FaceLink::Mqtt : (httpFallback ? FaceLink::Http : FaceLink::Down),
              lightValid, lastLux);
  if (mqttUp && sensorIntervalElapsed(now, lastDiag, sensorIntervalMs)) {
    // Raw PIR diagnostics on a separate topic: fast edges mean noise, long HIGH means retrigger.
    lastDiag = now;
    JsonDocument diag;
    diag["pir_raw_edges"] = pirRawEdges;
    diag["pir_high_pct"] = pirSamples ? (100UL * pirHighSamples / pirSamples) : 0;
    diag["oled"] = SIRO_HAS_OLED;
    diag["fw"] = SIRO_FW_VERSION;
    publishJson(prefix + "diag", diag, false);
    pirRawEdges = pirHighSamples = pirSamples = 0;
  }
  if (mqttUp) {
    if (motionChanged || buttonChanged ||
        sensorIntervalElapsed(now, lastStatePublish, sensorIntervalMs)) {
      publishState();
    }
  } else if (httpFallback) {
    if (motionChanged && pir.ready()) postHttpEvent(pir.motion() ? "motion_detected" : "motion_cleared", false);
    if (buttonChanged && button.down()) postHttpEvent("button_pressed", false);
    if (lightValid && sensorIntervalElapsed(now, lastHttpLight, sensorIntervalMs)) {
      lastHttpLight = now;
      postHttpEvent("light_update", true);
    }
  }
  delay(10);
}
