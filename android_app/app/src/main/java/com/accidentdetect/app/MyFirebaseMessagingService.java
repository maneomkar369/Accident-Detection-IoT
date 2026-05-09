package com.accidentdetect.app;

import android.app.Notification;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

import androidx.core.app.NotificationCompat;

import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

import java.util.Map;

/**
 * MyFirebaseMessagingService
 *
 * Handles FCM messages sent by the Pi's alert_manager.py AFTER confirmation.
 * The notification payload contains: lat, lon, maps_url, status, confirmed_by.
 *
 * When received:
 *   - Launches AlertActivity (or a post-alert MapsActivity) with the location data
 *   - Shows a persistent heads-up notification with a "VIEW MAP" button
 */
public class MyFirebaseMessagingService extends FirebaseMessagingService {

    private static final String TAG     = "FCMService";
    private static final int    NOTIF_ID = 3001;

    @Override
    public void onMessageReceived(RemoteMessage remoteMessage) {
        Log.d(TAG, "FCM message from: " + remoteMessage.getFrom());

        Map<String, String> data = remoteMessage.getData();
        String status      = data.getOrDefault("status",      "");
        String lat         = data.getOrDefault("lat",         "0");
        String lon         = data.getOrDefault("lon",         "0");
        String mapsUrl     = data.getOrDefault("maps_url",    "");
        String confirmedBy = data.getOrDefault("confirmed_by","timeout");
        String timeStr     = data.getOrDefault("time",        "");

        Log.d(TAG, "Status=" + status + " | lat=" + lat + " | lon=" + lon
                + " | by=" + confirmedBy);

        if ("ALERT_SENT".equals(status)) {
            showEmergencyNotification(lat, lon, mapsUrl, confirmedBy, timeStr);
        }
    }

    private void showEmergencyNotification(String lat, String lon,
                                            String mapsUrl, String confirmedBy,
                                            String timeStr) {
        NotificationManager nm =
            (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);

        // ── Intent 1: Open AlertActivity with location data ──────
        Intent alertIntent = new Intent(this, AlertActivity.class);
        alertIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        alertIntent.putExtra("lat",      lat);
        alertIntent.putExtra("lon",      lon);
        alertIntent.putExtra("maps_url", mapsUrl);
        PendingIntent alertPi = PendingIntent.getActivity(this, 0, alertIntent,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        // ── Intent 2: Open Google Maps directly ──────────────────
        android.net.Uri mapsUri = android.net.Uri.parse(
            mapsUrl.isEmpty()
                ? "https://www.google.com/maps?q=" + lat + "," + lon
                : mapsUrl
        );
        Intent mapsIntent = new Intent(Intent.ACTION_VIEW, mapsUri);
        mapsIntent.setPackage("com.google.android.apps.maps");
        PendingIntent mapsPi = PendingIntent.getActivity(this, 1, mapsIntent,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        // ── Build the notification ────────────────────────────────
        String triggerLabel = "user".equals(confirmedBy)
            ? "You requested help" : "Auto-sent (timeout)";

        String bodyText = triggerLabel + ".\n"
            + "📍 Location: " + lat + ", " + lon
            + (timeStr.isEmpty() ? "" : "\n🕐 " + timeStr);

        Notification notification = new NotificationCompat.Builder(this, "accident_alert_channel")
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle("🚨 Emergency Alert Sent!")
            .setContentText(triggerLabel + " — Tap to view location")
            .setStyle(new NotificationCompat.BigTextStyle().bigText(bodyText))
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setColor(0xB71C1C)
            .setAutoCancel(true)
            .setContentIntent(alertPi)
            .addAction(
                android.R.drawable.ic_menu_mapmode,
                "📍 VIEW MAP",
                mapsPi
            )
            .build();

        if (nm != null) {
            nm.notify(NOTIF_ID, notification);
        }
    }

    /** Called when a new FCM registration token is generated. Log it to update .env DEVICE_TOKEN. */
    @Override
    public void onNewToken(String token) {
        Log.d(TAG, "New FCM Token: " + token);
        // TODO: Send this token to your backend or Firebase so the Pi always
        // has the latest token. For now, copy it from logcat and update .env DEVICE_TOKEN=
    }
}
