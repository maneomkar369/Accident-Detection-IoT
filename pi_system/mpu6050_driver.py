"""
mpu6050_driver.py — MPU6050 IMU driver with dual-mode crash detection.

Mode 1 (real Pi): reads via I2C using smbus2
Mode 2 (simulation / testing): generates realistic fake sensor data

Crash is flagged only when BOTH accelerometer AND gyroscope
exceed their thresholds (double-check → reduces false positives).
"""

import time
import math
import random
from config import (
    I2C_BUS, MPU6050_ADDRESS,
    ACCEL_CRASH_THRESHOLD, GYRO_CRASH_THRESHOLD,
    CRASH_CONFIRMATION_MS
)

# MPU6050 registers
_PWR_MGMT_1   = 0x6B
_ACCEL_XOUT_H = 0x3B
_GYRO_XOUT_H  = 0x43
_ACCEL_CFG    = 0x1C
_GYRO_CFG     = 0x1B

# ±4g → 8192 LSB/g;  ±500°/s → 65.5 LSB/(°/s)
_ACCEL_SCALE = 8192.0
_GYRO_SCALE  = 65.5


class MPU6050Driver:

    def __init__(self):
        self._sim = False
        self._candidate_t = None
        try:
            import smbus2
            self._bus = smbus2.SMBus(I2C_BUS)
            self._init_sensor()
            print("[MPU6050] ✅ Hardware sensor initialised")
        except Exception as e:
            self._sim = True
            print(f"[MPU6050] ⚠️  Hardware not found ({e}) — SIMULATION MODE")

    def _init_sensor(self):
        import smbus2
        self._bus.write_byte_data(MPU6050_ADDRESS, _PWR_MGMT_1, 0x00)
        time.sleep(0.1)
        self._bus.write_byte_data(MPU6050_ADDRESS, _ACCEL_CFG, 0x08)  # ±4g
        self._bus.write_byte_data(MPU6050_ADDRESS, _GYRO_CFG,  0x08)  # ±500°/s
        time.sleep(0.05)

    def _read_word(self, reg):
        hi = self._bus.read_byte_data(MPU6050_ADDRESS, reg)
        lo = self._bus.read_byte_data(MPU6050_ADDRESS, reg + 1)
        v  = (hi << 8) | lo
        return v - 65536 if v > 32767 else v

    # ── Raw readings ──────────────────────────────────────────

    def get_accel(self):
        """Returns (ax, ay, az) in g."""
        if self._sim:
            return (
                random.gauss(0.05, 0.02),
                random.gauss(0.01, 0.02),
                random.gauss(1.02, 0.01),
            )
        return (
            self._read_word(_ACCEL_XOUT_H)     / _ACCEL_SCALE,
            self._read_word(_ACCEL_XOUT_H + 2) / _ACCEL_SCALE,
            self._read_word(_ACCEL_XOUT_H + 4) / _ACCEL_SCALE,
        )

    def get_gyro(self):
        """Returns (gx, gy, gz) in °/s."""
        if self._sim:
            return (
                random.gauss(0, 2),
                random.gauss(0, 2),
                random.gauss(0, 2),
            )
        return (
            self._read_word(_GYRO_XOUT_H)     / _GYRO_SCALE,
            self._read_word(_GYRO_XOUT_H + 2) / _GYRO_SCALE,
            self._read_word(_GYRO_XOUT_H + 4) / _GYRO_SCALE,
        )

    def accel_magnitude(self) -> float:
        ax, ay, az = self.get_accel()
        return math.sqrt(ax**2 + ay**2 + az**2)

    def gyro_magnitude(self) -> float:
        gx, gy, gz = self.get_gyro()
        return math.sqrt(gx**2 + gy**2 + gz**2)

    # ── Crash detection ───────────────────────────────────────

    def is_crash_detected(self) -> bool:
        """
        Returns True only when BOTH accel AND gyro exceed thresholds
        within CRASH_CONFIRMATION_MS of each other.
        """
        accel = self.accel_magnitude()
        gyro  = self.gyro_magnitude()
        a_over = accel > ACCEL_CRASH_THRESHOLD
        g_over = gyro  > GYRO_CRASH_THRESHOLD
        now    = time.time()

        if a_over and g_over:
            print(f"[MPU6050] ⚡ CRASH  accel={accel:.2f}g  gyro={gyro:.1f}°/s")
            self._candidate_t = None
            return True

        if a_over or g_over:
            if self._candidate_t is None:
                self._candidate_t = now
            elif (now - self._candidate_t) * 1000 <= CRASH_CONFIRMATION_MS:
                # Second sensor tripped within window
                print(f"[MPU6050] ⚡ CRASH (seq)  accel={accel:.2f}g  gyro={gyro:.1f}°/s")
                self._candidate_t = None
                return True
            else:
                self._candidate_t = None   # window expired
        else:
            self._candidate_t = None

        return False

    def simulate_crash(self):
        """For testing — temporarily overrides readings with crash values."""
        print("[MPU6050] 🧪 SIMULATING CRASH")
        self._sim_crash = True

    def close(self):
        if not self._sim:
            try:
                self._bus.close()
            except Exception:
                pass
