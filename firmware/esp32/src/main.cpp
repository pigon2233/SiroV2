#include <Arduino.h>
#include <ArduinoJson.h>
#include <ArduinoMqttClient.h>
#include <WiFi.h>
#include <Wire.h>
#include <time.h>

#include "secrets.h"
#include "sensor_telemetry.h"

WiFiClient network;
MqttClient mqtt(network);
String prefix = String("siro/devices/") + SIRO_DEVICE_ID + "/";
#if SIRO_HAS_LED
String lastCommandId;
#endif
constexpr time_t minimumSyncedTime = 1700000000;
constexpr uint32_t sensorIntervalMs = 10000UL;
PirMotionSampler pir(0);
ButtonSampler button;
uint32_t lastLightRead = 0;
uint32_t lastStatePublish = 0;
bool lightSensorReady = false;
bool lightValid = false;
bool connectedOnce = false;
float lastLux = 0.0f;

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
    delay(250);
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

void connectMqtt() {
  if (connectedOnce) {
    pir.invalidate();
    lightValid = false;
  }
  mqtt.setId(SIRO_DEVICE_ID);
  mqtt.setUsernamePassword(SIRO_MQTT_USERNAME, SIRO_MQTT_PASSWORD);
  mqtt.beginWill(prefix + "availability", 7, true, 1);
  mqtt.print("offline");
  mqtt.endWill();
#if SIRO_HAS_LED
  mqtt.onMessage(onMessage);
#endif
  while (!mqtt.connect(SIRO_MQTT_HOST, SIRO_MQTT_PORT)) delay(1000);
  mqtt.beginMessage(prefix + "availability", 6, true, 1, false);
  mqtt.print("online");
  mqtt.endMessage();
#if SIRO_HAS_LED
  mqtt.subscribe(prefix + "command", 1);
#endif
  publishState();
  connectedOnce = true;
}

void setup() {
#if SIRO_HAS_LED
  pinMode(SIRO_LED_PIN, OUTPUT);
#endif
  pinMode(SIRO_PIR_PIN, INPUT);
  pinMode(SIRO_BUTTON_PIN, INPUT_PULLUP);
  button.reset(digitalRead(SIRO_BUTTON_PIN) == LOW);
  Serial.begin(115200);
  pir.reset(millis());
  Wire.begin(SIRO_I2C_SDA_PIN, SIRO_I2C_SCL_PIN);
  Wire.setClock(100000);
  lightSensorReady = startLightSensor();
  lastLightRead = millis();
  WiFi.begin(SIRO_WIFI_SSID, SIRO_WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) delay(250);
  configTime(0, 0, "pool.ntp.org");
  if (!waitForTimeSync()) {
    Serial.println("NTP synchronization timed out; MQTT remains disconnected.");
    ESP.restart();
    return;
  }
  connectMqtt();
}

void loop() {
  if (time(nullptr) <= minimumSyncedTime) {
    delay(250);
    return;
  }
  if (WiFi.status() != WL_CONNECTED) ESP.restart();
  if (!mqtt.connected()) connectMqtt();
  mqtt.poll();
  const uint32_t now = millis();
  const bool motionChanged = pir.update(now, digitalRead(SIRO_PIR_PIN) == HIGH);
  const bool buttonChanged = button.update(now, digitalRead(SIRO_BUTTON_PIN) == LOW);
  if (sensorIntervalElapsed(now, lastLightRead, sensorIntervalMs)) {
    lastLightRead = now;
    if (!lightSensorReady) {
      lightSensorReady = startLightSensor();
    } else {
      float value = 0.0f;
      lightValid = readLightSensor(value);
      if (lightValid) {
        lastLux = value;
      } else {
        lightSensorReady = false;
      }
    }
  }
  if (motionChanged || buttonChanged ||
      sensorIntervalElapsed(now, lastStatePublish, sensorIntervalMs)) {
    publishState();
  }
  delay(10);
}
