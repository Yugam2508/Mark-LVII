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
    private var triedAuto = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(root)
        // Everything Jarvis may be asked to do on this phone, asked for once up front.
        val wanted = mutableListOf(Manifest.permission.RECORD_AUDIO, Manifest.permission.READ_CONTACTS,
            Manifest.permission.CALL_PHONE, Manifest.permission.SEND_SMS,
            Manifest.permission.READ_CALL_LOG, Manifest.permission.ACCESS_FINE_LOCATION)
        if (android.os.Build.VERSION.SDK_INT >= 33) wanted += Manifest.permission.POST_NOTIFICATIONS
        val missing = wanted.filter { checkSelfPermission(it) != android.content.pm.PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) requestPermissions(missing.toTypedArray(), 1)
        PhoneActions.stopRinging()
        show()
    }

    private fun show() {
        root.removeAllViews()
        if (Prefs(this).paired) {
            LinkService.start(this)
            root.addView(ConversationPanel(this, listenOnShow = intent?.action == Intent.ACTION_ASSIST, onUnpaired = { show() }))
        } else {
            root.addView(PairPanel(this, autoConnect = Prefs(this).canAutoConnect && !triedAuto) { show() })
            triedAuto = true
        }
        window.statusBarColor = android.graphics.Color.rgb(2, 8, 12)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        show()                                   // the microphone may just have been allowed: start listening
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        show()
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menu.add(0, 1, 0, "Make Jarvis my assistant")
        menu.add(0, 2, 0, "Always listening on/off")
        menu.add(0, 4, 0, "Talk over Jarvis on/off")
        menu.add(0, 5, 0, "Let Jarvis open apps and sites")
        menu.add(0, 6, 0, "Let Jarvis tap Send in WhatsApp")
        menu.add(0, 7, 0, "Let Jarvis read notifications")
        menu.add(0, 3, 0, "Forget this PC")
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        when (item.itemId) {
            1 -> startActivity(Intent(Settings.ACTION_VOICE_INPUT_SETTINGS))
            2 -> Prefs(this).let {
                it.openMic = !it.openMic
                if (it.openMic) LinkService.start(this, listen = true) else LiveAudio.stop()
            }
            4 -> Prefs(this).let { it.duplex = !it.duplex; LiveAudio.stop(); if (it.openMic) LinkService.start(this, listen = true) }
            5 -> startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, android.net.Uri.parse("package:$packageName")))
            6 -> startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            7 -> startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
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
