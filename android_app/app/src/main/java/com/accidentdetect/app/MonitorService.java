package com.accidentdetect.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;

import com.google.firebase.database.DataSnapshot;
import com.google.firebase.database.DatabaseError;
import com.google.firebase.database.DatabaseReference;
import com.google.firebase.database.FirebaseDatabase;
import com.google.firebase.database.ValueEventListener;

/**
 * MonitorService: A foreground service that keeps the Firebase listener alive
 * even when the app is in the background or killed by Android.
 *
 * This ensures the user ALWAYS gets the emergency alert regardless of app state.
 */
public class MonitorService extends Service {

    private static final String TAG = "MonitorService";
    private static final String CHANNEL_ID = "accident_monitor_channel";
    private static final int NOTIFICATION_ID = 1001;
    private static final String USER_ID = "user_123";
    private static final String STATUS_PATH = "users/" + USER_ID + "/status";

    private DatabaseReference statusRef;
    private ValueEventListener statusListener;

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
        startForeground(NOTIFICATION_ID, buildForegroundNotification());
        startFirebaseMonitoring();
    }

    private void startFirebaseMonitoring() {
        statusRef = FirebaseDatabase.getInstance().getReference(STATUS_PATH);

        statusListener = new ValueEventListener() {
            @Override
            public void onDataChange(DataSnapshot snapshot) {
                String status = snapshot.getValue(String.class);
                Log.d(TAG, "[Service] Status changed: " + status);

                if ("ACCIDENT_PENDING".equals(status)) {
                    // Fire a high-priority full-screen notification
                    showEmergencyNotification();
                }
            }

            @Override
            public void onCancelled(DatabaseError error) {
                Log.e(TAG, "Firebase error in service: " + error.getMessage());
            }
        };

        statusRef.addValueEventListener(statusListener);
    }

    private void showEmergencyNotification() {
        NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);

        // Intent to open AlertActivity from the notification
        Intent alertIntent = new Intent(this, AlertActivity.class);
        alertIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);

        PendingIntent pendingIntent = PendingIntent.getActivity(
            this, 0, alertIntent,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        Notification notification = new NotificationCompat.Builder(this, "accident_alert_channel")
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle("🚨 ACCIDENT DETECTED!")
            .setContentText("Tap immediately — emergency contacts will be alerted in 10 seconds.")
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setFullScreenIntent(pendingIntent, true)
            .setAutoCancel(true)
            .build();

        if (nm != null) {
            nm.notify(2001, notification);
        }
    }

    private Notification buildForegroundNotification() {
        Intent openIntent = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(this, 0, openIntent,
            PendingIntent.FLAG_IMMUTABLE);

        return new NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_compass)
            .setContentTitle("Accident Monitor Active")
            .setContentText("Monitoring for crash events...")
            .setContentIntent(pi)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build();
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationManager nm = getSystemService(NotificationManager.class);

            // Foreground service channel (silent)
            NotificationChannel monitorChannel = new NotificationChannel(
                CHANNEL_ID,
                "Accident Monitor",
                NotificationManager.IMPORTANCE_LOW
            );
            monitorChannel.setDescription("Shows while crash monitoring is active");

            // Alert channel (loud, heads-up)
            NotificationChannel alertChannel = new NotificationChannel(
                "accident_alert_channel",
                "Emergency Alerts",
                NotificationManager.IMPORTANCE_HIGH
            );
            alertChannel.setDescription("Full-screen alert when accident is detected");
            alertChannel.enableVibration(true);
            alertChannel.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);

            if (nm != null) {
                nm.createNotificationChannel(monitorChannel);
                nm.createNotificationChannel(alertChannel);
            }
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY; // Auto-restart if killed
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        if (statusRef != null && statusListener != null) {
            statusRef.removeEventListener(statusListener);
        }
    }
}
