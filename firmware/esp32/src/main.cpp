#include <Arduino.h>
#include <ArduinoJson.h>
#include <ArduinoMqttClient.h>
#include <WiFi.h>
#include <time.h>

#include "secrets.h"

WiFiClient network;
MqttClient mqtt(network);
String prefix = String("siro/devices/") + SIRO_DEVICE_ID + "/";
String lastCommandId;
constexpr time_t minimumSyncedTime = 1700000000;

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
  state["properties"]["power"] = digitalRead(SIRO_LED_PIN) == HIGH;
  publishJson(prefix + "state", state, true);
}

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

void connectMqtt() {
  mqtt.setId(SIRO_DEVICE_ID);
  mqtt.setUsernamePassword(SIRO_MQTT_USERNAME, SIRO_MQTT_PASSWORD);
  mqtt.beginWill(prefix + "availability", 7, true, 1);
  mqtt.print("offline");
  mqtt.endWill();
  mqtt.onMessage(onMessage);
  while (!mqtt.connect(SIRO_MQTT_HOST, SIRO_MQTT_PORT)) delay(1000);
  mqtt.beginMessage(prefix + "availability", 6, true, 1, false);
  mqtt.print("online");
  mqtt.endMessage();
  mqtt.subscribe(prefix + "command", 1);
  publishState();
}

void setup() {
  pinMode(SIRO_LED_PIN, OUTPUT);
  Serial.begin(115200);
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
  delay(10);
}
