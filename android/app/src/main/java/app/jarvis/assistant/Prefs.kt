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

    var speakReplies: Boolean
        get() = sp.getBoolean("speak", true)
        set(v) = sp.edit().putBoolean("speak", v).apply()

    val paired: Boolean get() = baseUrl.isNotEmpty() && deviceToken.isNotEmpty()

    /** A first run that can connect by itself: an address is known and no phone token yet. */
    val canAutoConnect: Boolean get() = defaultAddress.isNotEmpty() && deviceToken.isEmpty()

    /** The PC forgot this phone: drop the token but keep the address, so only a new key is needed. */
    fun forgetDevice() = sp.edit().remove("device").apply()

    fun forget() = sp.edit().remove("base").remove("device").apply()
}
