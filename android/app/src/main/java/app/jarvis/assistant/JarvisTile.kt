package app.jarvis.assistant

import android.app.PendingIntent
import android.content.Intent
import android.os.Build
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService

/**
 * A "Jarvis" tile in the pull-down Quick Settings: shows whether Jarvis is listening; tap to stop it, or to
 * open the app and start listening (Android only lets the microphone start from the app itself).
 */
class JarvisTile : TileService() {
    override fun onStartListening() { refresh() }

    override fun onClick() {
        if (LiveAudio.running) {
            Prefs(this).openMic = false
            LiveAudio.stop()
            refresh()
            return
        }
        Prefs(this).openMic = true
        val open = Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (Build.VERSION.SDK_INT >= 34) {
            startActivityAndCollapse(PendingIntent.getActivity(this, 3, open, PendingIntent.FLAG_IMMUTABLE))
        } else {
            @Suppress("DEPRECATION", "StartActivityAndCollapseDeprecated")
            startActivityAndCollapse(open)
        }
    }

    private fun refresh() {
        val t = qsTile ?: return
        val on = LiveAudio.running
        t.state = if (on) Tile.STATE_ACTIVE else Tile.STATE_INACTIVE
        t.label = "Jarvis"
        if (Build.VERSION.SDK_INT >= 29) t.subtitle = if (on) (if (LiveAudio.muted) "Muted" else "Listening") else "Off"
        t.updateTile()
    }
}
