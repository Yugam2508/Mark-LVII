package app.jarvis.assistant

import android.content.Context
import android.graphics.Color
import android.text.InputType
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView

/** First run: connect this phone to your Jarvis PC. */
class PairPanel(context: Context, private val onPaired: () -> Unit) : LinearLayout(context) {
    init {
        orientation = VERTICAL
        setBackgroundColor(Color.rgb(2, 8, 12))
        val pad = (20 * resources.displayMetrics.density).toInt()
        setPadding(pad, pad * 2, pad, pad)

        fun label(t: String, size: Float, color: Int) = TextView(context).apply { text = t; textSize = size; setTextColor(color) }
        addView(label("JARVIS", 28f, Color.rgb(0, 212, 255)))
        addView(label("Connect to your PC.\n\n1. Turn Tailscale on, on this phone.\n2. Type your PC's Tailscale address " +
            "(for example 100.89.195.89:8000).\n3. Press CONNECT. No key is needed when this phone is on the same " +
            "Tailscale account as the PC. If it asks for one, press Remote Control in Jarvis on the PC and type the " +
            "8-character key shown there (or paste the whole QR link).",
            14f, Color.rgb(160, 190, 205)))

        val address = EditText(context).apply {
            hint = "PC address, e.g. 100.89.195.89:8000"; setHintTextColor(Color.rgb(80, 110, 125))
            setTextColor(Color.WHITE); inputType = InputType.TYPE_TEXT_VARIATION_URI or InputType.TYPE_CLASS_TEXT
            setText(Prefs(context).baseUrl)
        }
        val key = EditText(context).apply {
            hint = "Key (only if asked)"; setHintTextColor(Color.rgb(80, 110, 125)); setTextColor(Color.WHITE)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS
        }
        val message = label("", 13f, Color.rgb(255, 160, 60))
        val go = Button(context).apply { text = "CONNECT" }
        go.setOnClickListener {
            val parsed = Protocol.parseAddress(address.text.toString())
            val k = key.text.toString().trim().ifEmpty { parsed?.key.orEmpty() }
            when {
                parsed == null -> message.text = "That doesn't look like an address."
                k.isNotEmpty() && !Protocol.isKey(k) -> message.text = "The key is 8 letters and numbers."
                else -> {
                    go.isEnabled = false; message.text = "Connecting…"
                    Hub.pair(context, parsed.baseUrl, k) { ok, detail ->
                        go.isEnabled = true
                        message.text = if (ok) "" else detail
                        if (ok) onPaired()
                    }
                }
            }
        }
        // Pasting the QR link fills in both fields.
        address.setOnFocusChangeListener { _, focused ->
            if (!focused) Protocol.parseAddress(address.text.toString())?.let { p ->
                p.key?.let { key.setText(it) }
                address.setText(p.baseUrl)
            }
        }
        addView(address); addView(key); addView(go); addView(message)
    }
}
