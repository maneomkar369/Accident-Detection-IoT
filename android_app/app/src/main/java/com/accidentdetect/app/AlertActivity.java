package com.accidentdetect.app;

import android.content.Intent;
import android.media.AudioAttributes;
import android.media.MediaPlayer;
import android.media.RingtoneManager;
import android.net.Uri;
import android.os.Bundle;
import android.os.CountDownTimer;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;
import android.util.Log;

import androidx.appcompat.app.AppCompatActivity;

import com.google.firebase.database.DataSnapshot;
import com.google.firebase.database.DatabaseError;
import com.google.firebase.database.DatabaseReference;
import com.google.firebase.database.FirebaseDatabase;
import com.google.firebase.database.ValueEventListener;

/**
 * AlertActivity — Full-screen emergency alert with THREE outcomes:
 *
 *  ✅ DENY     → User presses "I AM OKAY"     → writes "DENIED"    → cancel
 *  🆘 CONFIRM  → User presses "SEND HELP NOW" → writes "CONFIRMED" → immediate alert
 *  ⏰ TIMEOUT  → 10s expires with no action   → Pi sends auto-alert
 *
 * After CONFIRMED or TIMEOUT the Pi fires:
 *   📲 FCM push notification (with Maps deep-link)
 *   💬 Twilio SMS            (with Google Maps URL)
 *   📞 Twilio Voice Call     (TTS location readout)
 */
public class AlertActivity extends AppCompatActivity {

    private static final String TAG        = "AlertActivity";
    private static final String STATUS_PATH = "users/user_123/status";
    private static final int COUNTDOWN     = 10;

    private DatabaseReference statusRef;
    private MediaPlayer       alarmPlayer;
    private CountDownTimer    timer;
    private ValueEventListener statusListener;

    private TextView tvCountdown;
    private TextView tvLocation;
    private Button   denyButton;
    private Button   confirmButton;

    // Location passed from the notification data payload
    private double lat = 0, lon = 0;
    private String mapsUrl = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Show over lock screen, keep screen on
        getWindow().addFlags(
            WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON      |
            WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD    |
            WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED    |
            WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
        );
        setContentView(R.layout.activity_alert);

        tvCountdown   = findViewById(R.id.tvCountdown);
        tvLocation    = findViewById(R.id.tvLocation);
        denyButton    = findViewById(R.id.denyButton);
        confirmButton = findViewById(R.id.confirmButton);

        // Extract location from FCM notification data payload (if launched via notification)
        Intent intent = getIntent();
        if (intent != null) {
            String latStr    = intent.getStringExtra("lat");
            String lonStr    = intent.getStringExtra("lon");
            String mapsExtra = intent.getStringExtra("maps_url");
            if (latStr != null && lonStr != null) {
                try {
                    lat     = Double.parseDouble(latStr);
                    lon     = Double.parseDouble(lonStr);
                    mapsUrl = (mapsExtra != null) ? mapsExtra
                              : "https://www.google.com/maps?q=" + lat + "," + lon;
                    tvLocation.setText(String.format("%.5f, %.5f", lat, lon));
                } catch (NumberFormatException ignored) {}
            }
        }

        statusRef = FirebaseDatabase.getInstance().getReference(STATUS_PATH);

        playAlarm();
        startCountdown();
        attachStatusListener();

        // ── DENY: I AM OKAY ──────────────────────────────────
        denyButton.setOnClickListener(v -> {
            disableButtons();
            statusRef.setValue("DENIED")
                .addOnSuccessListener(aVoid -> {
                    Toast.makeText(this, "✅ You're marked SAFE. No alert sent.",
                                   Toast.LENGTH_LONG).show();
                    stopAndFinish();
                })
                .addOnFailureListener(e -> {
                    Toast.makeText(this, "⚠️ Failed — check internet.", Toast.LENGTH_SHORT).show();
                    enableButtons();
                });
        });

        // ── CONFIRM: SEND HELP NOW ────────────────────────────
        confirmButton.setOnClickListener(v -> {
            disableButtons();
            confirmButton.setText("🆘 Sending help...");
            statusRef.setValue("CONFIRMED")
                .addOnSuccessListener(aVoid -> {
                    Toast.makeText(this,
                        "🆘 Help is on the way! Emergency contacts being notified.",
                        Toast.LENGTH_LONG).show();
                    // Open Maps for the user to see their own location
                    if (!mapsUrl.isEmpty()) {
                        openMaps();
                    }
                    stopAndFinish();
                })
                .addOnFailureListener(e -> {
                    Toast.makeText(this, "⚠️ Failed — check internet.", Toast.LENGTH_SHORT).show();
                    enableButtons();
                });
        });
    }

    /** Open Google Maps at the crash location. */
    private void openMaps() {
        try {
            Intent mapIntent = new Intent(Intent.ACTION_VIEW,
                Uri.parse("geo:" + lat + "," + lon + "?q=" + lat + "," + lon + "(Accident Location)"));
            mapIntent.setPackage("com.google.android.apps.maps");
            if (mapIntent.resolveActivity(getPackageManager()) != null) {
                startActivity(mapIntent);
            } else {
                // Fallback to browser
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(mapsUrl)));
            }
        } catch (Exception e) {
            Log.e(TAG, "Failed to open Maps: " + e.getMessage());
        }
    }

    /** Listen for status changes so we dismiss if the Pi already resolved things. */
    private void attachStatusListener() {
        statusListener = new ValueEventListener() {
            @Override public void onDataChange(DataSnapshot snapshot) {
                String status = snapshot.getValue(String.class);
                Log.d(TAG, "Status from DB: " + status);
                if ("ALERT_SENT".equals(status)) {
                    Toast.makeText(AlertActivity.this,
                        "🚨 Emergency alert was auto-sent!", Toast.LENGTH_LONG).show();
                    if (!mapsUrl.isEmpty()) openMaps();
                    stopAndFinish();
                } else if ("NORMAL".equals(status)) {
                    stopAndFinish();
                }
            }
            @Override public void onCancelled(DatabaseError error) {
                Log.e(TAG, "Firebase error: " + error.getMessage());
            }
        };
        statusRef.addValueEventListener(statusListener);
    }

    private void startCountdown() {
        timer = new CountDownTimer(COUNTDOWN * 1000L, 1000) {
            @Override public void onTick(long ms) {
                long s = ms / 1000;
                tvCountdown.setText(String.valueOf(s));
                if (s <= 3) {
                    tvCountdown.setTextColor(
                        getResources().getColor(android.R.color.holo_orange_light, null));
                }
            }
            @Override public void onFinish() {
                tvCountdown.setText("0");
                // Timeout — Pi handles the alert automatically. Just dismiss.
                Toast.makeText(AlertActivity.this,
                    "⏰ Time's up — auto-alert sent by device.", Toast.LENGTH_LONG).show();
                stopAndFinish();
            }
        }.start();
    }

    private void playAlarm() {
        try {
            Uri uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM);
            if (uri == null) uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE);
            alarmPlayer = new MediaPlayer();
            alarmPlayer.setAudioAttributes(new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ALARM)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build());
            alarmPlayer.setDataSource(this, uri);
            alarmPlayer.setLooping(true);
            alarmPlayer.prepare();
            alarmPlayer.start();
        } catch (Exception e) {
            Log.e(TAG, "Alarm error: " + e.getMessage());
        }
    }

    private void stopAndFinish() {
        if (timer != null)       { timer.cancel(); }
        if (alarmPlayer != null) { alarmPlayer.stop(); alarmPlayer.release(); alarmPlayer = null; }
        finish();
    }

    private void disableButtons() {
        denyButton.setEnabled(false);
        confirmButton.setEnabled(false);
    }

    private void enableButtons() {
        denyButton.setEnabled(true);
        confirmButton.setEnabled(true);
        confirmButton.setText("🆘  SEND HELP NOW");
    }

    @Override protected void onDestroy() {
        super.onDestroy();
        if (statusRef != null && statusListener != null)
            statusRef.removeEventListener(statusListener);
        if (alarmPlayer != null) alarmPlayer.release();
        if (timer != null) timer.cancel();
    }
}
