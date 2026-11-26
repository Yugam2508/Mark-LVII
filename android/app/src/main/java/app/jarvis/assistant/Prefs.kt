package app.jarvis.assistant

import android.content.Context

/** The little the app remembers: which PC, and the token that lets this phone back in. */
class Prefs(context: Context) {
    private val sp = context.applicationContext.getSharedPreferences("jarvis", Context.MODE_PRIVATE)

    var baseUrl: String
        get() = sp.getString("base", "") ?: ""
        set(v) = sp.edit().putString("base", v).apply()

    var deviceToken: String
        get() = sp.getString("device", "") ?: ""
        set(v) = sp.edit().putString("device", v).apply()

    var speakReplies: Boolean
        get() = sp.getBoolean("speak", true)
        set(v) = sp.edit().putBoolean("speak", v).apply()

    val paired: Boolean get() = baseUrl.isNotEmpty() && deviceToken.isNotEmpty()

    fun forget() = sp.edit().remove("base").remove("device").apply()
}
