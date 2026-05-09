"""
alert_manager.py — Full emergency alert pipeline triggered after confirmation.

Sends THREE simultaneous alerts:
  1. 📲 FCM Push Notification  → Android phone (with geo link, opens Maps)
  2. 💬 Twilio SMS             → Emergency contacts (Google Maps URL)
  3. 📞 Twilio Voice Call      → Emergency contacts (TTS location message)
"""

import datetime
import concurrent.futures
from twilio.rest import Client
from firebase_admin import messaging
from config import (
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
    TWILIO_FROM_NUMBER, EMERGENCY_CONTACTS,
    OWNER_NAME, DEVICE_TOKENS
)


class AlertManager:

    def __init__(self):
        self._twilio = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        print(f"[Alert] ✅ Twilio ready  | contacts : {EMERGENCY_CONTACTS}")
        print(f"[Alert] ✅ FCM ready     | devices  : {len(DEVICE_TOKENS)} token(s)")

    # ── Helpers ───────────────────────────────────────────────

    def _maps_url(self, lat: float, lon: float) -> str:
        return f"https://www.google.com/maps?q={lat},{lon}"

    def _now_str(self) -> str:
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── 1. FCM Push Notification ──────────────────────────────

    def send_fcm_notification(self, lat: float, lon: float,
                               confirmed_by: str = "timeout") -> bool:
        """
        Sends a high-priority FCM push notification to the Android app.
        The notification includes:
          - Clickable Maps deep-link in the data payload
          - 'confirmed_by': 'user' (CONFIRM button) or 'timeout' (10s expired)
        """
        if not DEVICE_TOKENS:
            print("[Alert] ⚠️  No FCM tokens configured — skipping push notification")
            return False

        maps_url = self._maps_url(lat, lon)
        title    = "🚨 EMERGENCY ALERT SENT"
        body     = (
            f"{OWNER_NAME}'s accident alert was confirmed.\n"
            f"Emergency contacts have been notified.\n"
            f"📍 Tap to view location on Maps."
        )

        success = False
        for token in DEVICE_TOKENS:
            try:
                msg = messaging.Message(
                    notification=messaging.Notification(
                        title=title,
                        body=body,
                    ),
                    data={
                        "lat":          str(round(lat, 6)),
                        "lon":          str(round(lon, 6)),
                        "maps_url":     maps_url,
                        "status":       "ALERT_SENT",
                        "confirmed_by": confirmed_by,
                        "time":         self._now_str(),
                        "click_action": "OPEN_MAPS",
                    },
                    android=messaging.AndroidConfig(
                        priority="high",
                        notification=messaging.AndroidNotification(
                            sound="default",
                            priority="max",
                            channel_id="accident_alert_channel",
                            color="#B71C1C",
                        ),
                    ),
                    token=token,
                )
                response = messaging.send(msg)
                print(f"[Alert] ✅ FCM push → device  (msg_id: {response})")
                success = True
            except Exception as e:
                print(f"[Alert] ❌ FCM push failed: {e}")
        return success

    # ── 2. Twilio SMS ─────────────────────────────────────────

    def send_sms(self, lat: float, lon: float,
                 confirmed_by: str = "timeout") -> bool:
        maps_url = self._maps_url(lat, lon)
        trigger  = "confirmed by user" if confirmed_by == "user" else "auto (10s timeout)"
        body = (
            f"🚨 ACCIDENT ALERT 🚨\n"
            f"{OWNER_NAME} has been in an accident ({trigger}).\n"
            f"Time: {self._now_str()}\n"
            f"📍 Location: {maps_url}\n"
            f"Please check on them immediately."
        )
        success = False
        for number in EMERGENCY_CONTACTS:
            try:
                msg = self._twilio.messages.create(
                    body=body, from_=TWILIO_FROM_NUMBER, to=number
                )
                print(f"[Alert] ✅ SMS  → {number}  (SID: {msg.sid})")
                success = True
            except Exception as e:
                print(f"[Alert] ❌ SMS  → {number}  failed: {e}")
        return success

    # ── 3. Twilio Voice Call ──────────────────────────────────

    def make_call(self, lat: float, lon: float,
                  confirmed_by: str = "timeout") -> bool:
        trigger  = "confirmed by the user" if confirmed_by == "user" \
                   else "automatically after a 10-second timeout"
        maps_url = self._maps_url(lat, lon)

        twiml = (
            "<Response>"
            f"<Say voice='alice' language='en-IN'>"
            f"Emergency alert. {OWNER_NAME} has been in an accident, "
            f"{trigger}. "
            f"Their last known location is latitude {lat:.4f}, longitude {lon:.4f}. "
            f"A Google Maps link has also been sent by S M S. "
            f"Please check on them immediately."
            f"</Say>"
            "<Pause length='1'/>"
            f"<Say voice='alice' language='en-IN'>"
            f"Repeating. {OWNER_NAME} has been in an accident. "
            f"Check your S M S for the location link."
            f"</Say>"
            "</Response>"
        )
        success = False
        for number in EMERGENCY_CONTACTS:
            try:
                call = self._twilio.calls.create(
                    twiml=twiml, from_=TWILIO_FROM_NUMBER, to=number
                )
                print(f"[Alert] ✅ Call → {number}  (SID: {call.sid})")
                success = True
            except Exception as e:
                print(f"[Alert] ❌ Call → {number}  failed: {e}")
        return success

    # ── Master trigger ────────────────────────────────────────

    def trigger_full_emergency(self, lat: float, lon: float,
                                confirmed_by: str = "timeout") -> bool:
        """
        Fires ALL three alerts in parallel for minimum latency:
          FCM push notification  (to Android app)
          Twilio SMS             (to emergency contacts)
          Twilio Voice Call      (to emergency contacts)

        confirmed_by: 'user'    → Android CONFIRM button pressed
                      'timeout' → 10-second window expired with no DENIED
        """
        trigger_label = "USER CONFIRMED" if confirmed_by == "user" else "TIMEOUT"
        print(f"\n[Alert] 🚨 FULL EMERGENCY — trigger={trigger_label}")
        print(f"[Alert]    Contacts : {EMERGENCY_CONTACTS}")
        print(f"[Alert]    Location : {self._maps_url(lat, lon)}\n")

        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            f_fcm  = pool.submit(self.send_fcm_notification, lat, lon, confirmed_by)
            f_sms  = pool.submit(self.send_sms,              lat, lon, confirmed_by)
            f_call = pool.submit(self.make_call,             lat, lon, confirmed_by)

            results["fcm"]  = f_fcm.result()
            results["sms"]  = f_sms.result()
            results["call"] = f_call.result()

        ok = any(results.values())
        print(f"\n[Alert] Result → FCM={results['fcm']} | "
              f"SMS={results['sms']} | Call={results['call']}")
        print(f"[Alert] {'✅ Emergency delivered' if ok else '❌ ALL channels failed'}")
        return ok
