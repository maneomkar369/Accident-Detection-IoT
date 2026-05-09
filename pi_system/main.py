"""
main.py — Accident Detection System — Complete Pipeline

Detection flow:
  50Hz loop → MPU6050 threshold → ML model confirm
            → Firebase ACCIDENT_PENDING → Android 10s window
            ├─ DENIED    → cancel (user is safe)
            ├─ CONFIRMED → immediate alert (user requests help)
            └─ TIMEOUT   → auto alert (no response)

All three alert channels fire in parallel on CONFIRMED or TIMEOUT:
  📲 FCM Push Notification (with Maps link, opens on Android)
  💬 Twilio SMS            (with Google Maps URL)
  📞 Twilio Voice Call     (TTS location readout)
"""

import sys
import os
import time
import signal
import argparse
import threading
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root / "pi_system"))
os.chdir(_root)

from config import (
    validate,
    BUZZER_PIN, BUZZER_DURATION_SECS,
    POLLING_INTERVAL_SECS, CONFIRMATION_WAIT_SECS
)

try:
    import RPi.GPIO as GPIO
    _GPIO = True
except ImportError:
    _GPIO = False

from mpu6050_driver   import MPU6050Driver
from detector         import CrashDetector
from firebase_manager import FirebaseManager
from gps_manager      import GPSManager
from alert_manager    import AlertManager

_running = True


# ── GPIO helpers ──────────────────────────────────────────────

def _setup_gpio():
    if not _GPIO:
        return
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)

def _buzzer(state: bool):
    print(f"[Buzzer] {'ON 🔔' if state else 'OFF 🔕'}")
    if _GPIO:
        GPIO.output(BUZZER_PIN, GPIO.HIGH if state else GPIO.LOW)

def _buzzer_timed(secs):
    def _off():
        time.sleep(secs)
        _buzzer(False)
    threading.Thread(target=_off, daemon=True).start()


# ── Core crash handler ────────────────────────────────────────

def handle_crash(firebase: FirebaseManager,
                 gps:      GPSManager,
                 alert:    AlertManager):
    """
    Three-stage crash response.
    Stage A: Immediate hardware + Firebase push
    Stage B: Wait for Android — DENIED / CONFIRMED / TIMEOUT
    Stage C: Fire all 3 alert channels on CONFIRMED or TIMEOUT
    """
    print()
    print("═" * 60)
    print("  ⚡  CRASH CONFIRMED — EMERGENCY PROTOCOL STARTED  ⚡")
    print("═" * 60)

    # ── Stage A ───────────────────────────────────────────────
    _buzzer(True)
    _buzzer_timed(BUZZER_DURATION_SECS)

    # Push status → triggers Android AlertActivity
    firebase.set_status("ACCIDENT_PENDING")

    # Capture location immediately
    maps_url, lat, lon = gps.get_maps_url()
    print(f"[Main] 📍 {maps_url}")

    # Log to crash history
    firebase.log_crash(lat, lon, outcome="PENDING")

    # ── Stage B ───────────────────────────────────────────────
    print(f"[Main] ⏳ Waiting {CONFIRMATION_WAIT_SECS}s for Android response...")
    response = firebase.wait_for_response(timeout_secs=CONFIRMATION_WAIT_SECS)
    print(f"[Main] 📱 Android response: {response}")

    # ── Handle DENIED ─────────────────────────────────────────
    if response == "DENIED":
        print("[Main] ✅ User confirmed SAFE — cancelling alert")
        _buzzer(False)
        firebase.update_crash_outcome("DENIED")
        firebase.set_status("NORMAL")
        print("[Main] System reset to NORMAL\n")
        return

    # ── Stage C: CONFIRMED or TIMEOUT → fire all alerts ───────
    confirmed_by = "user" if response == "CONFIRMED" else "timeout"

    if response == "CONFIRMED":
        print("[Main] 🆘 User pressed SEND HELP — firing immediate alert!")
    else:
        print("[Main] ⏰ 10s timeout — no denial received — auto-alerting!")

    firebase.set_status("ALERT_SENT")
    firebase.update_crash_outcome(f"ALERT_SENT_{confirmed_by.upper()}")

    # Fire FCM + SMS + Voice Call in parallel
    alert_ok = alert.trigger_full_emergency(lat, lon, confirmed_by=confirmed_by)

    if not alert_ok:
        print("[Main] ❌ All alert channels failed — check credentials & network")

    # Brief pause so Android can update its UI from ALERT_SENT status
    time.sleep(5)
    firebase.set_status("NORMAL")
    print("[Main] ✅ System reset to NORMAL\n")


# ── Signal handler ────────────────────────────────────────────

def _on_sigint(sig, frame):
    global _running
    print("\n[Main] SIGINT — shutting down gracefully...")
    _running = False


# ── Entry point ───────────────────────────────────────────────

def main():
    global _running

    parser = argparse.ArgumentParser(description="Accident Detection System")
    parser.add_argument("--simulate", action="store_true",
                        help="Inject a fake crash in 5 seconds (for testing)")
    args = parser.parse_args()

    print("═" * 60)
    print("  Accident Detection System — v2.0")
    print("  Channels: FCM push + Twilio SMS + Twilio Voice Call")
    print("═" * 60)

    signal.signal(signal.SIGINT, _on_sigint)

    validate()
    _setup_gpio()

    print("[Main] Initialising subsystems...")
    sensor   = MPU6050Driver()
    ml       = CrashDetector()
    firebase = FirebaseManager()
    gps      = GPSManager()
    alert    = AlertManager()

    firebase.set_status("NORMAL")
    print(f"[Main] ✅ Monitoring at {1/POLLING_INTERVAL_SECS:.0f} Hz  "
          f"| threshold={22.0}g  | timeout={CONFIRMATION_WAIT_SECS}s\n")

    # Simulation: trigger crash after 5s for testing
    if args.simulate:
        print("[Main] 🧪 SIMULATION MODE — crash fires in 5 seconds\n")
        def _sim():
            time.sleep(5)
            print("[Main] 🧪 Injecting simulated crash...")
            handle_crash(firebase, gps, alert)
        threading.Thread(target=_sim, daemon=True).start()

    # ── 50 Hz polling loop ────────────────────────────────────
    in_event = False

    while _running:
        try:
            if not in_event and not args.simulate:
                ax, ay, az = sensor.get_accel()

                # Layer 1 — fast threshold gate
                if sensor.is_crash_detected():
                    # Layer 2 — ML model confirmation
                    if ml.predict(ax, ay, az):
                        in_event = True
                        handle_crash(firebase, gps, alert)
                        in_event = False
                        time.sleep(5)   # cooldown after event

            time.sleep(POLLING_INTERVAL_SECS)

        except Exception as e:
            print(f"[Main] ⚠️  Error: {e}")
            time.sleep(1)

    # ── Cleanup ───────────────────────────────────────────────
    sensor.close()
    _buzzer(False)
    if _GPIO:
        GPIO.cleanup()
    firebase.set_status("OFFLINE")
    print("[Main] ✅ Shutdown complete")


if __name__ == "__main__":
    main()
