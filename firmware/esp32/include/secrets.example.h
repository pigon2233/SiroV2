#pragma once

#define SIRO_WIFI_SSID "replace-me"
#define SIRO_WIFI_PASSWORD "replace-me"
#define SIRO_MQTT_HOST "192.0.2.1"
#define SIRO_MQTT_PORT 1883
#define SIRO_MQTT_USERNAME "replace-me"
#define SIRO_MQTT_PASSWORD "replace-me"
#define SIRO_DEVICE_ID "esp32-lab-01"

// Match these to the actual board and wiring before flashing. ESP32 DevKit
// defaults are shown; other ESP32 variants may use different I2C pins.
#define SIRO_PIR_PIN 27
#define SIRO_I2C_SDA_PIN 21
#define SIRO_I2C_SCL_PIN 22
#define SIRO_BH1750_ADDRESS 0x23
