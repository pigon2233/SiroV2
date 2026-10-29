#pragma once

#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <Update.h>
#include <esp_ota_ops.h>
#include <mbedtls/sha256.h>

// Pull-based OTA. The node asks the PC relay for a manifest, only accepts a strictly newer
// version, verifies sha256 before the partition switch, and the first boots of the new image
// must prove themselves (connect to MQTT) or the previous partition is restored.
//
// Disabled unless secrets.h defines SIRO_OTA_BASE_URL, e.g. "http://192.168.1.193:8765/ota".
// Build the image to serve with PLATFORMIO_BUILD_FLAGS='-DSIRO_FW_VERSION=\"1.0.1\"'.

#ifndef SIRO_FW_VERSION
#define SIRO_FW_VERSION "1.0.3"
#endif
#ifndef SIRO_OTA_CHECK_INTERVAL_MS
#define SIRO_OTA_CHECK_INTERVAL_MS (6UL * 60UL * 60UL * 1000UL)
#endif
#ifndef SIRO_OTA_CONFIRM_TIMEOUT_MS
#define SIRO_OTA_CONFIRM_TIMEOUT_MS 120000UL
#endif
#ifndef SIRO_OTA_MAX_BOOT_TRIES
#define SIRO_OTA_MAX_BOOT_TRIES 3
#endif

inline bool otaParseVersion(const char *text, int out[3]) {
  char tail = 0;
  return sscanf(text, "%d.%d.%d%c", &out[0], &out[1], &out[2], &tail) == 3;
}

inline bool otaIsNewer(const char *candidate, const char *current) {
  int a[3], b[3];
  if (!otaParseVersion(candidate, a) || !otaParseVersion(current, b)) return false;
  for (int i = 0; i < 3; ++i) {
    if (a[i] != b[i]) return a[i] > b[i];
  }
  return false;
}

// Restore the partition that was running before the update; clears the pending state first so
// a missing/invalid previous image can never cause a reboot loop.
inline void otaRollback(Preferences &prefs) {
  String previous = prefs.getString("prev", "");
  prefs.putBool("pending", false);
  prefs.end();
  const esp_partition_t *target = previous.length()
      ? esp_partition_find_first(ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_ANY, previous.c_str())
      : nullptr;
  if (target != nullptr && esp_ota_set_boot_partition(target) == ESP_OK) {
    Serial.println("OTA: new image failed self-check, rolling back.");
    ESP.restart();
  }
}

inline bool otaPending() {
  Preferences prefs;
  prefs.begin("ota", true);
  const bool pending = prefs.getBool("pending", false);
  prefs.end();
  return pending;
}

// Call first thing in setup(). Counts this boot against the new image's budget.
inline void otaBootCheck() {
  Preferences prefs;
  prefs.begin("ota", false);
  if (!prefs.getBool("pending", false)) {
    prefs.end();
    return;
  }
  const uint8_t tries = prefs.getUChar("tries", 0) + 1;
  prefs.putUChar("tries", tries);
  if (tries > SIRO_OTA_MAX_BOOT_TRIES) otaRollback(prefs);
  prefs.end();
}

// Call while waiting for connectivity and from loop(): an unconfirmed image that hangs
// (e.g. Wi-Fi/MQTT never comes up) is rolled back after the confirm timeout.
inline void otaWatchdog() {
  if (millis() < SIRO_OTA_CONFIRM_TIMEOUT_MS) return;
  Preferences prefs;
  prefs.begin("ota", false);
  if (prefs.getBool("pending", false)) otaRollback(prefs);
  prefs.end();
}

// Self-check passed (MQTT connected): keep the new image.
inline void otaConfirm() {
  Preferences prefs;
  prefs.begin("ota", false);
  if (prefs.getBool("pending", false)) {
    prefs.putBool("pending", false);
    Serial.println("OTA: new image confirmed.");
  }
  prefs.end();
}

// Returns only on "no update / failure"; a successful update restarts the chip.
inline void otaCheckAndUpdate() {
#ifdef SIRO_OTA_BASE_URL
  if (otaPending() || WiFi.status() != WL_CONNECTED) return;
  const String base = SIRO_OTA_BASE_URL;

  HTTPClient http;
  http.setTimeout(5000);
  if (!http.begin(base + "/manifest")) return;
  if (http.GET() != 200) {
    http.end();
    return;
  }
  JsonDocument manifest;
  const DeserializationError parsed = deserializeJson(manifest, http.getString());
  http.end();
  if (parsed) return;
  const char *version = manifest["version"] | "";
  const char *hash = manifest["sha256"] | "";
  const size_t size = manifest["size"] | 0;
  if (!otaIsNewer(version, SIRO_FW_VERSION) || strlen(hash) != 64 || size == 0) return;
  const esp_partition_t *next = esp_ota_get_next_update_partition(nullptr);
  const esp_partition_t *running = esp_ota_get_running_partition();
  if (next == nullptr || running == nullptr || size > next->size) return;

  Serial.printf("OTA: %s -> %s (%u bytes)\n", SIRO_FW_VERSION, version, static_cast<unsigned>(size));
  if (!http.begin(base + "/firmware")) return;
  http.setTimeout(15000);
  if (http.GET() != 200 || http.getSize() != static_cast<int>(size) || !Update.begin(size)) {
    http.end();
    return;
  }
  mbedtls_sha256_context sha;
  mbedtls_sha256_init(&sha);
  mbedtls_sha256_starts(&sha, 0);
  WiFiClient *stream = http.getStreamPtr();
  uint8_t buffer[1024];
  size_t written = 0;
  bool ok = true;
  uint32_t lastData = millis();
  while (written < size && ok) {
    const size_t want = min(sizeof(buffer), size - written);
    const int got = stream->readBytes(buffer, want);
    if (got <= 0) {
      if (millis() - lastData > 15000UL) ok = false;
      delay(5);
      continue;
    }
    lastData = millis();
    mbedtls_sha256_update(&sha, buffer, got);
    ok = Update.write(buffer, got) == static_cast<size_t>(got);
    written += got;
  }
  http.end();
  uint8_t digest[32];
  mbedtls_sha256_finish(&sha, digest);
  mbedtls_sha256_free(&sha);
  char hex[65];
  for (int i = 0; i < 32; ++i) snprintf(hex + 2 * i, 3, "%02x", digest[i]);
  // Verify before Update.end(): end() is what switches the boot partition.
  if (!ok || written != size || strcasecmp(hex, hash) != 0) {
    Update.abort();
    Serial.println("OTA: download or sha256 verification failed; keeping current image.");
    return;
  }
  Preferences prefs;
  prefs.begin("ota", false);
  prefs.putString("prev", running->label);
  prefs.putUChar("tries", 0);
  prefs.putBool("pending", true);
  prefs.end();
  if (!Update.end(true)) {
    Serial.println("OTA: finalize failed; keeping current image.");
    prefs.begin("ota", false);
    prefs.putBool("pending", false);
    prefs.end();
    return;
  }
  Serial.println("OTA: image verified, restarting into new partition.");
  delay(200);
  ESP.restart();
#endif
}
