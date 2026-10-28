#pragma once

#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Wire.h>

// SIRO's little face on a 128x64 SSD1306. Purely cosmetic: a missing or failing
// display only turns every call into a no-op and never blocks the sensors.
enum class FaceMood : uint8_t { Idle, Surprised, Happy, Squint, Confused, Sleep };
enum class FaceLink : uint8_t { Down, Mqtt, Http };

class SiroFace {
 public:
  bool begin(uint8_t address) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() != 0) return false;  // No ACK: screen absent.
    ready_ = oled_.begin(SSD1306_SWITCHCAPVCC, address);
    return ready_;
  }

  // A reaction overrides the resting mood for holdMs (motion, button, light jump).
  void react(FaceMood mood, uint32_t now, uint32_t holdMs) {
    mood_ = mood;
    moodStart_ = now;
    moodUntil_ = now + holdMs;
    lastActivity_ = now;
  }

  void update(uint32_t now, bool wifi, FaceLink link, bool luxValid, float lux) {
    if (!ready_ || now - lastFrame_ < frameMs) return;
    lastFrame_ = now;
    const bool reacting = mood_ != FaceMood::Idle && static_cast<int32_t>(moodUntil_ - now) > 0;
    FaceMood mood = FaceMood::Idle;
    if (reacting) {
      mood = mood_;
    } else if (!wifi || now - lastActivity_ > dozeAfterMs) {
      mood = FaceMood::Sleep;  // Dozes off when nothing has happened for a while.
    } else if (link == FaceLink::Down) {
      mood = FaceMood::Confused;
    }
    // Brief flash when a reaction starts so a detection is hard to miss.
    const bool flash = reacting && now - moodStart_ < 150;
    if (flash != inverted_) {
      oled_.invertDisplay(flash);
      inverted_ = flash;
    }
    oled_.clearDisplay();
    switch (mood) {
      case FaceMood::Surprised: drawSurprised(now); break;
      case FaceMood::Happy: drawHappy(now); break;
      case FaceMood::Squint: drawSquint(); break;
      case FaceMood::Confused: drawConfused(now); break;
      case FaceMood::Sleep: drawSleep(now); break;
      default: drawIdle(now); break;
    }
    drawStatus(now, wifi, link, luxValid, lux);
    oled_.display();
  }

 private:
  static constexpr uint32_t frameMs = 80;
  static constexpr uint32_t dozeAfterMs = 150000;
  Adafruit_SSD1306 oled_{128, 64, &Wire, -1};
  bool ready_ = false;
  bool inverted_ = false;
  FaceMood mood_ = FaceMood::Idle;
  uint32_t moodStart_ = 0;
  uint32_t moodUntil_ = 0;
  uint32_t lastFrame_ = 0;
  uint32_t nextBlink_ = 2500;
  uint32_t blinkEnd_ = 0;
  uint32_t nextLook_ = 4000;
  uint32_t lookEnd_ = 0;
  int8_t lookX_ = 0;
  uint32_t nextYawn_ = 40000;
  uint32_t yawnEnd_ = 0;
  uint32_t lastActivity_ = 0;
  uint32_t nextQuirk_ = 15000;
  uint32_t quirkEnd_ = 0;
  uint8_t quirk_ = 0;

  void eye(int cx, int cy, int w, int h, int lookX, int lookY, int pupil) {
    if (h <= 4) {
      oled_.fillRoundRect(cx - w / 2, cy - 1, w, 3, 1, SSD1306_WHITE);
      return;
    }
    oled_.fillRoundRect(cx - w / 2, cy - h / 2, w, h, 7, SSD1306_WHITE);
    if (pupil > 0) oled_.fillCircle(cx + lookX, cy + lookY, pupil, SSD1306_BLACK);
  }

  void heart(int cx, int cy) {
    oled_.fillCircle(cx - 4, cy - 2, 4, SSD1306_WHITE);
    oled_.fillCircle(cx + 4, cy - 2, 4, SSD1306_WHITE);
    oled_.fillTriangle(cx - 8, cy, cx + 8, cy, cx, cy + 9, SSD1306_WHITE);
  }

  void drawIdle(uint32_t now) {
    if (static_cast<int32_t>(now - nextBlink_) >= 0 && blinkEnd_ < nextBlink_) {
      blinkEnd_ = now + 140;
      nextBlink_ = now + random(2500, 6500);
    }
    if (static_cast<int32_t>(now - nextLook_) >= 0 && lookEnd_ < nextLook_) {
      lookX_ = random(0, 2) ? 7 : -7;
      lookEnd_ = now + random(900, 1800);
      nextLook_ = now + random(5000, 10000);
    }
    if (static_cast<int32_t>(now - nextYawn_) >= 0 && yawnEnd_ < nextYawn_) {
      yawnEnd_ = now + 1800;
      nextYawn_ = now + random(45000, 90000);
    }
    if (static_cast<int32_t>(now - nextQuirk_) >= 0 && quirkEnd_ < nextQuirk_) {
      quirk_ = random(0, 3);  // 0 wink, 1 cross-eyed, 2 gaze up
      quirkEnd_ = now + (quirk_ == 1 ? 1200 : 600);
      nextQuirk_ = now + random(12000, 25000);
    }
    const bool quirky = static_cast<int32_t>(quirkEnd_ - now) > 0;
    const bool yawning = static_cast<int32_t>(yawnEnd_ - now) > 0;
    const bool blinking = static_cast<int32_t>(blinkEnd_ - now) > 0;
    const int look = static_cast<int32_t>(lookEnd_ - now) > 0 ? lookX_ : 0;
    const int h = yawning ? 6 : (blinking ? 3 : 30);
    const int cross = quirky && quirk_ == 1 ? 7 : 0;
    const int up = quirky && quirk_ == 2 ? -7 : 0;
    const int rightH = quirky && quirk_ == 0 ? 3 : h;
    eye(36, 26, 28, h, cross ? cross : look, up, 6);
    eye(92, 26, 28, rightH, cross ? -cross : look, up, 6);
    if (yawning) oled_.fillRoundRect(57, 42, 14, 16, 7, SSD1306_WHITE);
  }

  void drawSurprised(uint32_t now) {
    const int shake = (now - moodStart_ < 600) ? ((now / 80) % 2 ? 2 : -2) : 0;
    eye(38 + shake, 26, 34, 40, 0, 0, 3);
    eye(90 + shake, 26, 34, 40, 0, 0, 3);
    oled_.setTextColor(SSD1306_WHITE);
    oled_.setTextSize(2);
    oled_.setCursor(58, 48);
    oled_.print("!");
  }

  void chevron(int cx, int cy) {
    for (int dy = -1; dy <= 1; ++dy) {
      oled_.drawLine(cx - 14, cy + 7 + dy, cx, cy - 7 + dy, SSD1306_WHITE);
      oled_.drawLine(cx, cy - 7 + dy, cx + 14, cy + 7 + dy, SSD1306_WHITE);
    }
  }

  void drawHappy(uint32_t now) {
    chevron(36, 24);
    chevron(92, 24);
    heart(64, 46 + ((now / 200) % 2 ? 1 : 0));
  }

  void drawSquint() {
    eye(36, 26, 32, 5, 0, 0, 0);
    eye(92, 26, 32, 5, 0, 0, 0);
    oled_.drawLine(54, 50, 74, 50, SSD1306_WHITE);
  }

  void drawConfused(uint32_t now) {
    const int wobble = (now / 500) % 2 ? 1 : 0;
    eye(34, 26, 26, 30, 4, -3 + wobble, 5);
    eye(92, 28, 18, 18, 3, -2, 4);
    oled_.setTextColor(SSD1306_WHITE);
    oled_.setTextSize(2);
    oled_.setCursor(108, 0);
    oled_.print("?");
    oled_.drawLine(52, 52, 58, 49, SSD1306_WHITE);
    oled_.drawLine(58, 49, 64, 52, SSD1306_WHITE);
    oled_.drawLine(64, 52, 70, 49, SSD1306_WHITE);
  }

  void drawSleep(uint32_t now) {
    eye(36, 30, 28, 3, 0, 0, 0);
    eye(92, 30, 28, 3, 0, 0, 0);
    const int phase = static_cast<int>((now / 400) % 4);
    oled_.setTextColor(SSD1306_WHITE);
    oled_.setTextSize(1);
    oled_.setCursor(104 + phase * 3, 18 - phase * 3);
    oled_.print("z");
    oled_.setTextSize(2);
    oled_.setCursor(108, 4);
    oled_.print("Z");
  }

  void drawStatus(uint32_t now, bool wifi, FaceLink link, bool luxValid, float lux) {
    oled_.setTextColor(SSD1306_WHITE);
    for (int i = 0; i < 4; ++i) {
      const int barHeight = 2 + i * 2;
      if (wifi) {
        oled_.fillRect(i * 4, 62 - barHeight, 3, barHeight, SSD1306_WHITE);
      } else {
        oled_.drawPixel(i * 4 + 1, 61, SSD1306_WHITE);
      }
    }
    oled_.setTextSize(1);
    oled_.setCursor(20, 55);
    oled_.print(link == FaceLink::Mqtt ? "M" : (link == FaceLink::Http ? "H" : "-"));
    if (luxValid) {
      char text[10];
      snprintf(text, sizeof(text), "%.0f", lux);
      oled_.setCursor(128 - 6 * static_cast<int>(strlen(text)), 55);
      oled_.print(text);
    }
    (void)now;
  }
};
