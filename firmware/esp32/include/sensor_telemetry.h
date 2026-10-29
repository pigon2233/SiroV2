#pragma once

#include <stdint.h>

// uint32_t subtraction keeps these intervals correct across millis() rollover.
inline bool sensorIntervalElapsed(uint32_t now, uint32_t since, uint32_t interval) {
  return static_cast<uint32_t>(now - since) >= interval;
}

inline float luxFromBh1750Raw(uint16_t raw) {
  return static_cast<float>(raw) / 1.2f;
}

class ButtonSampler {
 public:
  void reset(bool rawDown) {
    down_ = rawDown;
    candidateActive_ = false;
    pressCount_ = 0;
  }

  // Count stable presses, not boot-time held state or electrical bounce.
  bool update(uint32_t now, bool rawDown) {
    if (rawDown == down_) {
      candidateActive_ = false;
      return false;
    }
    if (!candidateActive_ || candidate_ != rawDown) {
      candidateActive_ = true;
      candidate_ = rawDown;
      candidateSince_ = now;
      return false;
    }
    if (!sensorIntervalElapsed(now, candidateSince_, 50UL)) return false;
    down_ = rawDown;
    candidateActive_ = false;
    if (down_) ++pressCount_;
    return true;
  }

  bool down() const { return down_; }
  uint32_t pressCount() const { return pressCount_; }

 private:
  uint32_t candidateSince_ = 0;
  uint32_t pressCount_ = 0;
  bool down_ = false;
  bool candidateActive_ = false;
  bool candidate_ = false;
};

// PIR tuning. This module reports ~1 s HIGH pulses (about every 3-4 s) while someone moves, so
// presence is decided from a pulse count / duty cycle over a window and then held, not from
// the length of a single pulse.
constexpr uint32_t kPirWarmupMs = 60000UL;       // Sensor settle time after boot.
constexpr uint32_t kPirPulseDebounceMs = 150UL;  // A level must hold this long to count.
constexpr uint32_t kPirWindowMs = 10000UL;       // Look-back window for pulses / duty.
constexpr uint8_t kPirMinPulses = 2;             // Pulses in the window that mean "someone".
constexpr uint8_t kPirDutyPercent = 15;          // ...or HIGH share of the window (>= this).
constexpr uint32_t kPirLongHighMs = 1500UL;      // ...or one sustained HIGH of this length.
constexpr uint32_t kPirHoldMs = 25000UL;         // Presence is held and renewed by new pulses.
constexpr uint32_t kPirRecoverStableMs = 500UL;  // Stable raw level needed after a reconnect.

class PirMotionSampler {
 public:
  explicit PirMotionSampler(uint32_t bootMs) : bootMs_(bootMs) {}

  void reset(uint32_t bootMs) {
    *this = PirMotionSampler(bootMs);
  }

  // A broker gap may outlive the last sample. Require a fresh, stable reading
  // before assigning a new observation timestamp after reconnect.
  void invalidate() {
    ready_ = false;
    recovering_ = true;
    recoverActive_ = false;
  }

  // True only for the first post-warm-up/recovery sample or when presence flips.
  bool update(uint32_t now, bool raw) {
    raw_ = raw;
    if (!ready_) {
      if (!sensorIntervalElapsed(now, bootMs_, kPirWarmupMs)) return false;
      if (recovering_) {
        if (!recoverActive_ || recoverLevel_ != raw) {
          recoverActive_ = true;
          recoverLevel_ = raw;
          recoverSince_ = now;
          return false;
        }
        if (!sensorIntervalElapsed(now, recoverSince_, kPirRecoverStableMs)) return false;
        recovering_ = false;
        recoverActive_ = false;
      }
      ready_ = true;
      level_ = raw;  // First sample goes through the same confirmation as any other.
      candidateActive_ = false;
      if (level_) startPulse(now);
      motion_ = motion_ && static_cast<int32_t>(holdUntil_ - now) > 0;
      return true;
    }
    trackLevel(now, raw);
    const bool presence = evidence(now) || (motion_ && static_cast<int32_t>(holdUntil_ - now) > 0);
    if (evidence(now)) holdUntil_ = now + kPirHoldMs;
    if (presence == motion_) return false;
    motion_ = presence;
    return true;
  }

  bool ready() const { return ready_; }
  bool motion() const { return motion_; }
  bool raw() const { return raw_; }

  // Debounced pulses that started within the look-back window.
  uint8_t pulsesInWindow(uint32_t now) const {
    uint8_t count = 0;
    for (const Pulse &pulse : pulses_) {
      if (pulse.used && !sensorIntervalElapsed(now, pulse.start, kPirWindowMs)) ++count;
    }
    return count;
  }

 private:
  struct Pulse {
    uint32_t start = 0;
    uint32_t end = 0;
    bool used = false;
    bool open = false;
  };

  uint32_t bootMs_;
  uint32_t candidateSince_ = 0;
  uint32_t recoverSince_ = 0;
  uint32_t holdUntil_ = 0;
  Pulse pulses_[8];
  uint8_t next_ = 0;
  bool ready_ = false;
  bool motion_ = false;
  bool raw_ = false;
  bool level_ = false;  // Debounced level.
  bool candidateActive_ = false;
  bool candidate_ = false;
  bool recovering_ = false;
  bool recoverActive_ = false;
  bool recoverLevel_ = false;

  void startPulse(uint32_t now) {
    Pulse &pulse = pulses_[next_];
    pulse.start = now;
    pulse.end = now;
    pulse.used = true;
    pulse.open = true;
    next_ = (next_ + 1) % 8;
  }

  Pulse *openPulse() {
    for (Pulse &pulse : pulses_) {
      if (pulse.used && pulse.open) return &pulse;
    }
    return nullptr;
  }

  void trackLevel(uint32_t now, bool raw) {
    if (raw == level_) {
      candidateActive_ = false;
      return;
    }
    if (!candidateActive_ || candidate_ != raw) {
      candidateActive_ = true;
      candidate_ = raw;
      candidateSince_ = now;
      return;
    }
    if (!sensorIntervalElapsed(now, candidateSince_, kPirPulseDebounceMs)) return;
    level_ = raw;
    candidateActive_ = false;
    if (level_) {
      startPulse(candidateSince_);  // The pulse began when the level first changed.
    } else if (Pulse *pulse = openPulse()) {
      pulse->end = candidateSince_;
      pulse->open = false;
    }
  }

  // Someone is moving: enough pulses, enough HIGH time, or one long HIGH.
  bool evidence(uint32_t now) const {
    uint32_t highMs = 0;
    uint8_t count = 0;
    for (const Pulse &pulse : pulses_) {
      if (!pulse.used) continue;
      const uint32_t ageStart = now - pulse.start;
      const uint32_t ageEnd = pulse.open ? 0u : now - pulse.end;
      if (ageStart < kPirWindowMs) ++count;
      if (ageEnd < kPirWindowMs) {
        const uint32_t from = ageStart < kPirWindowMs ? ageStart : kPirWindowMs;
        highMs += from - ageEnd;
      }
      if (pulse.open && ageStart >= kPirLongHighMs) return true;
      if (!pulse.open && pulse.end - pulse.start >= kPirLongHighMs && ageEnd < kPirWindowMs) {
        return true;
      }
    }
    return count >= kPirMinPulses || highMs * 100UL >= kPirWindowMs * kPirDutyPercent;
  }
};
