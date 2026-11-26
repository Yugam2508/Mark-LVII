package app.jarvis.assistant

import org.json.JSONObject

/**
 * Everything the app needs to know about how it talks to a Jarvis PC, with no Android types
 * in it so it can be tested on a plain JVM (see android/README.md).
 *
 * The PC side is dashboard/server.py: pair once with a one-time key, keep the device token,
 * trade it for a fresh session token each time, then a WebSocket at /ws carries the
 * conversation and takes commands.
 */
object Protocol {

    /** A hub address and pairing key found in what the user typed or pasted. */
    data class Pairing(val baseUrl: String, val key: String?)

    private val KEY = Regex("^[A-Za-z0-9]{8}$")

    /**
     * Accepts any of:
     *   http://100.89.195.89:8000/auto-login?key=ABCD1234   (the QR link)
     *   100.89.195.89:8000                                  (address only)
     *   100.89.195.89                                       (default port 8000)
     */
    fun parseAddress(input: String): Pairing? {
        var text = input.trim()
        if (text.isEmpty()) return null
        var key: String? = null
        val q = text.indexOf("?key=")
        if (q >= 0) {
            key = text.substring(q + 5).takeWhile { it.isLetterOrDigit() }.uppercase()
            text = text.substring(0, q)
        }
        text = text.removeSuffix("/auto-login").trimEnd('/')
        if (!text.contains("://")) text = "http://$text"
        val authority = text.substringAfter("://").substringBefore('/')
        if (authority.isEmpty() || authority.contains(' ')) return null
        val hostPart = if (authority.contains(':')) authority else "$authority:8000"
        return Pairing(text.substringBefore("://") + "://" + hostPart, key)
    }

    fun isKey(s: String) = KEY.matches(s.trim())

    fun wsUrl(baseUrl: String, token: String): String =
        baseUrl.replaceFirst("https://", "wss://").replaceFirst("http://", "ws://") + "/ws?token=" + token

    fun pairBody(key: String, deviceName: String): String =
        JSONObject().put("pin", key.trim().uppercase()).put("name", deviceName).toString()

    fun commandBody(text: String): String = JSONObject().put("type", "command").put("text", text).toString()

    /** Tells the PC this phone is here and what it can do. */
    fun helloBody(name: String, abilities: List<String>): String =
        JSONObject().put("type", "hello").put("name", name).put("abilities", org.json.JSONArray(abilities)).toString()

    /** The phone's answer to an action the PC asked for. */
    fun resultBody(id: String, ok: Boolean, text: String, data: JSONObject? = null): String {
        val o = JSONObject().put("type", "result").put("id", id).put("ok", ok).put("text", text)
        if (data != null) o.put("data", data)
        return o.toString()
    }

    /** What the server can send down the socket. */
    sealed class Event {
        data class Said(val speaker: String, val text: String) : Event()   // speaker: "user" | "jarvis"
        data class System(val text: String) : Event()
        data class Status(val state: String) : Event()                     // "active" | "sleeping"
        /** The PC asks this phone to do something (call, text, ...). Answered with resultBody. */
        class PhoneAction(val id: String, val action: String, val args: JSONObject) : Event()
    }

    fun parseEvent(json: String): Event? = try {
        val o = JSONObject(json)
        when (o.optString("type")) {
            "log" -> {
                val text = o.optString("text").trim()
                if (text.isEmpty()) null else Event.Said(o.optString("speaker", "jarvis"), text)
            }
            "sys" -> Event.System(o.optString("text"))
            "status" -> Event.Status(o.optString("state"))
            "phone_action" -> {
                val id = o.optString("id")
                if (id.isEmpty()) null else Event.PhoneAction(id, o.optString("action"), o.optJSONObject("args") ?: JSONObject())
            }
            else -> null
        }
    } catch (e: Exception) {
        null
    }

    /** Pulls "ok", "token", "device_token" and "error" out of the pairing / login replies. */
    data class AuthReply(val ok: Boolean, val token: String?, val deviceToken: String?, val error: String?)

    fun parseAuth(json: String): AuthReply = try {
        val o = JSONObject(json)
        AuthReply(o.optBoolean("ok"), o.optString("token").ifEmpty { null },
            o.optString("device_token").ifEmpty { null }, o.optString("error").ifEmpty { null })
    } catch (e: Exception) {
        AuthReply(false, null, null, "The PC sent something unexpected")
    }
}
