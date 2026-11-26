package app.jarvis.assistant

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.view.View
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin

/**
 * The phone's version of the holographic display: turning rings in the colour of what Jarvis
 * is doing, a ring of bars that moves with the voice, and the name in the middle.
 */
class HoloView(context: Context) : View(context) {
    enum class State { IDLE, LISTENING, THINKING, SPEAKING }

    var state: State = State.IDLE
    /** 0..1, how loud the voice is right now. */
    var level: Float = 0f
    var label: String = "JARVIS"

    private var phase = 0f
    private val stroke = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeCap = Paint.Cap.BUTT }
    private val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }
    private val text = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE; textAlign = Paint.Align.CENTER; letterSpacing = 0.25f; isFakeBoldText = true
    }
    private val rect = RectF()

    private val ticker = object : Runnable {
        override fun run() {
            val speed = when (state) { State.THINKING -> 1.6f; State.SPEAKING -> 0.9f; else -> 0.4f }
            phase += 0.016f * speed
            level *= 0.92f
            invalidate()
            postOnAnimation(this)
        }
    }

    override fun onAttachedToWindow() { super.onAttachedToWindow(); postOnAnimation(ticker) }
    override fun onDetachedFromWindow() { removeCallbacks(ticker); super.onDetachedFromWindow() }

    private fun accent(): Int = when (state) {
        State.LISTENING -> Color.rgb(0, 255, 136)
        State.THINKING -> Color.rgb(255, 196, 0)
        State.SPEAKING -> Color.rgb(255, 106, 0)
        State.IDLE -> Color.rgb(0, 212, 255)
    }

    override fun onDraw(c: Canvas) {
        val cx = width / 2f
        val cy = height / 2f
        val r = min(width, height) * 0.42f
        val main = Color.rgb(0, 212, 255)
        val acc = accent()

        // outer tick dial
        stroke.color = main; stroke.strokeWidth = 2f; stroke.alpha = 150
        for (i in 0 until 90) {
            val a = (phase * 0.4f + i * (Math.PI * 2 / 90)).toFloat()
            val long = i % 10 == 0
            val r0 = r * (if (long) 0.93f else 0.97f)
            c.drawLine(cx + cos(a) * r0, cy + sin(a) * r0, cx + cos(a) * r * 1.02f, cy + sin(a) * r * 1.02f, stroke)
        }
        // turning arcs in the state colour
        stroke.color = acc; stroke.alpha = 230; stroke.strokeWidth = 7f
        rect.set(cx - r * 0.84f, cy - r * 0.84f, cx + r * 0.84f, cy + r * 0.84f)
        val base = -phase * 70f
        c.drawArc(rect, base, 96f, false, stroke)
        c.drawArc(rect, base + 130f, 58f, false, stroke)
        stroke.strokeWidth = 3f; stroke.alpha = 150
        c.drawArc(rect, base + 215f, 120f, false, stroke)
        // voice spectrum
        val live = state == State.SPEAKING || state == State.LISTENING
        for (i in 0 until 60) {
            val a = (-Math.PI / 2 + i * (Math.PI * 2 / 60)).toFloat()
            val wob = (0.5f + 0.5f * sin(phase * 9f + i * 0.9f)) * (0.6f + 0.4f * sin(phase * 3f + i * 2.3f))
            val h = 2f + (if (live) level * wob * r * 0.22f else 0f)
            val r0 = r * 0.50f
            stroke.color = if (h > 6f) acc else main; stroke.alpha = 200; stroke.strokeWidth = 3f
            c.drawLine(cx + cos(a) * r0, cy + sin(a) * r0, cx + cos(a) * (r0 + h), cy + sin(a) * (r0 + h), stroke)
        }
        // core
        fill.color = acc; fill.alpha = (50 + 90 * level).toInt().coerceIn(0, 255)
        c.drawCircle(cx, cy, r * 0.36f, fill)
        stroke.color = main; stroke.strokeWidth = 2f; stroke.alpha = 200
        c.drawCircle(cx, cy, r * 0.36f, stroke)
        text.textSize = r * 0.14f
        c.drawText(label, cx, cy + text.textSize * 0.35f, text)
    }
}
