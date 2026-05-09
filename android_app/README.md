# Accident Detect — Android App

A companion Android app for the Raspberry Pi Accident Detection System.

## What It Does

| Feature | Description |
|---|---|
| 🔄 **Live Firebase Monitor** | Watches `users/user_123/status` in real time |
| 🚨 **Full-Screen Alert** | Launches over the lock screen with alarm sound when `ACCIDENT_PENDING` |
| ✅ **Deny Button** | Writes `"DENIED"` to Firebase, cancelling the emergency alert |
| ⏱️ **10-Second Countdown** | Auto-dismisses if user doesn't respond (alert already sent by Pi) |
| 🔁 **Background Service** | Foreground service keeps monitoring alive at all times |
| 📲 **Boot Auto-Start** | Restarts monitoring automatically after device reboot |

---

## Setup Instructions

### Step 1 — Firebase Project
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create a new project (or use your existing one)
3. Enable **Realtime Database** → Start in **Test Mode** initially
4. Go to Project Settings → **Add Android App**
   - Package name: `com.accidentdetect.app`
5. Download `google-services.json` and place it at:
   ```
   android_app/app/google-services.json
   ```

### Step 2 — Firebase Database Rules
In Firebase Console → Realtime Database → Rules, paste:
```json
{
  "rules": {
    "users": {
      "$uid": {
        ".read": "auth != null && auth.uid == $uid",
        ".write": "auth != null && auth.uid == $uid"
      }
    }
  }
}
```
> For testing, you can temporarily use `".read": true, ".write": true`

### Step 3 — Open in Android Studio
1. Open Android Studio
2. **File → Open** → Select the `android_app/` folder
3. Let Gradle sync complete
4. Connect your Android phone (enable USB debugging)
5. Press **Run ▶**

---

## Project File Structure

```
android_app/
├── app/
│   ├── src/main/
│   │   ├── java/com/accidentdetect/app/
│   │   │   ├── MainActivity.java       ← Firebase monitor screen
│   │   │   ├── AlertActivity.java      ← Full-screen emergency alert
│   │   │   ├── MonitorService.java     ← Background foreground service
│   │   │   └── BootReceiver.java       ← Auto-start on device boot
│   │   ├── res/
│   │   │   ├── layout/
│   │   │   │   ├── activity_main.xml   ← Main screen UI
│   │   │   │   └── activity_alert.xml  ← Red full-screen alert UI
│   │   │   ├── drawable/
│   │   │   │   ├── circle_green.xml    ← Live indicator
│   │   │   │   └── circle_red_outline.xml ← Countdown circle
│   │   │   └── values/
│   │   │       ├── strings.xml
│   │   │       └── themes.xml
│   │   └── AndroidManifest.xml
│   ├── build.gradle                    ← App dependencies
│   └── google-services.json           ← ⚠️ ADD THIS FILE (from Firebase Console)
├── build.gradle
└── settings.gradle
```

---

## Firebase Status Flow

```
Raspberry Pi                        Firebase                        Android App
    |                                   |                               |
    |── detect crash ──────────────────►|                               |
    |   write ACCIDENT_PENDING          |── onDataChange ──────────────►|
    |                                   |                               |── show AlertActivity
    |                                   |                               |── play alarm
    |                                   |                               |── start countdown
    |                                   |                               |
    |                              [User presses DENY]                  |
    |                                   |◄── write "DENIED" ───────────|
    |── reads DENIED ──────────────────►|                               |
    |   cancel SMS/call                 |                               |── stop alarm
    |   write NORMAL                    |                               |── finish activity
```

---

## ⚠️ Security Notice

- **Never hardcode API keys** (Twilio, Google Maps) in the Android app source code.
- Store them in Firebase Remote Config or a secure backend.
- Rotate (regenerate) any keys that were shared publicly in chats or commits.
- Enable Firebase Authentication before deploying to production.
