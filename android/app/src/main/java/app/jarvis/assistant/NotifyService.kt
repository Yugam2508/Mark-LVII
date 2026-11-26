package app.jarvis.assistant

import android.app.Notification
import android.app.RemoteInput
import android.content.Context
import android.content.Intent
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import org.json.JSONArray
import org.json.JSONObject

/**
 * Lets Jarvis read the phone's notifications (WhatsApp, texts, anything) and answer the ones that have a
 * "Reply" button, the same way you would from the shade. It is switched on by the user in
 * Settings > Notifications > Device & app notifications. Notifications are kept only in memory (the latest
 * 60) and shown to the PC on request or when a message arrives; nothing is written to disk.
 */
class NotifyService : NotificationListenerService() {
    override fun onListenerConnected() { instance = this }
    override fun onListenerDisconnected() { if (instance === this) instance = null }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        if (sbn.packageName == packageName) return
        val n = sbn.notification
        if (n.flags and Notification.FLAG_ONGOING_EVENT != 0 || n.flags and Notification.FLAG_GROUP_SUMMARY != 0) return
        val extras = n.extras
        var title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
        var text = (extras.getCharSequence(Notification.EXTRA_BIG_TEXT) ?: extras.getCharSequence(Notification.EXTRA_TEXT))?.toString().orEmpty()
        // Chat apps (WhatsApp, Telegram, Messages) keep the conversation in MessagingStyle: the last
        // message there is the new one, where EXTRA_TEXT may only say "3 new messages".
        @Suppress("DEPRECATION")
        val msgs = extras.getParcelableArray(Notification.EXTRA_MESSAGES)
        val last = msgs?.lastOrNull() as? android.os.Bundle
        if (last != null) {
            val body = last.getCharSequence("text")?.toString().orEmpty()
            val sender = last.getCharSequence("sender")?.toString().orEmpty()
            val convo = extras.getCharSequence(Notification.EXTRA_CONVERSATION_TITLE)?.toString().orEmpty()
            if (body.isNotBlank()) {
                text = body
                title = when {
                    convo.isNotBlank() && sender.isNotBlank() -> "$sender in $convo"
                    sender.isNotBlank() -> sender
                    else -> title
                }
            }
        }
        if (title.isBlank() && text.isBlank()) return
        val reply = n.actions?.firstOrNull { a -> a.remoteInputs?.isNotEmpty() == true }
        val app = try {
            packageManager.getApplicationLabel(packageManager.getApplicationInfo(sbn.packageName, 0)).toString()
        } catch (e: Exception) { sbn.packageName }
        val entry = Entry(sbn.key, sbn.packageName, app, title.take(120), text.take(600), sbn.postTime, reply)
        synchronized(recent) {
            recent.removeAll { it.key == entry.key }
            recent.add(entry)
            while (recent.size > 60) recent.removeAt(0)
        }
        Hub.sendRaw(JSONObject().put("type", "notification").put("key", entry.key).put("pkg", entry.pkg)
            .put("app", entry.app).put("title", entry.title).put("text", entry.text)
            .put("can_reply", reply != null).toString())
    }

    class Entry(val key: String, val pkg: String, val app: String, val title: String, val text: String,
                val time: Long, val reply: Notification.Action?)

    companion object {
        @Volatile var instance: NotifyService? = null
        private val recent = ArrayList<Entry>()

        fun enabled(context: Context): Boolean =
            android.provider.Settings.Secure.getString(context.contentResolver, "enabled_notification_listeners")
                ?.contains(context.packageName) == true

        fun list(app: String, limit: Int): JSONArray {
            val out = JSONArray()
            val want = app.trim().lowercase()
            synchronized(recent) {
                for (e in recent.asReversed()) {
                    if (want.isNotEmpty() && !e.app.lowercase().contains(want) && !e.pkg.lowercase().contains(want)) continue
                    out.put(JSONObject().put("key", e.key).put("app", e.app).put("title", e.title).put("text", e.text)
                        .put("age_s", (System.currentTimeMillis() - e.time) / 1000).put("can_reply", e.reply != null))
                    if (out.length() >= limit) break
                }
            }
            return out
        }

        /** Find by key, or the newest from [from] (a name in the title) in [app]. */
        fun find(key: String, app: String, from: String): Entry? = synchronized(recent) {
            if (key.isNotBlank()) return recent.firstOrNull { it.key == key }
            recent.asReversed().firstOrNull {
                (app.isBlank() || it.app.lowercase().contains(app.lowercase())) &&
                    (from.isBlank() || it.title.lowercase().contains(from.lowercase()))
            }
        }

        fun reply(context: Context, e: Entry, text: String): Boolean {
            val action = e.reply ?: return false
            val input = action.remoteInputs?.firstOrNull() ?: return false
            val intent = Intent()
            val bundle = android.os.Bundle().also { it.putCharSequence(input.resultKey, text) }
            RemoteInput.addResultsToIntent(action.remoteInputs, intent, bundle)
            action.actionIntent.send(context, 0, intent)
            return true
        }

        fun dismiss(e: Entry): Boolean {
            val s = instance ?: return false
            s.cancelNotification(e.key)
            return true
        }
    }
}
