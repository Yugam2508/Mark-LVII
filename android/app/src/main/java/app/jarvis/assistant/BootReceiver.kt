package app.jarvis.assistant

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Restores the link to the PC after the phone restarts. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) LinkService.start(context)
    }
}
