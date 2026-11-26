package app.jarvis.assistant

import android.Manifest
import android.app.Activity
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast

/**
 * "Permissions & setup": everything Jarvis can be allowed to do on this phone, each with a tick or a cross
 * and one tap to fix it. The phone has no menu key, so this screen is where every switch lives (opened from
 * the ⋮ button on the main screen). Rows refresh when you come back from a settings page.
 */
class SetupPanel(private val activity: Activity, private val onClose: () -> Unit) : ScrollView(activity) {
    private val list = LinearLayout(activity).apply { orientation = LinearLayout.VERTICAL }

    init {
        setBackgroundColor(Color.rgb(2, 8, 12))
        val pad = dp(16)
        list.setPadding(pad, pad, pad, pad)
        addView(list)
        refresh()
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private class Row(val title: String, val ok: Boolean, val fix: String, val action: () -> Unit)

    private fun granted(p: String) = activity.checkSelfPermission(p) == PackageManager.PERMISSION_GRANTED

    private fun askOrSettings(vararg perms: String) {
        val missing = perms.filter { !granted(it) }
        if (missing.isEmpty()) return
        // Asked once and refused twice, Android stops showing the prompt: the app's page is the way then.
        if (missing.any { !activity.shouldShowRequestPermissionRationale(it) } && asked.containsAll(missing)) {
            openAppSettings()
        } else {
            asked.addAll(missing)
            activity.requestPermissions(missing.toTypedArray(), 2)
        }
    }

    private fun openAppSettings() = open(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${activity.packageName}")))

    private fun open(i: Intent) {
        try { activity.startActivity(i) } catch (e: Exception) {
            Toast.makeText(activity, "This phone doesn't have that settings page; opening the app's page instead", Toast.LENGTH_LONG).show()
            try { activity.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${activity.packageName}"))) } catch (_: Exception) { }
        }
    }

    private fun rows(): List<Row> {
        val pm = activity.getSystemService(PowerManager::class.java)
        val prefs = Prefs(activity)
        val list = mutableListOf(
            Row("Microphone (talk to Jarvis)", granted(Manifest.permission.RECORD_AUDIO), "allow") { askOrSettings(Manifest.permission.RECORD_AUDIO) },
            Row("Contacts (call or text people by name)", granted(Manifest.permission.READ_CONTACTS), "allow") { askOrSettings(Manifest.permission.READ_CONTACTS) },
            Row("Phone calls", granted(Manifest.permission.CALL_PHONE), "allow") { askOrSettings(Manifest.permission.CALL_PHONE) },
            Row("Send texts", granted(Manifest.permission.SEND_SMS), "allow") { askOrSettings(Manifest.permission.SEND_SMS) },
            Row("Read texts (\"what did Mum text me?\")", granted(Manifest.permission.READ_SMS), "allow") { askOrSettings(Manifest.permission.READ_SMS) },
            Row("Call history (\"did anyone call?\")", granted(Manifest.permission.READ_CALL_LOG), "allow") { askOrSettings(Manifest.permission.READ_CALL_LOG) },
            Row("Location (\"where's my phone?\")", granted(Manifest.permission.ACCESS_FINE_LOCATION), "allow") { askOrSettings(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION) },
        )
        if (Build.VERSION.SDK_INT >= 33) list += Row("Notifications from Jarvis", granted(Manifest.permission.POST_NOTIFICATIONS), "allow") { askOrSettings(Manifest.permission.POST_NOTIFICATIONS) }
        list += listOf(
            Row("Open apps and sites when asked", Settings.canDrawOverlays(activity), "switch on") {
                open(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:${activity.packageName}"))) },
            Row("Read and reply to notifications (WhatsApp etc.)", NotifyService.enabled(activity), "switch on") {
                open(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)) },
            Row("Press Send in WhatsApp for you (optional)", sendTapEnabled(activity), "switch on") {
                Toast.makeText(activity, "Find Jarvis under Installed apps / Downloaded apps and switch it on", Toast.LENGTH_LONG).show()
                open(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) },
            Row("Jarvis is the phone's assistant (long-press power)", isAssistant(activity), "choose Jarvis") {
                open(Intent(Settings.ACTION_VOICE_INPUT_SETTINGS)) },
            Row("Battery: not restricted (keeps the link alive)", pm?.isIgnoringBatteryOptimizations(activity.packageName) == true, "allow") {
                try {
                    activity.startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:${activity.packageName}")))
                } catch (e: Exception) { open(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) } },
        )
        list += listOf(
            Row("Always listening: ${if (prefs.openMic) "ON" else "OFF"}", true, "") {
                prefs.openMic = !prefs.openMic
                if (prefs.openMic) LinkService.start(activity, listen = true) else LiveAudio.stop()
                Toast.makeText(activity, if (prefs.openMic) "Listening all the time" else "Stopped listening", Toast.LENGTH_SHORT).show()
            },
            Row("Talk over Jarvis while it speaks: ${if (prefs.duplex) "ON" else "OFF"}", true, "") {
                prefs.duplex = !prefs.duplex
                LiveAudio.stop(); if (prefs.openMic) LinkService.start(activity, listen = true)
                Toast.makeText(activity, if (prefs.duplex) "You can interrupt Jarvis by talking" else "Jarvis won't listen while it speaks (use this if it hears itself)", Toast.LENGTH_LONG).show()
            },
        )
        return list
    }

    fun refresh() {
        list.removeAllViews()
        val head = TextView(activity).apply {
            text = "PERMISSIONS & SETUP"; textSize = 20f; setTextColor(Color.rgb(0, 212, 255)); setPadding(0, 0, 0, dp(6))
        }
        list.addView(head)
        list.addView(TextView(activity).apply {
            text = "Tap a line with ✗ to fix it. Ticks show what Jarvis can already do."
            textSize = 13f; setTextColor(Color.rgb(140, 170, 185)); setPadding(0, 0, 0, dp(12))
        })
        for (r in rows()) {
            val t = TextView(activity).apply {
                text = when {
                    r.fix.isEmpty() -> "•  ${r.title}"
                    r.ok -> "✓  ${r.title}"
                    else -> "✗  ${r.title}  —  tap to ${r.fix}"
                }
                textSize = 15f
                setTextColor(when { r.fix.isEmpty() -> Color.rgb(200, 220, 230); r.ok -> Color.rgb(0, 230, 130); else -> Color.rgb(255, 170, 70) })
                setPadding(0, dp(10), 0, dp(10))
                setOnClickListener { r.action(); postDelayed({ refresh() }, 400) }
            }
            list.addView(t)
        }
        val bar = LinearLayout(activity).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.END; setPadding(0, dp(16), 0, 0) }
        bar.addView(Button(activity).apply {
            text = "FORGET THIS PC"
            setOnClickListener { Hub.disconnect(); Prefs(activity).forget(); onClose() }
        })
        bar.addView(Button(activity).apply { text = "DONE"; setOnClickListener { onClose() } })
        list.addView(bar)
    }

    companion object {
        private val asked = mutableSetOf<String>()

        fun sendTapEnabled(context: Context): Boolean {
            val on = Settings.Secure.getString(context.contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES) ?: return false
            val me = ComponentName(context, SendTapService::class.java)
            return on.split(':').any { ComponentName.unflattenFromString(it) == me }
        }

        fun isAssistant(context: Context): Boolean {
            val r = context.contentResolver
            val a = Settings.Secure.getString(r, "assistant") ?: ""
            val v = Settings.Secure.getString(r, "voice_interaction_service") ?: ""
            return a.contains(context.packageName) || v.contains(context.packageName)
        }
    }
}
