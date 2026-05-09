"""
firebase_manager.py — Realtime Database + FCM status coordination.

Status values used across the system:
  NORMAL            → idle, all clear
  ACCIDENT_PENDING  → crash detected, waiting for Android response
  DENIED            → user pressed "I AM OKAY" → cancel alert
  CONFIRMED         → user pressed "SEND HELP NOW" → trigger immediately
  ALERT_SENT        → emergency dispatched
  OFFLINE           → Pi shutting down
"""

import firebase_admin
from firebase_admin import credentials, db
import datetime
import threading
from pathlib import Path
from config import (
    FIREBASE_CREDENTIALS_PATH, FIREBASE_DATABASE_URL,
    FIREBASE_STATUS_PATH, FIREBASE_USER_ID
)

_root = Path(__file__).resolve().parent.parent

# Status values the Android app can write back
DENIED_STATUS    = "DENIED"
CONFIRMED_STATUS = "CONFIRMED"   # user pressed SEND HELP NOW


class FirebaseManager:

    def __init__(self):
        self._response_event  = threading.Event()
        self._response_value  = None   # stores "DENIED" or "CONFIRMED"
        self._listener        = None
        self._connect()

    def _connect(self):
        cred_path = _root / FIREBASE_CREDENTIALS_PATH
        try:
            cred = credentials.Certificate(str(cred_path))
        except Exception:
            cred = credentials.ApplicationDefault()

        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DATABASE_URL})

        self._status_ref = db.reference(FIREBASE_STATUS_PATH)
        print("[Firebase] ✅ Connected →", FIREBASE_DATABASE_URL)

    # ── Status ────────────────────────────────────────────────

    def set_status(self, status: str):
        try:
            self._status_ref.set(status)
            print(f"[Firebase] Status → {status}")
        except Exception as e:
            print(f"[Firebase] ❌ set_status: {e}")

    def get_status(self) -> str:
        try:
            return self._status_ref.get() or "UNKNOWN"
        except Exception as e:
            print(f"[Firebase] ❌ get_status: {e}")
            return "UNKNOWN"

    # ── Android response listener ─────────────────────────────

    def _on_change(self, event):
        """Called on every Firebase status change during the wait window."""
        val = event.data
        print(f"[Firebase] 📡 Android response: {val}")
        if val in (DENIED_STATUS, CONFIRMED_STATUS):
            self._response_value = val
            self._response_event.set()

    def wait_for_response(self, timeout_secs: int) -> str:
        """
        Blocks for up to timeout_secs, waiting for the Android app to write
        either "DENIED" or "CONFIRMED" to the status path.

        Returns:
          "DENIED"    → user pressed I AM OKAY
          "CONFIRMED" → user pressed SEND HELP NOW
          "TIMEOUT"   → no response within the window
        """
        self._response_event.clear()
        self._response_value  = None
        self._listener = self._status_ref.listen(self._on_change)

        triggered = self._response_event.wait(timeout=timeout_secs)

        if self._listener:
            self._listener.close()
            self._listener = None

        if triggered and self._response_value:
            return self._response_value
        return "TIMEOUT"

    # ── Crash history ─────────────────────────────────────────

    def log_crash(self, lat: float, lon: float,
                  accel: float = 0, gyro: float = 0,
                  outcome: str = "PENDING"):
        try:
            db.reference(f"users/{FIREBASE_USER_ID}/crash_history").push({
                "timestamp":  datetime.datetime.utcnow().isoformat() + "Z",
                "latitude":   lat,
                "longitude":  lon,
                "accel_g":    round(accel, 3),
                "gyro_dps":   round(gyro, 1),
                "outcome":    outcome,
                "maps_url":   f"https://www.google.com/maps?q={lat},{lon}"
            })
            print(f"[Firebase] Crash logged  outcome={outcome}")
        except Exception as e:
            print(f"[Firebase] ❌ log_crash: {e}")

    def update_crash_outcome(self, outcome: str):
        """Updates the most recent crash history entry's outcome."""
        try:
            hist_ref = db.reference(f"users/{FIREBASE_USER_ID}/crash_history")
            entries  = hist_ref.order_by_key().limit_to_last(1).get()
            if entries:
                key = list(entries.keys())[0]
                hist_ref.child(key).update({"outcome": outcome})
                print(f"[Firebase] Crash outcome updated → {outcome}")
        except Exception as e:
            print(f"[Firebase] ❌ update_crash_outcome: {e}")

    def reset(self):
        self.set_status("NORMAL")
