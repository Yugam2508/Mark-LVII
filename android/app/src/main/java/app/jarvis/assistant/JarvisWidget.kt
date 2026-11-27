package app.jarvis.assistant

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews

/**
 * The home-screen widget: what Jarvis is doing right now (listening, waiting for "Hey Jarvis", speaking, off),
 * and one tap to open it listening.
 */
class JarvisWidget : AppWidgetProvider() {
    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) = refresh(context)

    companion object {
        private var last = ""

        fun refresh(context: Context?) {
            val c = context?.applicationContext ?: return
            val state = when {
                !LiveAudio.running -> "Off — tap to talk"
                LiveAudio.muted -> "Muted"
                LiveAudio.state == LiveAudio.State.SPEAKING -> "Speaking…"
                LiveAudio.state == LiveAudio.State.CONNECTING -> "Connecting to your PC…"
                LiveAudio.wakeMode && LiveAudio.wakeAvailable && !LiveAudio.awake -> "Say “Hey Jarvis”"
                else -> "Listening"
            }
            if (state == last) return                     // only when something changed
            last = state
            val manager = AppWidgetManager.getInstance(c)
            val ids = manager.getAppWidgetIds(ComponentName(c, JarvisWidget::class.java))
            if (ids.isEmpty()) return
            val open = PendingIntent.getActivity(c, 9, Intent(c, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE)
            val views = RemoteViews(c.packageName, R.layout.jarvis_widget).apply {
                setTextViewText(R.id.widget_state, state)
                setOnClickPendingIntent(R.id.widget_root, open)
            }
            manager.updateAppWidget(ids, views)
        }
    }
}
