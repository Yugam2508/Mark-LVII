package app.jarvis.assistant

import android.content.Context
import android.graphics.Color
import android.text.InputType
import android.view.Gravity
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/**
 * The conversation screen, built in code so the same panel is the app's main screen AND the overlay
 * that opens when Jarvis is the phone's assistant (long-press power).
 *
 * The microphone is open (see LiveAudio): just talk. Jarvis's voice plays here, the same voice as on the
 * PC. Everything said and everything Jarvis shows on the PC (cards, notices) is listed below the display.
 */
class ConversationPanel(
    context: Context,
    private val listenOnShow: Boolean = false,
    /** Called when the PC no longer knows this phone, so the app can go back to the connect screen. */
    private val onUnpaired: (() -> Unit)? = null,
) : LinearLayout(context), Hub.Listener, LiveAudio.Listener {

    private val prefs = Prefs(context)
    private val holo = HoloView(context)
    private val status = TextView(context)
    private val log = TextView(context)
    private val scroll = ScrollView(context)
    private val input = EditText(context)
    private val mic = Button(context)
    private val lines = StringBuilder()

    init {
        orientation = VERTICAL
        setBackgroundColor(Color.rgb(2, 8, 12))
        setPadding(dp(14), dp(10), dp(14), dp(10))

        status.setTextColor(Color.rgb(90, 140, 160)); status.textSize = 12f; status.gravity = Gravity.CENTER
        val top = LinearLayout(context).apply { orientation = HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        top.addView(status, LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f))
        // Every switch lives behind this button (phones have no menu key). Not in the assistant overlay.
        (context as? MainActivity)?.let { act ->
            top.addView(Button(context).apply {
                text = "⋮"; textSize = 20f; setBackgroundColor(Color.TRANSPARENT); setTextColor(Color.rgb(0, 212, 255))
                contentDescription = "Permissions and setup"
                setOnClickListener { act.showSetup() }
            }, LayoutParams(dp(48), dp(48)))
        }
        addView(top, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))
        addView(holo, LayoutParams(LayoutParams.MATCH_PARENT, 0, 1.3f))

        log.setTextColor(Color.rgb(220, 235, 245)); log.textSize = 15f
        scroll.addView(log)
        addView(scroll, LayoutParams(LayoutParams.MATCH_PARENT, 0, 1f))

        val row = LinearLayout(context).apply { orientation = HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        input.hint = "Just talk, or type here"; input.setHintTextColor(Color.rgb(80, 110, 125))
        input.setTextColor(Color.WHITE); input.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
        input.imeOptions = EditorInfo.IME_ACTION_SEND; input.maxLines = 3
        input.setOnEditorActionListener { _, _, _ -> sendTyped(); true }
        row.addView(input, LayoutParams(0, LayoutParams.WRAP_CONTENT, 1f))
        mic.setOnClickListener { toggleMic() }
        row.addView(mic, LayoutParams(LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT))
        addView(row, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))

        Hub.history.forEach { append(it.speaker, it.text) }
        render()
        refreshMic()
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        Hub.add(this)
        Hub.connect(context)
        LiveAudio.add(this)
        // Listening is the default: the app and the assistant overlay both open the microphone.
        if (prefs.openMic || listenOnShow) LinkService.start(context, listen = true)
    }

    override fun onDetachedFromWindow() {
        Hub.remove(this)
        LiveAudio.remove(this)
        super.onDetachedFromWindow()
    }

    // ── Hub ──────────────────────────────────────────────────────────────────

    override fun onConnection(connected: Boolean, detail: String) {
        if (!connected && !prefs.paired) onUnpaired?.let { post(it) }
        status.text = if (connected) "● connected to your PC" else "○ $detail"
        status.setTextColor(if (connected) Color.rgb(0, 255, 136) else Color.rgb(255, 160, 60))
    }

    override fun onEvent(event: Protocol.Event) {
        when (event) {
            is Protocol.Event.Said -> { append(event.speaker, event.text); render() }
            is Protocol.Event.Card -> {
                lines.append("▣ ").append(event.title.uppercase())
                if (event.text.isNotEmpty()) lines.append("\n").append(event.text)
                lines.append("\n\n"); render()
            }
            is Protocol.Event.System, is Protocol.Event.Status, is Protocol.Event.PhoneAction -> Unit
        }
    }

    // ── the voice ────────────────────────────────────────────────────────────

    override fun onState(state: LiveAudio.State, level: Float) {
        holo.state = when (state) {
            LiveAudio.State.LISTENING -> if (LiveAudio.muted) HoloView.State.IDLE else HoloView.State.LISTENING
            LiveAudio.State.SPEAKING -> HoloView.State.SPEAKING
            LiveAudio.State.CONNECTING -> HoloView.State.THINKING
            LiveAudio.State.OFF -> HoloView.State.IDLE
        }
        holo.level = maxOf(holo.level, level)
        refreshMic()
    }

    private fun refreshMic() {
        mic.text = when {
            !LiveAudio.running -> "LISTEN"
            LiveAudio.muted -> "UNMUTE"
            else -> "MUTE"
        }
    }

    /** LISTEN starts the open microphone; MUTE/UNMUTE pauses sending without hanging up. */
    private fun toggleMic() {
        when {
            !LiveAudio.running -> { prefs.openMic = true; LinkService.start(context, listen = true) }
            else -> { LiveAudio.muted = !LiveAudio.muted; refreshMic(); onState(LiveAudio.state, 0f) }
        }
    }

    fun startListening() { if (!LiveAudio.running) LinkService.start(context, listen = true) }

    /** The assistant overlay was dismissed: stop talking, but leave the link up. */
    fun stopAll() { /* the microphone stays open in the background service until you stop it */ }

    // ── typing ───────────────────────────────────────────────────────────────

    private fun sendTyped() {
        val t = input.text.toString().trim()
        if (t.isEmpty()) return
        input.setText("")
        if (Hub.send(t)) holo.state = HoloView.State.THINKING else { append("jarvis", "Not connected to your PC."); render() }
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
