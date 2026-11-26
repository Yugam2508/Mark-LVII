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
    val abilities = listOf("status", "contacts", "call", "text", "find_phone")

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

    /** Stops "find my phone" (called when the app is opened). */
    fun stopRinging() { ringing?.stop(); ringing = null }
}
