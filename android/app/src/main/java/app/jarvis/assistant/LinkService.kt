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
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP_LISTEN) {
            Prefs(this).openMic = false
            LiveAudio.stop()
        }
        val listen = (intent?.getBooleanExtra(EXTRA_LISTEN, false) == true && Prefs(this).openMic) ||
            (intent?.action == null && LiveAudio.running)
        val canMic = checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        startForegroundCompat(listen && canMic)
        Hub.connect(this)
        if (listen && canMic) LiveAudio.start(this)
        return START_STICKY
    }

    private fun startForegroundCompat(mic: Boolean) {
        getSystemService(NotificationManager::class.java)
            ?.createNotificationChannel(NotificationChannel("link", "Jarvis link", NotificationManager.IMPORTANCE_MIN))
        val stop = PendingIntent.getService(this, 1, Intent(this, LinkService::class.java).setAction(ACTION_STOP_LISTEN),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val b = Notification.Builder(this, "link")
            .setContentTitle(if (mic) "Jarvis is listening" else "Jarvis is linked to your PC")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setOngoing(true)
        if (mic) b.addAction(Notification.Action.Builder(null, "Stop listening", stop).build())
        val note = b.build()
        try {
            when {
                Build.VERSION.SDK_INT >= 34 -> startForeground(1, note, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE or
                    (if (mic) ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE else 0))
                Build.VERSION.SDK_INT >= 30 && mic -> startForeground(1, note, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
                else -> startForeground(1, note)
            }
        } catch (e: SecurityException) {
            // Android refused a microphone service (e.g. started from the background): stay linked, without the mic.
            if (Build.VERSION.SDK_INT >= 34) startForeground(1, note, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE) else startForeground(1, note)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        private const val ACTION_STOP_LISTEN = "app.jarvis.assistant.STOP_LISTEN"
        private const val EXTRA_LISTEN = "listen"

        /** Start (or update) the link; `listen` also opens the microphone. */
        fun start(context: Context, listen: Boolean = false) {
            if (!Prefs(context).paired) return
            context.startForegroundService(Intent(context, LinkService::class.java).putExtra(EXTRA_LISTEN, listen))
        }
    }
}
