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
    private var setup: SetupPanel? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(root)
        // Everything Jarvis may be asked to do on this phone, asked for once up front.
        val wanted = mutableListOf(Manifest.permission.RECORD_AUDIO, Manifest.permission.READ_CONTACTS,
            Manifest.permission.CALL_PHONE, Manifest.permission.SEND_SMS,
            Manifest.permission.READ_CALL_LOG, Manifest.permission.READ_SMS, Manifest.permission.ACCESS_FINE_LOCATION)
        if (android.os.Build.VERSION.SDK_INT >= 33) wanted += Manifest.permission.POST_NOTIFICATIONS
        val missing = wanted.filter { checkSelfPermission(it) != android.content.pm.PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) requestPermissions(missing.toTypedArray(), 1)
        PhoneActions.stopRinging()
        show()
    }

    /** The "Permissions & setup" screen (from the ⋮ button: the phone has no menu key). */
    fun showSetup() {
        root.removeAllViews()
        setup = SetupPanel(this) { show() }.also { root.addView(it) }
    }

    override fun onResume() {
        super.onResume()
        visible = true
        setup?.refresh()                          // back from a settings page: show what changed
    }

    override fun onPause() {
        visible = false
        super.onPause()
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (setup != null) show() else @Suppress("DEPRECATION") super.onBackPressed()
    }

    private fun show() {
        setup = null
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
        if (setup != null) setup?.refresh()       // asked from the setup screen: stay there, show the new ticks
        else show()                               // the microphone may just have been allowed: start listening
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        show()
    }

    // Phones with a menu key get the same screen from it.
    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menu.add(0, 1, 0, "Permissions & setup")
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        if (item.itemId == 1 && Prefs(this).paired) showSetup()
        return true
    }

    // The window has no action bar (NoActionBar theme), so open the menu from the hardware/gesture menu key.
    override fun onKeyUp(keyCode: Int, event: android.view.KeyEvent?): Boolean {
        if (keyCode == android.view.KeyEvent.KEYCODE_MENU) { openOptionsMenu(); return true }
        return super.onKeyUp(keyCode, event)
    }

    @Suppress("unused")
    private fun gravityCenter() = Gravity.CENTER

    companion object {
        /** On screen right now: Android lets an app open other apps and pages while it is visible. */
        @Volatile var visible = false
    }
}
