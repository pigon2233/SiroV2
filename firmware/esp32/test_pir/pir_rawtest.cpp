// Raw PIR bench test: no OLED, no OTA, no filtering. Samples GPIO5 every 20 ms, prints each
// edge on the serial port and publishes per-second raw statistics to
// siro/devices/<id>/pirraw (not retained, not state: SIRO ignores it).
#include <Arduino.h>
#include <ArduinoJson.h>
#include <ArduinoMqttClient.h>
#include <WiFi.h>

#include "secrets.h"
#include "ota.h"  // Keeps the bench image replaceable over the air (new version -> production).

WiFiClient network;
MqttClient mqtt(network);
String topic = String("siro/devices/") + SIRO_DEVICE_ID + "/pirraw";
constexpr uint32_t sampleMs = 20;
uint32_t lastSample = 0;
uint32_t lastReport = 0;
uint32_t lastMqttTry = 0;
uint32_t levelSince = 0;
bool level = false;
uint32_t edges = 0;
uint32_t highMs = 0;
uint32_t maxHighRunMs = 0;
uint32_t totalEdges = 0;
uint32_t lastOtaCheck = 0;
bool otaCheckedOnce = false;

void connectMqtt(uint32_t now) {
  if (mqtt.connected() || WiFi.status() != WL_CONNECTED || now - lastMqttTry < 5000UL) return;
  lastMqttTry = now;
  mqtt.setId(String(SIRO_DEVICE_ID) + "-pirraw");
  mqtt.setUsernamePassword(SIRO_MQTT_USERNAME, SIRO_MQTT_PASSWORD);
  mqtt.connect(SIRO_MQTT_HOST, SIRO_MQTT_PORT);
}

void setup() {
  otaBootCheck();
  Serial.begin(115200);
  pinMode(SIRO_PIR_PIN, INPUT);
  level = digitalRead(SIRO_PIR_PIN) == HIGH;
  levelSince = millis();
  WiFi.begin(SIRO_WIFI_SSID, SIRO_WIFI_PASSWORD);
  Serial.println("PIR raw test: GPIO" + String(SIRO_PIR_PIN));
}

void loop() {
  const uint32_t now = millis();
  connectMqtt(now);
  otaWatchdog();
  if (mqtt.connected()) {
    mqtt.poll();
    otaConfirm();
    if (!otaCheckedOnce || now - lastOtaCheck >= SIRO_OTA_CHECK_INTERVAL_MS) {
      otaCheckedOnce = true;
      lastOtaCheck = now;
      otaCheckAndUpdate();
    }
  }
  if (now - lastSample >= sampleMs) {
    lastSample = now;
    const bool raw = digitalRead(SIRO_PIR_PIN) == HIGH;
    if (raw) highMs += sampleMs;
    if (raw != level) {
      const uint32_t held = now - levelSince;
      if (level && held > maxHighRunMs) maxHighRunMs = held;
      Serial.println(String(level ? "HIGH held " : "LOW held ") + held + " ms -> " +
                     (raw ? "HIGH" : "LOW"));
      level = raw;
      levelSince = now;
      ++edges;
      ++totalEdges;
    }
  }
  if (now - lastReport >= 1000UL) {
    lastReport = now;
    if (mqtt.connected()) {
      JsonDocument report;
      report["pir_raw"] = level ? 1 : 0;
      report["edges"] = edges;
      report["total_edges"] = totalEdges;
      report["high_ms"] = highMs;
      report["max_high_run_ms"] = maxHighRunMs;
      report["cur_run_ms"] = now - levelSince;
      String payload;
      serializeJson(report, payload);
      mqtt.beginMessage(topic, payload.length(), false, 0, false);
      mqtt.print(payload);
      mqtt.endMessage();
    }
    edges = 0;
    highMs = 0;
    maxHighRunMs = 0;
  }
}
