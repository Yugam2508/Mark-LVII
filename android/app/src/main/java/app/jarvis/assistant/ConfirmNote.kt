package app.jarvis.assistant

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * A confirmation waiting on the PC, as a phone notification with CONFIRM and CANCEL — so a text you asked
 * for from the phone can be approved from the lock screen, without the app open.
 */
object ConfirmNote {
    private const val ID = 77
    private const val CHANNEL = "confirm"

    fun update(context: Context?, card: Protocol.Event.Card) {
        val c = context ?: return
        val nm = c.getSystemService(NotificationManager::class.java) ?: return
        if (card.kind == "confirm_done") { nm.cancel(ID); return }
        nm.createNotificationChannel(NotificationChannel(CHANNEL, "Confirmations from your PC", NotificationManager.IMPORTANCE_HIGH))
        fun answer(ok: Boolean, code: Int) = PendingIntent.getBroadcast(c, code,
            Intent(c, ConfirmReceiver::class.java).putExtra("title", card.title).putExtra("ok", ok),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val n = Notification.Builder(c, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle("Jarvis needs your OK")
            .setContentText(card.title)
            .setStyle(Notification.BigTextStyle().bigText("${card.title}\n${card.text}"))
            .setAutoCancel(true)
            .addAction(Notification.Action.Builder(null, "CANCEL", answer(false, 81)).build())
            .addAction(Notification.Action.Builder(null, "CONFIRM", answer(true, 82)).build())
            .build()
        try { nm.notify(ID, n) } catch (e: SecurityException) { }
    }

    fun clear(context: Context) {
        context.getSystemService(NotificationManager::class.java)?.cancel(ID)
    }
}

class ConfirmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val title = intent.getStringExtra("title") ?: return
        Hub.sendRaw(Protocol.confirmBody(title, intent.getBooleanExtra("ok", false)))
        ConfirmNote.clear(context)
    }
}
