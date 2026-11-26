package app.jarvis.assistant

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.text.InputType
import android.view.Gravity
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/**
 * The conversation screen, built in code so the same panel is the app's main screen AND the
 * overlay that opens when Jarvis is the phone's assistant (long-press power).
 *
 * Talk with the mic button (or it starts listening by itself as the assistant), or type.
 * Replies appear here and are read aloud on the phone.
 */
class ConversationPanel(context: Context, private val listenOnShow: Boolean = false) :
    LinearLayout(context), Hub.Listener, VoiceInput.Callback {

    private val prefs = Prefs(context)
    private val holo = HoloView(context)
    private val status = TextView(context)
    private val log = TextView(context)
    private val scroll = ScrollView(context)
    private val input = EditText(context)
    private val mic = Button(context)
    private val speaker = Speaker(context) { speaking ->
        post { holo.state = if (speaking) HoloView.State.SPEAKING else HoloView.State.IDLE; if (speaking) holo.level = 0.7f }
    }
    private val voice = VoiceInput(context, this)
    private var awaitingReply = false
    private val lines = StringBuilder()

    init {
        orientation = VERTICAL
        setBackgroundColor(Color.rgb(2, 8, 12))
        setPadding(dp(14), dp(10), dp(14), dp(10))

        status.setTextColor(Color.rgb(90, 140, 160)); status.textSize = 12f; status.gravity = Gravity.CENTER
        addView(status, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))
        addView(holo, LayoutParams(LayoutParams.MATCH_PARENT, 0, 1.3f))

        log.setTextColor(Color.rgb(220, 235, 245)); log.textSize = 15f
        scroll.addView(log)
        addView(scroll, LayoutParams(LayoutParams.MATCH_PARENT, 0, 1f))

        val row = LinearLayout(context).apply { orientation = HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        input.hint = "Type, or tap the mic"; input.setHintTextColor(Color.rgb(80, 110, 125))
        input.setTextColor(Color.WHITE); input.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
        input.imeOptions = EditorInfo.IME_ACTION_SEND; input.maxLines = 3
        input.setOnEditorActionListener { _, _, _ -> sendTyped(); true }
        row.addView(input, LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f))
        mic.text = "MIC"; mic.setOnClickListener { toggleMic() }
        row.addView(mic, LayoutParams(LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT))
        addView(row, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))

        Hub.history.forEach { append(it.speaker, it.text) }
        render()
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        Hub.add(this)
        Hub.connect(context)
        if (listenOnShow) post { startListening() }
    }

    override fun onDetachedFromWindow() {
        Hub.remove(this)
        stopAll()
        speaker.shutdown()
        super.onDetachedFromWindow()
    }

    // ── Hub ──────────────────────────────────────────────────────────────────

    override fun onConnection(connected: Boolean, detail: String) {
        status.text = if (connected) "● connected to your PC" else "○ $detail"
        status.setTextColor(if (connected) Color.rgb(0, 255, 136) else Color.rgb(255, 160, 60))
    }

    override fun onEvent(event: Protocol.Event) {
        when (event) {
            is Protocol.Event.Said -> {
                append(event.speaker, event.text); render()
                if (event.speaker == "jarvis") {
                    if (awaitingReply) {
                        awaitingReply = false
                        if (prefs.speakReplies) speaker.say(event.text) else holo.state = HoloView.State.IDLE
                    }
                }
            }
            is Protocol.Event.System, is Protocol.Event.Status -> Unit
        }
    }

    // ── mic ──────────────────────────────────────────────────────────────────

    fun startListening() {
        if (context.checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            append("jarvis", "Open Jarvis once and allow the microphone."); render(); return
        }
        speaker.stop()
        holo.state = HoloView.State.LISTENING
        mic.text = "STOP"
        voice.start()
    }

    fun stopAll() {
        voice.stop()
        speaker.stop()
        mic.text = "MIC"
        holo.state = HoloView.State.IDLE
    }

    private fun toggleMic() { if (voice.listening) stopAll() else startListening() }

    override fun onPartial(text: String) { input.setText(text); input.setSelection(text.length) }
    override fun onLevel(level: Float) { holo.level = maxOf(holo.level, level) }
    override fun onFinal(text: String) { mic.text = "MIC"; input.setText(""); say(text) }
    override fun onError(message: String) {
        mic.text = "MIC"; holo.state = HoloView.State.IDLE
        append("jarvis", message); render()
    }

    // ── sending ──────────────────────────────────────────────────────────────

    private fun sendTyped() {
        val t = input.text.toString().trim()
        if (t.isNotEmpty()) { input.setText(""); say(t) }
    }

    private fun say(text: String) {
        if (Hub.send(text)) {
            awaitingReply = true
            holo.state = HoloView.State.THINKING
        } else {
            append("jarvis", "Not connected to your PC."); render()
        }
    }

    // ── the log ──────────────────────────────────────────────────────────────

    private fun append(who: String, text: String) {
        lines.append(if (who == "user") "YOU   " else "JARVIS   ").append(text).append("\n\n")
    }

    private fun render() {
        log.text = lines.toString().trimEnd()
        scroll.post { scroll.fullScroll(ScrollView.FOCUS_DOWN) }
    }
}
