package app.jarvis.assistant

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder

/**
 * Keeps Jarvis reachable and listening while the app isn't on screen: the link to your PC (so it can ask
 * this phone to call, text or ring) and, when listening is on, the open microphone and speaker. Shows one
 * quiet notification, as Android requires, with a button to stop listening.
 */
class LinkService : Service() {
    // Tell the PC when the phone's battery runs low (Jarvis says it, or shows a card if you're busy).
    private val batteryLow = object : android.content.BroadcastReceiver() {
        override fun onReceive(c: Context, i: Intent) {
            val b = c.registerReceiver(null, android.content.IntentFilter(Intent.ACTION_BATTERY_CHANGED))
            val level = b?.getIntExtra(android.os.BatteryManager.EXTRA_LEVEL, -1) ?: -1
            val scale = b?.getIntExtra(android.os.BatteryManager.EXTRA_SCALE, 100) ?: 100
            val pct = if (level >= 0) level * 100 / scale else -1
            Hub.sendRaw(org.json.JSONObject().put("type", "phone_event").put("event", "battery_low")
                .put("level", pct).toString(), queue = true)
        }
    }
    private var watching = false

    override fun onCreate() {
        super.onCreate()
        try {
            registerReceiver(batteryLow, android.content.IntentFilter(Intent.ACTION_BATTERY_LOW))
            watching = true
        } catch (e: Exception) { }
    }

    override fun onDestroy() {
        if (watching) try { unregisterReceiver(batteryLow) } catch (e: Exception) { }
        super.onDestroy()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP_LISTEN) {
            Prefs(this).openMic = false
            LiveAudio.stop()
        }
        if (intent?.action == ACTION_MUTE) {
            LiveAudio.muted = !LiveAudio.muted
        }
        // Whether the microphone stays part of this service. Mute keeps it (the mic is only paused);
        // only "Stop listening" drops it.
        val listen = when (intent?.action) {
            ACTION_STOP_LISTEN -> false
            ACTION_MUTE -> LiveAudio.running
            else -> (intent?.getBooleanExtra(EXTRA_LISTEN, false) == true && Prefs(this).openMic) || LiveAudio.running
        }
        val canMic = checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        val micOn = startForegroundCompat(listen && canMic)
        Hub.connect(this)
        if (micOn) LiveAudio.start(this)
        return START_STICKY
    }

    /** Runs as a foreground service; true when it could include the microphone. */
    private fun startForegroundCompat(mic: Boolean): Boolean {
        getSystemService(NotificationManager::class.java)
            ?.createNotificationChannel(NotificationChannel("link", "Jarvis link", NotificationManager.IMPORTANCE_MIN))
        val stop = PendingIntent.getService(this, 1, Intent(this, LinkService::class.java).setAction(ACTION_STOP_LISTEN),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val mute = PendingIntent.getService(this, 2, Intent(this, LinkService::class.java).setAction(ACTION_MUTE),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val open = PendingIntent.getActivity(this, 4, Intent(this, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP), PendingIntent.FLAG_IMMUTABLE)
        val waiting = mic && Prefs(this).wakeWord
        val b = Notification.Builder(this, "link")
            .setContentTitle(when {
                !mic -> "Jarvis is linked to your PC"
                LiveAudio.muted -> "Jarvis is muted"
                waiting -> "Jarvis — say “Hey Jarvis”"
                else -> "Jarvis is listening"
            })
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentIntent(open)
            .setOngoing(true)
        if (mic) {
            b.addAction(Notification.Action.Builder(null, if (LiveAudio.muted) "Unmute" else "Mute", mute).build())
            b.addAction(Notification.Action.Builder(null, "Stop listening", stop).build())
        }
        val note = b.build()
        try {
            when {
                Build.VERSION.SDK_INT >= 34 -> startForeground(1, note, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE or
                    (if (mic) ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE else 0))
                Build.VERSION.SDK_INT >= 30 && mic -> startForeground(1, note, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
                else -> startForeground(1, note)
            }
            return mic
        } catch (e: Exception) {
            // Android refused a microphone service (started from the background, or after a reboot):
            // stay linked without the mic; opening the app turns listening back on.
            return try {
                val linkOnly = Notification.Builder(this, "link").setContentTitle("Jarvis is linked to your PC")
                    .setContentText("Open Jarvis to start listening").setSmallIcon(android.R.drawable.ic_dialog_info)
                    .setOngoing(true).build()
                if (Build.VERSION.SDK_INT >= 34) startForeground(1, linkOnly, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
                else startForeground(1, linkOnly)
                false
            } catch (e2: Exception) {
                stopSelf()
                false
            }
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        private const val ACTION_STOP_LISTEN = "app.jarvis.assistant.STOP_LISTEN"
        private const val ACTION_MUTE = "app.jarvis.assistant.MUTE"
        private const val EXTRA_LISTEN = "listen"

        /** Start (or update) the link; `listen` also opens the microphone. */
        fun start(context: Context, listen: Boolean = false) {
            if (!Prefs(context).paired) return
            context.startForegroundService(Intent(context, LinkService::class.java).putExtra(EXTRA_LISTEN, listen))
        }
    }
}
