"""
config.py — Loads all configuration from the .env file.
All other modules import from here; credentials stay out of source code.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (one level above pi_system/)
_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env")

def _get(key: str, default=None, cast=None):
    val = os.getenv(key, default)
    if val is None:
        return None
    return cast(val) if cast else val

# ── Firebase ─────────────────────────────────────────────────
FIREBASE_CREDENTIALS_PATH = _get("FIREBASE_CREDENTIALS", "pi_system/google-services.json")
FIREBASE_DATABASE_URL      = _get("FIREBASE_DATABASE_URL")
FIREBASE_USER_ID           = _get("USER_ID", "user_123")
FIREBASE_STATUS_PATH       = f"users/{FIREBASE_USER_ID}/status"

# FCM device token(s) for push notifications to the Android app
# Comma-separated list for multiple devices
_tokens_raw     = _get("DEVICE_TOKEN", "")
DEVICE_TOKENS   = [t.strip() for t in _tokens_raw.split(",") if t.strip()]

# ── Twilio ────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID   = _get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN    = _get("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER   = _get("TWILIO_PHONE_NUMBER")
EMERGENCY_TO_NUMBER  = _get("EMERGENCY_CONTACT")

# Parse multi-contact list (comma-separated)
_contacts_raw = _get("EMERGENCY_CONTACTS", "")
EMERGENCY_CONTACTS = [c.strip() for c in _contacts_raw.split(",") if c.strip()]
if not EMERGENCY_CONTACTS and EMERGENCY_TO_NUMBER:
    EMERGENCY_CONTACTS = [EMERGENCY_TO_NUMBER]

# ── Google Maps ───────────────────────────────────────────────
GOOGLE_MAPS_API_KEY = _get("GOOGLE_MAPS_API_KEY")

# ── ML Model ─────────────────────────────────────────────────
ML_MODEL_PATH = _get("ML_MODEL_PATH", "model/crash_model.pkl")
DATASET_PATH  = _get("DATASET_PATH",  "sensor_data.csv")

# ── Hardware ──────────────────────────────────────────────────
BUZZER_PIN       = 17
I2C_BUS          = 1
MPU6050_ADDRESS  = 0x68

# ── Crash Detection ───────────────────────────────────────────
ACCEL_CRASH_THRESHOLD  = _get("ACCELERATION_THRESHOLD", "22.0", float)
GYRO_CRASH_THRESHOLD   = 250.0   # °/s – rotation indicating flip/spin
CRASH_CONFIRMATION_MS  = 50      # Both must trigger within this window

# ── Timings ───────────────────────────────────────────────────
CONFIRMATION_WAIT_SECS = _get("CONFIRMATION_TIMEOUT", "10", int)
POLLING_INTERVAL_SECS  = _get("MONITORING_INTERVAL",  "0.02", float)
BUZZER_DURATION_SECS   = 30

# ── GPS Fallback ──────────────────────────────────────────────
DEFAULT_LATITUDE  = _get("DEFAULT_LATITUDE",  "19.863686532647435", float)
DEFAULT_LONGITUDE = _get("DEFAULT_LONGITUDE", "75.32118665626619",  float)

# ── Owner Info ────────────────────────────────────────────────
OWNER_NAME = "User"


def validate():
    """Call at startup to catch missing credentials early."""
    required = {
        "FIREBASE_DATABASE_URL": FIREBASE_DATABASE_URL,
        "TWILIO_ACCOUNT_SID":    TWILIO_ACCOUNT_SID,
        "TWILIO_AUTH_TOKEN":     TWILIO_AUTH_TOKEN,
        "TWILIO_FROM_NUMBER":    TWILIO_FROM_NUMBER,
        "EMERGENCY_CONTACT":     EMERGENCY_TO_NUMBER,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Check your .env file."
        )
    print("[Config] ✅ All credentials loaded")
