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

class PirMotionSampler {
 public:
  explicit PirMotionSampler(uint32_t bootMs) : bootMs_(bootMs) {}

  void reset(uint32_t bootMs) {
    bootMs_ = bootMs;
    ready_ = false;
    motion_ = false;
    candidateActive_ = false;
    recovering_ = false;
  }

  // A broker gap may outlive the last sample. Require a fresh, stable reading
  // before assigning a new observation timestamp after reconnect.
  void invalidate() {
    ready_ = false;
    candidateActive_ = false;
    recovering_ = true;
  }

  // True only for the first post-warm-up sample or a debounced edge.
  bool update(uint32_t now, bool raw) {
    if (!ready_) {
      if (!sensorIntervalElapsed(now, bootMs_, 60000UL)) return false;
      if (recovering_) {
        if (!candidateActive_ || candidate_ != raw) {
          candidateActive_ = true;
          candidate_ = raw;
          candidateSince_ = now;
          return false;
        }
        if (!sensorIntervalElapsed(now, candidateSince_, 500UL)) return false;
        recovering_ = false;
        candidateActive_ = false;
      }
      ready_ = true;
      motion_ = raw;
      return true;
    }
    if (raw == motion_) {
      candidateActive_ = false;
      return false;
    }
    if (!candidateActive_ || candidate_ != raw) {
      candidateActive_ = true;
      candidate_ = raw;
      candidateSince_ = now;
      return false;
    }
    if (!sensorIntervalElapsed(now, candidateSince_, 500UL)) return false;
    motion_ = raw;
    candidateActive_ = false;
    return true;
  }

  bool ready() const { return ready_; }
  bool motion() const { return motion_; }

 private:
  uint32_t bootMs_;
  uint32_t candidateSince_ = 0;
  bool ready_ = false;
  bool motion_ = false;
  bool candidateActive_ = false;
  bool candidate_ = false;
  bool recovering_ = false;
};
