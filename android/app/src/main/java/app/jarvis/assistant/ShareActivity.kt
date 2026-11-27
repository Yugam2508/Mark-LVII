package app.jarvis.assistant

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import org.json.JSONObject

/**
 * "Share → Jarvis" from any app: the text or link goes to your PC, where Jarvis puts it on the clipboard and
 * opens links in the browser, so you can carry on there. Nothing is shown here but a short note.
 */
class ShareActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val text = when (intent?.action) {
            Intent.ACTION_SEND -> listOfNotNull(intent.getStringExtra(Intent.EXTRA_SUBJECT), intent.getStringExtra(Intent.EXTRA_TEXT))
                .filter { it.isNotBlank() }.distinct().joinToString("\n")
            else -> ""
        }
        if (text.isBlank()) {
            Toast.makeText(this, "Nothing to send: Jarvis can pass on text and links", Toast.LENGTH_SHORT).show()
        } else if (!Prefs(this).paired) {
            Toast.makeText(this, "Open Jarvis and connect to your PC first", Toast.LENGTH_LONG).show()
        } else {
            val sent = Hub.sendRaw(JSONObject().put("type", "share").put("text", text.take(20000)).toString(), queue = true)
            if (!sent) { Hub.connect(this); LinkService.start(this) }
            Toast.makeText(this, if (sent) "Sent to your PC" else "Sending when your PC is reachable", Toast.LENGTH_SHORT).show()
        }
        finish()
    }
}
