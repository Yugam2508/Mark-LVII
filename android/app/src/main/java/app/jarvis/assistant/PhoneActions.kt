package app.jarvis.assistant

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.Ringtone
import android.media.RingtoneManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.BatteryManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.ContactsContract
import android.telecom.TelecomManager
import android.telephony.SmsManager
import org.json.JSONArray
import org.json.JSONObject

/**
 * What the phone can do when the PC asks. Everything here works from the background (no
 * screens are opened): that is why calls go through TelecomManager and texts through SmsManager.
 * The PC always asks the user to confirm calls and texts first (plugins/phone_control.py).
 */
object PhoneActions {
    val abilities = listOf("status", "contacts", "call", "text", "find_phone", "open_app", "open_url",
        "settings", "volume", "flashlight", "timer", "media", "navigate", "whatsapp",
        "notifications", "reply_notification", "dismiss_notification", "recent_calls",
        "send_to_phone", "location", "dnd", "texts", "alarm", "screenshot", "lock", "answer_call", "decline_call",
        "screen_read", "tap", "scroll", "type_text", "nav", "ringer")

    class Result(val ok: Boolean, val text: String, val data: JSONObject? = null)

    private var ringing: Ringtone? = null

    /** A system service, or a clear message when this phone doesn't have it. */
    private fun <T : Any> service(context: Context, cls: Class<T>): T =
        context.getSystemService(cls) ?: throw IllegalStateException("this phone has no ${cls.simpleName}")

    fun run(context: Context, action: String, args: JSONObject): Result = try {
        when (action) {
            "status" -> status(context)
            "contacts" -> contacts(context, args.optString("query"))
            "call" -> call(context, args.optString("number"))
            "text" -> text(context, args.optString("number"), args.optString("message"))
            "find_phone" -> findPhone(context, args.optInt("seconds", 30))
            "open_app" -> openApp(context, args.optString("name"))
            "open_url" -> openUrl(context, args.optString("url"))
            "settings" -> openSettings(context, args.optString("page"))
            "volume" -> volume(context, args.optInt("level", -1), args.optString("direction"))
            "flashlight" -> flashlight(context, args.optBoolean("on", true))
            "timer" -> timer(context, args.optInt("seconds", 0), args.optString("label"))
            "media" -> media(context, args.optString("key"))
            "notifications" -> notifications(context, args.optString("app"), args.optInt("limit", 8))
            "reply_notification" -> replyNotification(context, args)
            "dismiss_notification" -> dismissNotification(args)
            "send_to_phone" -> sendToPhone(context, args.optString("text"), args.optString("title"))
            "location" -> location(context)
            "dnd" -> dnd(context, args.optBoolean("on", true))
            "recent_calls" -> recentCalls(context, args.optInt("limit", 8))
            "texts" -> texts(context, args.optString("from"), args.optInt("limit", 8))
            "alarm" -> alarm(context, args.optInt("hour", -1), args.optInt("minute", 0), args.optString("label"))
            "screenshot" -> globalAction(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_TAKE_SCREENSHOT, "Screenshot taken (it's in the phone's gallery)")
            "screen_read" -> SendTapService.screenText()?.let { Result(true, it.ifBlank { "Nothing readable on screen" }) }
                ?: Result(false, accessHint)
            "tap" -> hands { SendTapService.tap(args.optString("text")) }
            "scroll" -> hands { SendTapService.scroll(args.optString("direction") != "up") }
            "type_text" -> hands { SendTapService.type(args.optString("text")) }
            "nav" -> nav(args.optString("where"))
            "ringer" -> ringer(context, args.optString("mode"))
            "answer_call" -> callButton(true)
            "decline_call" -> callButton(false)
            "lock" -> globalAction(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_LOCK_SCREEN, "Phone locked")
            "whatsapp" -> whatsapp(context, args.optString("number"), args.optString("message"))
            "navigate" -> navigate(context, args.optString("where"))
            else -> Result(false, "This phone doesn't know how to $action yet")
        }
    } catch (e: SecurityException) {
        Result(false, "Jarvis doesn't have permission for that on the phone. Open the app and allow it.")
    } catch (e: Exception) {
        Result(false, "It failed: ${e.message}")
    }

    private fun status(context: Context): Result {
        val b = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = b?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = b?.getIntExtra(BatteryManager.EXTRA_SCALE, 100) ?: 100
        val pct = if (level >= 0) level * 100 / scale else -1
        val charging = (b?.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) ?: 0) != 0
        val cm = service(context, ConnectivityManager::class.java)
        val caps = cm.getNetworkCapabilities(cm.activeNetwork)
        val net = when {
            caps == null -> "offline"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "on Wi-Fi"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "on mobile data"
            else -> "connected"
        }
        val text = "Battery ${if (pct >= 0) "$pct%" else "unknown"}${if (charging) ", charging" else ""}, $net"
        return Result(true, text, JSONObject().put("battery", pct).put("charging", charging))
    }

    private fun contacts(context: Context, query: String): Result {
        if (query.isBlank()) return Result(false, "Who should I look up?")
        val out = JSONArray()
        val uri = ContactsContract.CommonDataKinds.Phone.CONTENT_URI
        val cols = arrayOf(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
            ContactsContract.CommonDataKinds.Phone.NUMBER, ContactsContract.CommonDataKinds.Phone.TYPE)
        context.contentResolver.query(uri, cols, "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} LIKE ?",
            arrayOf("%$query%"), "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} ASC")?.use { c ->
            while (c.moveToNext() && out.length() < 10) {
                val type = c.getInt(2)
                out.put(JSONObject().put("name", c.getString(0)).put("number", c.getString(1))
                    .put("label", ContactsContract.CommonDataKinds.Phone.getTypeLabel(context.resources, type, "").toString()))
            }
        }
        return Result(true, "${out.length()} match(es)", JSONObject().put("contacts", out))
    }

    private fun call(context: Context, number: String): Result {
        if (number.isBlank()) return Result(false, "No number to call")
        service(context, TelecomManager::class.java).placeCall(Uri.fromParts("tel", number, null), Bundle())
        return Result(true, "Calling $number")
    }

    private fun text(context: Context, number: String, message: String): Result {
        if (number.isBlank() || message.isBlank()) return Result(false, "I need a number and a message")
        // SmsManager is a system service only from Android 12; before that it is SmsManager.getDefault().
        val sms = if (android.os.Build.VERSION.SDK_INT >= 31) service(context, SmsManager::class.java)
            else @Suppress("DEPRECATION") SmsManager.getDefault()
        sms.sendMultipartTextMessage(number, null, sms.divideMessage(message), null, null)
        return Result(true, "Text sent to $number")
    }

    private fun findPhone(context: Context, seconds: Int): Result {
        val audio = service(context, AudioManager::class.java)
        audio.setStreamVolume(AudioManager.STREAM_ALARM, audio.getStreamMaxVolume(AudioManager.STREAM_ALARM), 0)
        ringing?.stop()
        val r = RingtoneManager.getRingtone(context, RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM))
        r.audioAttributes = AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build()
        r.isLooping = true
        r.play()
        ringing = r
        Handler(Looper.getMainLooper()).postDelayed({ if (ringing === r) { r.stop(); ringing = null } },
            seconds.coerceIn(5, 120) * 1000L)
        return Result(true, "Ringing")
    }

    /** Starting an activity from the background needs "Display over other apps". */
    private fun launch(context: Context, intent: Intent): Result {
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
        return Result(true, "Opened")
    }

    private val overlayHint = "On the phone, open Jarvis → ⋮ → Permissions & setup and switch on \"Open apps and sites when asked\""

    /**
     * Android quietly ignores an app that opens something while it is in the background (no error comes
     * back), so "opened" would be a lie. It is allowed while Jarvis is on screen, or with "Display over
     * other apps" switched on; otherwise say what to switch on instead of pretending.
     */
    private fun guarded(context: Context, intent: Intent): Result {
        if (!android.provider.Settings.canDrawOverlays(context) && !MainActivity.visible)
            return Result(false, "Android won't let Jarvis open things from the background yet. $overlayHint")
        return try { launch(context, intent) } catch (e: android.content.ActivityNotFoundException) {
            Result(false, "No app on the phone can open that")
        } catch (e: Exception) {
            Result(false, "The phone wouldn't open it (${e.message})")
        }
    }

    private fun openApp(context: Context, name: String): Result {
        if (name.isBlank()) return Result(false, "Which app?")
        val pm = context.packageManager
        val main = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val apps = pm.queryIntentActivities(main, 0)
        val want = name.trim().lowercase()
        val hit = apps.firstOrNull { it.loadLabel(pm).toString().lowercase() == want }
            ?: apps.firstOrNull { it.loadLabel(pm).toString().lowercase().contains(want) }
            ?: return Result(false, "No app called $name is installed")
        val intent = pm.getLaunchIntentForPackage(hit.activityInfo.packageName)
            ?: return Result(false, "$name can't be opened")
        return guarded(context, intent).let {
            if (it.ok) Result(true, "Opened ${hit.loadLabel(pm)}") else it
        }
    }

    private fun openUrl(context: Context, url: String): Result {
        val u = url.trim()
        if (!Regex("^https?://", RegexOption.IGNORE_CASE).containsMatchIn(u)) return Result(false, "Only web links can be opened")
        return guarded(context, Intent(Intent.ACTION_VIEW, Uri.parse(u)))
    }

    private fun openSettings(context: Context, page: String): Result {
        val action = when (page.lowercase()) {
            "bluetooth" -> android.provider.Settings.ACTION_BLUETOOTH_SETTINGS
            "wifi", "wi-fi" -> android.provider.Settings.ACTION_WIFI_SETTINGS
            "airplane" -> android.provider.Settings.ACTION_AIRPLANE_MODE_SETTINGS
            "display" -> android.provider.Settings.ACTION_DISPLAY_SETTINGS
            "sound" -> android.provider.Settings.ACTION_SOUND_SETTINGS
            "location" -> android.provider.Settings.ACTION_LOCATION_SOURCE_SETTINGS
            "battery" -> android.provider.Settings.ACTION_BATTERY_SAVER_SETTINGS
            else -> android.provider.Settings.ACTION_SETTINGS
        }
        // Android no longer lets apps flip Bluetooth or Wi-Fi themselves; the page opens for one tap.
        return guarded(context, Intent(action))
    }

    private fun volume(context: Context, level: Int, direction: String): Result {
        val audio = service(context, AudioManager::class.java)
        val max = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
        val now = audio.getStreamVolume(AudioManager.STREAM_MUSIC)
        val target = when {
            level >= 0 -> (level.coerceIn(0, 100) * max / 100.0).toInt()
            direction == "up" -> (now + maxOf(1, max / 7)).coerceAtMost(max)
            direction == "down" -> (now - maxOf(1, max / 7)).coerceAtLeast(0)
            else -> return Result(false, "Say a level or up/down")
        }
        audio.setStreamVolume(AudioManager.STREAM_MUSIC, target, 0)
        return Result(true, "Volume ${target * 100 / max}%")
    }

    private fun flashlight(context: Context, on: Boolean): Result {
        val cm = service(context, android.hardware.camera2.CameraManager::class.java)
        val id = cm.cameraIdList.firstOrNull {
            cm.getCameraCharacteristics(it).get(android.hardware.camera2.CameraCharacteristics.FLASH_INFO_AVAILABLE) == true
        } ?: return Result(false, "This phone has no flashlight")
        cm.setTorchMode(id, on)
        return Result(true, if (on) "Flashlight on" else "Flashlight off")
    }

    private fun timer(context: Context, seconds: Int, label: String): Result {
        if (seconds <= 0) return Result(false, "How long?")
        val i = Intent(android.provider.AlarmClock.ACTION_SET_TIMER)
            .putExtra(android.provider.AlarmClock.EXTRA_LENGTH, seconds)
            .putExtra(android.provider.AlarmClock.EXTRA_MESSAGE, label)
            .putExtra(android.provider.AlarmClock.EXTRA_SKIP_UI, true)
        return guarded(context, i).let { if (it.ok) Result(true, "Timer set for ${seconds}s") else it }
    }

    private fun media(context: Context, key: String): Result {
        val code = when (key.lowercase()) {
            "play", "pause", "playpause" -> android.view.KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE
            "next" -> android.view.KeyEvent.KEYCODE_MEDIA_NEXT
            "previous" -> android.view.KeyEvent.KEYCODE_MEDIA_PREVIOUS
            else -> return Result(false, "play, pause, next or previous")
        }
        val audio = service(context, AudioManager::class.java)
        audio.dispatchMediaKeyEvent(android.view.KeyEvent(android.view.KeyEvent.ACTION_DOWN, code))
        audio.dispatchMediaKeyEvent(android.view.KeyEvent(android.view.KeyEvent.ACTION_UP, code))
        return Result(true, "Sent $key")
    }

    /** Opens the chat with the message typed in; the accessibility service (if on) presses Send. */
    private fun whatsapp(context: Context, number: String, message: String): Result {
        val digits = number.filter { it.isDigit() }
        if (digits.length < 6 || message.isBlank()) return Result(false, "I need a number and a message")
        val url = "https://wa.me/$digits?text=" + Uri.encode(message)
        // Switched on in Settings counts even if Android hasn't bound the service in this process yet.
        val autoSend = SendTapService.enabled || SetupPanel.sendTapEnabled(context)
        if (autoSend) SendTapService.arm()
        val r = guarded(context, Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        if (!r.ok) return r
        return Result(true, if (autoSend) "WhatsApp opened; Send will be pressed when the chat appears"
            else "WhatsApp is open with the message typed in; it still needs a tap on Send",
            JSONObject().put("auto_send", autoSend))
    }

    private fun notifications(context: Context, app: String, limit: Int): Result {
        if (!NotifyService.enabled(context))
            return Result(false, "Notification access is off. In the Jarvis app menu choose \"Let Jarvis read notifications\".")
        val list = NotifyService.list(app, limit.coerceIn(1, 30))
        return Result(true, "${list.length()} notification(s)", JSONObject().put("notifications", list))
    }

    private fun replyNotification(context: Context, a: JSONObject): Result {
        val e = NotifyService.find(a.optString("key"), a.optString("app"), a.optString("from"))
            ?: return Result(false, "I can't find that message on the phone any more")
        if (a.optString("text").isBlank()) return Result(false, "What should the reply say?")
        if (!NotifyService.reply(context, e, a.optString("text"))) return Result(false, "That notification has no reply button")
        return Result(true, "Replied to ${e.title} in ${e.app}")
    }

    private fun dismissNotification(a: JSONObject): Result {
        val e = NotifyService.find(a.optString("key"), a.optString("app"), a.optString("from"))
            ?: return Result(false, "Nothing like that to clear")
        return if (NotifyService.dismiss(e)) Result(true, "Cleared") else Result(false, "Notification access is off")
    }

    /** Text or a link from the PC: copied to the clipboard and shown as a notification (tap to open a link). */
    private fun sendToPhone(context: Context, text: String, title: String): Result {
        if (text.isBlank()) return Result(false, "Nothing to send")
        val cm = service(context, android.content.ClipboardManager::class.java)
        cm.setPrimaryClip(android.content.ClipData.newPlainText("From Jarvis", text))
        val nm = service(context, android.app.NotificationManager::class.java)
        nm.createNotificationChannel(android.app.NotificationChannel("from_pc", "From your PC",
            android.app.NotificationManager.IMPORTANCE_HIGH))
        val link = Regex("https?://\\S+").find(text)?.value
        val tap = if (link != null) Intent(Intent.ACTION_VIEW, Uri.parse(link)) else
            Intent(context, MainActivity::class.java)
        val pi = android.app.PendingIntent.getActivity(context, 7, tap.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            android.app.PendingIntent.FLAG_IMMUTABLE or android.app.PendingIntent.FLAG_UPDATE_CURRENT)
        val n = android.app.Notification.Builder(context, "from_pc")
            .setSmallIcon(android.R.drawable.ic_menu_send)
            .setContentTitle(title.ifBlank { "From Jarvis" })
            .setContentText(text.take(200))
            .setStyle(android.app.Notification.BigTextStyle().bigText(text.take(2000)))
            .setContentIntent(pi).setAutoCancel(true).build()
        nm.notify(text.hashCode(), n)
        return Result(true, "On the phone (copied, and in the notifications)")
    }

    private fun location(context: Context): Result {
        val lm = service(context, android.location.LocationManager::class.java)
        val best = lm.getProviders(true).mapNotNull { lm.getLastKnownLocation(it) }.maxByOrNull { it.time }
            ?: return Result(false, "The phone has no recent location (location off, or permission not given)")
        val ageMin = (System.currentTimeMillis() - best.time) / 60000
        val link = "https://maps.google.com/?q=${best.latitude},${best.longitude}"
        return Result(true, "Within ${best.accuracy.toInt()} m, $ageMin min ago: $link",
            JSONObject().put("lat", best.latitude).put("lon", best.longitude).put("accuracy_m", best.accuracy.toDouble())
                .put("age_min", ageMin).put("map", link))
    }

    private fun dnd(context: Context, on: Boolean): Result {
        val svc = NotifyService.instance
            ?: return Result(false, "Turn on \"Let Jarvis read notifications\" in the app menu first")
        svc.requestInterruptionFilter(if (on) android.service.notification.NotificationListenerService.INTERRUPTION_FILTER_PRIORITY
            else android.service.notification.NotificationListenerService.INTERRUPTION_FILTER_ALL)
        return Result(true, if (on) "Do Not Disturb on" else "Do Not Disturb off")
    }

    /** The latest texts in the inbox, optionally only from one person (a name or part of a number). */
    private fun texts(context: Context, from: String, limit: Int): Result {
        val out = JSONArray()
        val uri = android.provider.Telephony.Sms.Inbox.CONTENT_URI
        val cols = arrayOf(android.provider.Telephony.Sms.ADDRESS, android.provider.Telephony.Sms.BODY,
            android.provider.Telephony.Sms.DATE)
        val want = from.trim().lowercase()
        val names = HashMap<String, String>()
        context.contentResolver.query(uri, cols, null, null, "${android.provider.Telephony.Sms.DATE} DESC")?.use { c ->
            var scanned = 0
            while (c.moveToNext() && out.length() < limit.coerceIn(1, 30) && scanned < 500) {
                scanned++
                val addr = c.getString(0) ?: continue
                val name = names.getOrPut(addr) { contactName(context, addr) ?: addr }
                if (want.isNotEmpty() && !name.lowercase().contains(want) && !addr.filter { it.isDigit() }.contains(want.filter { it.isDigit() }.ifEmpty { "\u0000" })) continue
                out.put(JSONObject().put("from", name).put("text", (c.getString(1) ?: "").take(500))
                    .put("age_min", (System.currentTimeMillis() - c.getLong(2)) / 60000))
            }
        }
        return Result(true, "${out.length()} text(s)", JSONObject().put("texts", out))
    }

    private fun contactName(context: Context, number: String): String? = try {
        val u = Uri.withAppendedPath(ContactsContract.PhoneLookup.CONTENT_FILTER_URI, Uri.encode(number))
        context.contentResolver.query(u, arrayOf(ContactsContract.PhoneLookup.DISPLAY_NAME), null, null, null)?.use {
            if (it.moveToFirst()) it.getString(0) else null
        }
    } catch (e: Exception) { null }

    private fun recentCalls(context: Context, limit: Int): Result {
        val out = JSONArray()
        context.contentResolver.query(android.provider.CallLog.Calls.CONTENT_URI,
            arrayOf(android.provider.CallLog.Calls.CACHED_NAME, android.provider.CallLog.Calls.NUMBER,
                android.provider.CallLog.Calls.TYPE, android.provider.CallLog.Calls.DATE),
            null, null, "${android.provider.CallLog.Calls.DATE} DESC")?.use { c ->
            while (c.moveToNext() && out.length() < limit.coerceIn(1, 30)) {
                val kind = when (c.getInt(2)) {
                    android.provider.CallLog.Calls.MISSED_TYPE -> "missed"
                    android.provider.CallLog.Calls.INCOMING_TYPE -> "incoming"
                    android.provider.CallLog.Calls.OUTGOING_TYPE -> "outgoing"
                    else -> "other"
                }
                out.put(JSONObject().put("who", c.getString(0) ?: c.getString(1)).put("type", kind)
                    .put("age_min", (System.currentTimeMillis() - c.getLong(3)) / 60000))
            }
        }
        return Result(true, "${out.length()} call(s)", JSONObject().put("calls", out))
    }

    private fun alarm(context: Context, hour: Int, minute: Int, label: String): Result {
        if (hour !in 0..23 || minute !in 0..59) return Result(false, "What time? (hour 0-23)")
        val i = Intent(android.provider.AlarmClock.ACTION_SET_ALARM)
            .putExtra(android.provider.AlarmClock.EXTRA_HOUR, hour)
            .putExtra(android.provider.AlarmClock.EXTRA_MINUTES, minute)
            .putExtra(android.provider.AlarmClock.EXTRA_MESSAGE, label.ifBlank { "Jarvis" })
            .putExtra(android.provider.AlarmClock.EXTRA_SKIP_UI, true)
        return guarded(context, i).let { if (it.ok) Result(true, "Alarm set for %02d:%02d".format(hour, minute)) else it }
    }

    private val accessHint = "That needs Jarvis switched on in Accessibility: open Jarvis → ⋮ → Permissions & setup → the Accessibility line"

    private fun hands(act: () -> String): Result {
        if (SendTapService.instance == null) return Result(false, accessHint)
        val r = act()
        return Result(r in setOf("tapped", "scrolled", "typed"), r)
    }

    private fun nav(where: String): Result {
        val a = when (where.lowercase()) {
            "back" -> android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_BACK
            "home" -> android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_HOME
            "recents", "recent apps", "apps" -> android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_RECENTS
            "notifications" -> android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_NOTIFICATIONS
            "quick settings" -> android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_QUICK_SETTINGS
            else -> return Result(false, "back, home, recents, notifications or quick settings")
        }
        return globalAction(a, "Done")
    }

    /** Ring / vibrate / silent. Silent needs Do Not Disturb access on Android, which notification access gives. */
    private fun ringer(context: Context, mode: String): Result {
        val audio = service(context, AudioManager::class.java)
        val m = when (mode.lowercase()) {
            "normal", "ring", "loud", "on" -> AudioManager.RINGER_MODE_NORMAL
            "vibrate", "vibration" -> AudioManager.RINGER_MODE_VIBRATE
            "silent", "mute", "off" -> AudioManager.RINGER_MODE_SILENT
            else -> return Result(false, "ring, vibrate or silent?")
        }
        return try {
            audio.ringerMode = m
            Result(true, "Ringer: ${mode.lowercase()}")
        } catch (e: SecurityException) {
            Result(false, "Android needs Do Not Disturb access for that: switch on \"Read and reply to notifications\" in ⋮ → Permissions & setup")
        }
    }

    private fun callButton(answer: Boolean): Result {
        val a = NotifyService.callButton(answer)
            ?: return Result(false, "No call is ringing (or notification access is off)")
        a.actionIntent.send()
        return Result(true, if (answer) "Answered" else "Declined")
    }

    private fun globalAction(action: Int, done: String): Result =
        if (SendTapService.global(action)) Result(true, done)
        else Result(false, "That needs Jarvis switched on in Accessibility: open Jarvis → ⋮ → Permissions & setup → " +
            "\"Press Send in WhatsApp for you\" (the same switch allows screenshots and locking)")

    private fun navigate(context: Context, where: String): Result {
        if (where.isBlank()) return Result(false, "Where to?")
        return guarded(context, Intent(Intent.ACTION_VIEW, Uri.parse("google.navigation:q=" + Uri.encode(where))))
    }

    /** Stops "find my phone" (called when the app is opened). */
    fun stopRinging() { ringing?.stop(); ringing = null }
}
