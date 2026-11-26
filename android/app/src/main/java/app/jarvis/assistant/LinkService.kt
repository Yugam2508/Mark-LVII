package app.jarvis.assistant

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder

/**
 * Keeps the link to your PC alive while the app isn't on screen, so Jarvis on the PC can ask this
 * phone to call, text or ring ("find my phone"). Shows one quiet notification, as Android requires.
 */
class LinkService : Service() {
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val nm = getSystemService(NotificationManager::class.java)
        nm?.createNotificationChannel(NotificationChannel("link", "Jarvis link", NotificationManager.IMPORTANCE_MIN))
        val note = Notification.Builder(this, "link")
            .setContentTitle("Jarvis is linked to your PC")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(1, note, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(1, note)
        }
        Hub.connect(this)
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        fun start(context: Context) {
            if (Prefs(context).paired) context.startForegroundService(Intent(context, LinkService::class.java))
        }
    }
}
