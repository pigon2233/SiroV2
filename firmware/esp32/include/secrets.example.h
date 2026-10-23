#pragma once

#define SIRO_WIFI_SSID "replace-me"
#define SIRO_WIFI_PASSWORD "replace-me"
#define SIRO_MQTT_HOST "192.0.2.1"
#define SIRO_MQTT_PORT 1883
#define SIRO_MQTT_USERNAME "replace-me"
#define SIRO_MQTT_PASSWORD "replace-me"
#define SIRO_DEVICE_ID "esp32-lab-01"

// User's ESP32-S3 N16R8 sketch wiring; confirm physical board before flashing.
#define SIRO_PIR_PIN 5
#define SIRO_BUTTON_PIN 4
#define SIRO_I2C_SDA_PIN 8
#define SIRO_I2C_SCL_PIN 9
#define SIRO_BH1750_ADDRESS 0x23

// This is a sensor-only node by default. Enable only after an LED is wired
// and its GPIO is verified for the exact board variant.
#define SIRO_HAS_LED 0
