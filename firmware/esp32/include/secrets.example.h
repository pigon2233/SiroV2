#pragma once

#define SIRO_WIFI_SSID "replace-me"
#define SIRO_WIFI_PASSWORD "replace-me"
#define SIRO_MQTT_HOST "192.0.2.1"
#define SIRO_MQTT_PORT 1883
#define SIRO_MQTT_USERNAME "replace-me"
#define SIRO_MQTT_PASSWORD "replace-me"
#define SIRO_DEVICE_ID "siro-node-mqtt-01"  // Must match SIRO_ESP32_MQTT_DEVICE_ID.

// HTTP fallback: used after MQTT stays unreachable for this long; MQTT is retried
// every 5 s and takes over again when it recovers. The HTTP device ID must be the
// one registered by the Windows receiver path (SIRO_ESP32_HTTP_DEVICE_ID), which is
// deliberately different from the MQTT device ID.
#define SIRO_HTTP_FALLBACK_URL "http://192.0.2.10:8765/event"
#define SIRO_HTTP_DEVICE_ID "siro-node-01"
#define SIRO_MQTT_FALLBACK_AFTER_MS 30000UL

// User's ESP32-S3 N16R8 sketch wiring; confirm physical board before flashing.
#define SIRO_PIR_PIN 5
#define SIRO_BUTTON_PIN 4
#define SIRO_I2C_SDA_PIN 8
#define SIRO_I2C_SCL_PIN 9
#define SIRO_BH1750_ADDRESS 0x23

// This is a sensor-only node by default. Enable only after an LED is wired
// and its GPIO is verified for the exact board variant.
#define SIRO_HAS_LED 0
