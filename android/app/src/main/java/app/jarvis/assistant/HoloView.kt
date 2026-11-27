package app.jarvis.assistant

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RadialGradient
import android.graphics.RectF
import android.graphics.Shader
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

    // Living layers, as on the PC: drifting motes with depth, ripples on loud moments, a turning globe.
    private val rnd = java.util.Random(7)
    private val motes = Array(48) { floatArrayOf((rnd.nextFloat() * 6.283f), 0.55f + rnd.nextFloat() * 1.0f,
        0.25f + rnd.nextFloat() * 0.75f, (0.02f + rnd.nextFloat() * 0.07f) * (if (rnd.nextBoolean()) 1 else -1), rnd.nextFloat() * 6.3f) }
    private val ripples = ArrayList<FloatArray>()      // [age, strength]
    private var lastPeak = 0f
    private val glow = Paint(Paint.ANTI_ALIAS_FLAG)

    private val ticker = object : Runnable {
        override fun run() {
            val speed = when (state) { State.THINKING -> 1.6f; State.SPEAKING -> 0.9f; else -> 0.4f }
            phase += 0.016f * speed
            // motes: drawn in while listening, blown out while speaking
            val push = when (state) { State.SPEAKING -> 0.10f + 0.5f * level; State.LISTENING -> -0.06f; else -> 0f }
            for (m in motes) {
                m[0] += m[3] * 0.016f * (if (state == State.THINKING) 2.2f else 1f)
                m[1] += push * 0.016f * (0.4f + m[2])
                m[4] += 0.016f * (1.5f + m[2])
                if (m[1] > 1.6f) m[1] = 0.55f else if (m[1] < 0.5f) m[1] = 1.55f
            }
            if (level > 0.35f && level > lastPeak * 1.25f && (ripples.isEmpty() || ripples.last()[0] > 0.35f))
                ripples.add(floatArrayOf(0f, level.coerceAtMost(1f)))
            lastPeak = maxOf(level, lastPeak * 0.92f)
            for (r in ripples) r[0] += 0.016f
            ripples.removeAll { it[0] > 1.6f }
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

        // soft glow behind everything, brighter with the voice
        glow.shader = RadialGradient(cx, cy, r * 1.2f, intArrayOf(Color.argb((40 + 70 * level).toInt().coerceIn(0, 255),
            Color.red(acc), Color.green(acc), Color.blue(acc)), Color.argb(0, Color.red(acc), Color.green(acc), Color.blue(acc))),
            floatArrayOf(0f, 1f), Shader.TileMode.CLAMP)
        c.drawCircle(cx, cy, r * 1.2f, glow)
        // motes
        for (m in motes) {
            val tw = 0.55f + 0.45f * sin(m[4])
            fill.color = if (state == State.SPEAKING || state == State.LISTENING) acc else main
            fill.alpha = ((0.10f + 0.45f * m[2]) * tw * 255).toInt().coerceIn(0, 255)
            c.drawCircle(cx + cos(m[0]) * m[1] * r, cy + sin(m[0]) * m[1] * r * 0.85f, 1.2f + 2.2f * m[2], fill)
        }
        // ripples leaving the core on loud moments
        for (rp in ripples) {
            val k = rp[0] / 1.6f
            stroke.color = acc; stroke.strokeWidth = 2f; stroke.alpha = ((1 - k) * 140 * rp[1]).toInt().coerceIn(0, 255)
            c.drawCircle(cx, cy, r * (0.40f + 0.75f * k), stroke)
        }

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
        // core, with a wireframe globe turning inside it
        fill.color = acc; fill.alpha = (50 + 90 * level).toInt().coerceIn(0, 255)
        c.drawCircle(cx, cy, r * 0.36f, fill)
        drawGlobe(c, cx, cy, r * 0.33f, main)
        stroke.color = main; stroke.strokeWidth = 2f; stroke.alpha = 200
        c.drawCircle(cx, cy, r * 0.36f, stroke)
        text.textSize = r * 0.14f
        c.drawText(label, cx, cy + text.textSize * 0.35f, text)
    }

    private fun drawGlobe(c: Canvas, cx: Float, cy: Float, R: Float, main: Int) {
        val yaw = phase * 0.9f
        val tilt = 0.38f
        val ct = cos(tilt); val st = sin(tilt)
        fun line(lat1: Float, lon1: Float, lat2: Float, lon2: Float) {
            val x1 = cos(lat1) * sin(lon1); val y1 = sin(lat1); val z1 = cos(lat1) * cos(lon1)
            val x2 = cos(lat2) * sin(lon2); val y2 = sin(lat2); val z2 = cos(lat2) * cos(lon2)
            val yy1 = y1 * ct - z1 * st; val zz1 = y1 * st + z1 * ct
            val yy2 = y2 * ct - z2 * st; val zz2 = y2 * st + z2 * ct
            val front = (zz1 + zz2) / 2f
            stroke.color = main; stroke.strokeWidth = 1.2f
            stroke.alpha = ((0.08f + 0.25f * maxOf(0f, front)) * 255).toInt()
            c.drawLine(cx + x1 * R, cy + yy1 * R, cx + x2 * R, cy + yy2 * R, stroke)
        }
        val pi = Math.PI.toFloat()
        for (k in 0 until 8) {                                     // meridians
            val lon = yaw + k * pi / 8
            for (i in 0 until 16) line(-pi / 2 + i * pi / 16, lon, -pi / 2 + (i + 1) * pi / 16, lon)
        }
        for (latDeg in intArrayOf(-60, -30, 0, 30, 60)) {          // parallels
            val lat = latDeg * pi / 180f
            for (i in 0 until 28) line(lat, yaw + i * 2 * pi / 28, lat, yaw + (i + 1) * 2 * pi / 28)
        }
    }
}
