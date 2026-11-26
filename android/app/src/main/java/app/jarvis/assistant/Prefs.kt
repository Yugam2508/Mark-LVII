package app.jarvis.assistant

import android.content.Context

/** The little the app remembers: which PC, and the token that lets this phone back in. */
class Prefs(context: Context) {
    private val app = context.applicationContext
    private val sp = app.getSharedPreferences("jarvis", Context.MODE_PRIVATE)

    /**
     * The PC's address: what was paired with, else the one baked into this build.
     * To bake yours in, put it in android/app/src/main/assets/default_address.txt (git-ignored, so
     * your address stays out of the public repository) and rebuild — then the app never asks.
     */
    val defaultAddress: String by lazy {
        try {
            val text = app.assets.open("default_address.txt").bufferedReader().use { it.readText() }
            Protocol.parseAddress(text)?.baseUrl ?: ""
        } catch (e: Exception) {
            ""
        }
    }

    var baseUrl: String
        get() = (sp.getString("base", "") ?: "").ifEmpty { defaultAddress }
        set(v) = sp.edit().putString("base", v).apply()

    var deviceToken: String
        get() = sp.getString("device", "") ?: ""
        set(v) = sp.edit().putString("device", v).apply()

    /** Keep the microphone open and listening (no button). */
    var openMic: Boolean
        get() = sp.getBoolean("openMic", true)
        set(v) = sp.edit().putBoolean("openMic", v).apply()

    /** Let Jarvis hear you while it speaks (needs the phone's echo cancellation; turn off if it hears itself). */
    var duplex: Boolean
        get() = sp.getBoolean("duplex", true)
        set(v) = sp.edit().putBoolean("duplex", v).apply()

    /** Wait for "Hey Jarvis" before anything heard reaches Jarvis (the PC listens for it). */
    var wakeWord: Boolean
        get() = sp.getBoolean("wakeWord", true)
        set(v) = sp.edit().putBoolean("wakeWord", v).apply()

    /** A short chime and buzz when Jarvis wakes up. */
    var chime: Boolean
        get() = sp.getBoolean("chime", true)
        set(v) = sp.edit().putBoolean("chime", v).apply()

    /** Send the microphone only while someone talks (saves mobile data and battery). */
    var saveData: Boolean
        get() = sp.getBoolean("saveData", true)
        set(v) = sp.edit().putBoolean("saveData", v).apply()

    val paired: Boolean get() = baseUrl.isNotEmpty() && deviceToken.isNotEmpty()

    /** A first run that can connect by itself: an address is known and no phone token yet. */
    val canAutoConnect: Boolean get() = defaultAddress.isNotEmpty() && deviceToken.isEmpty()

    /** The PC forgot this phone: drop the token but keep the address, so only a new key is needed. */
    fun forgetDevice() = sp.edit().remove("device").apply()

    fun forget() = sp.edit().remove("base").remove("device").apply()
}
