package com.accidentdetect.app;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.google.firebase.database.DataSnapshot;
import com.google.firebase.database.DatabaseError;
import com.google.firebase.database.DatabaseReference;
import com.google.firebase.database.FirebaseDatabase;
import com.google.firebase.database.ValueEventListener;

/**
 * MainActivity: Background monitor for the Firebase status path.
 * Watches users/user_123/status. If ACCIDENT_PENDING is received,
 * launches the full-screen AlertActivity.
 */
public class MainActivity extends AppCompatActivity {

    private static final String TAG = "AccidentDetect";
    private static final String USER_ID = "user_123";        // Change this to dynamic auth later
    private static final String STATUS_PATH = "users/" + USER_ID + "/status";

    private DatabaseReference statusRef;
    private ValueEventListener statusListener;
    private TextView tvStatus;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        tvStatus = findViewById(R.id.tvStatus);

        // Initialize Firebase reference for the status path
        statusRef = FirebaseDatabase.getInstance().getReference(STATUS_PATH);

        // Attach a live listener
        startMonitoring();
    }

    private void startMonitoring() {
        statusListener = new ValueEventListener() {
            @Override
            public void onDataChange(DataSnapshot snapshot) {
                String status = snapshot.getValue(String.class);
                Log.d(TAG, "Status changed: " + status);

                if (status == null) {
                    tvStatus.setText("Status: Monitoring...");
                    return;
                }

                tvStatus.setText("Status: " + status);

                switch (status) {
                    case "ACCIDENT_PENDING":
                        // Launch the full-screen alert activity
                        Intent intent = new Intent(MainActivity.this, AlertActivity.class);
                        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
                        startActivity(intent);
                        break;

                    case "DENIED":
                        tvStatus.setText("Status: ✅ You marked yourself SAFE");
                        break;

                    case "ALERT_SENT":
                        tvStatus.setText("Status: 🚨 Emergency Alert Sent!");
                        Toast.makeText(MainActivity.this, "Emergency contacts have been notified!", Toast.LENGTH_LONG).show();
                        break;

                    case "NORMAL":
                    default:
                        tvStatus.setText("Status: ✅ All Clear");
                        break;
                }
            }

            @Override
            public void onCancelled(DatabaseError error) {
                Log.e(TAG, "Firebase listener cancelled: " + error.getMessage());
                tvStatus.setText("⚠️ Connection Error");
            }
        };

        statusRef.addValueEventListener(statusListener);
        tvStatus.setText("Status: Monitoring...");
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        // Clean up the listener to avoid memory leaks
        if (statusRef != null && statusListener != null) {
            statusRef.removeEventListener(statusListener);
        }
    }
}
