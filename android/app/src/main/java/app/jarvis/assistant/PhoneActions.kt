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
        "settings", "volume", "flashlight", "timer", "media", "navigate")

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
        val sms = service(context, SmsManager::class.java)
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

    private val overlayHint = "Allow \"Let Jarvis open apps and sites\" in the app's menu first"

    private fun guarded(context: Context, intent: Intent): Result =
        try { launch(context, intent) } catch (e: Exception) {
            Result(false, "The phone wouldn't open it. $overlayHint")
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

    private fun navigate(context: Context, where: String): Result {
        if (where.isBlank()) return Result(false, "Where to?")
        return guarded(context, Intent(Intent.ACTION_VIEW, Uri.parse("google.navigation:q=" + Uri.encode(where))))
    }

    /** Stops "find my phone" (called when the app is opened). */
    fun stopRinging() { ringing?.stop(); ringing = null }
}
