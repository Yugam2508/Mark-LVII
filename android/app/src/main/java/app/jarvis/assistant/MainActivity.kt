package app.jarvis.assistant

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.view.Menu
import android.view.MenuItem
import android.widget.FrameLayout

/**
 * The app's own screen. Also answers the system's ASSIST intent, so it opens from
 * "long-press power" even before it is chosen as the default assistant.
 */
class MainActivity : Activity() {
    private val root by lazy { FrameLayout(this) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(root)
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 1)
        }
        show()
    }

    private fun show() {
        root.removeAllViews()
        if (Prefs(this).paired) {
            root.addView(ConversationPanel(this, listenOnShow = intent?.action == Intent.ACTION_ASSIST))
        } else {
            root.addView(PairPanel(this) { show() })
        }
        window.statusBarColor = android.graphics.Color.rgb(2, 8, 12)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        show()
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menu.add(0, 1, 0, "Make Jarvis my assistant")
        menu.add(0, 2, 0, "Speak replies on/off")
        menu.add(0, 3, 0, "Forget this PC")
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        when (item.itemId) {
            1 -> startActivity(Intent(Settings.ACTION_VOICE_INPUT_SETTINGS))
            2 -> Prefs(this).let { it.speakReplies = !it.speakReplies }
            3 -> { Hub.disconnect(); Prefs(this).forget(); show() }
        }
        return true
    }

    // The window has no action bar (NoActionBar theme), so open the menu from the hardware/gesture menu key.
    override fun onKeyUp(keyCode: Int, event: android.view.KeyEvent?): Boolean {
        if (keyCode == android.view.KeyEvent.KEYCODE_MENU) { openOptionsMenu(); return true }
        return super.onKeyUp(keyCode, event)
    }

    @Suppress("unused")
    private fun gravityCenter() = Gravity.CENTER
}
