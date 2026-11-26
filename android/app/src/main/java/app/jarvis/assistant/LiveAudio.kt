package app.jarvis.assistant

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.NoiseSuppressor
import android.os.Build
import android.os.Handler
import android.os.Looper
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import java.util.concurrent.CopyOnWriteArraySet
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit

/**
 * The phone as Jarvis's microphone and speaker.
 *
 * Your voice goes up to the PC's Jarvis (the same brain, memory and voice as on the PC) and its
 * voice comes back down and plays here, so there is one Jarvis answering, not two. The microphone
 * is open all the time (no button); the phone's own echo cancellation lets you talk over Jarvis.
 * The PC mutes its own speakers and microphone while the phone is doing this.
 */
object LiveAudio {
    enum class State { OFF, CONNECTING, LISTENING, SPEAKING }

    interface Listener { fun onState(state: State, level: Float) }

    private const val IN_RATE = 16000
    private const val OUT_RATE = 24000
    private val main = Handler(Looper.getMainLooper())
    private val listeners = CopyOnWriteArraySet<Listener>()

    @Volatile var state = State.OFF
        private set
    @Volatile var muted = false
    /** With the wake word on: true after "Hey Jarvis" until it goes back to waiting. */
    @Volatile var awake = false
        private set
    /** False when the PC has no wake word set up (then everything heard goes through). */
    @Volatile var wakeAvailable = true
        private set
    val wakeMode: Boolean get() = ctx?.let { Prefs(it).wakeWord } == true

    private var socket: WebSocket? = null
    private var record: AudioRecord? = null
    private var track: AudioTrack? = null
    private var captureThread: Thread? = null
    private var playThread: Thread? = null
    private val playQueue = LinkedBlockingQueue<ByteArray>()
    @Volatile private var wanted = false
    @Volatile private var lastVoiceAt = 0L
    private var retry = 2000L
    private var ctx: Context? = null
    private var audio: AudioManager? = null
    private var savedMode = AudioManager.MODE_NORMAL

    fun add(l: Listener) { listeners.add(l); l.onState(state, 0f) }
    fun remove(l: Listener) { listeners.remove(l) }

    private fun emit(s: State, level: Float = 0f) {
        state = s
        main.post { listeners.forEach { it.onState(s, level) } }
    }

    val running: Boolean get() = wanted

    fun start(context: Context) {
        val app = context.applicationContext
        if (wanted) return
        if (app.checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) return
        if (!Prefs(app).paired) return
        ctx = app
        wanted = true
        audio = app.getSystemService(AudioManager::class.java)
        audio?.let {
            savedMode = it.mode
            it.mode = AudioManager.MODE_IN_COMMUNICATION          // enables the phone's echo cancellation path
            route(it)
        }
        connect()
    }

    /** Headphones or a Bluetooth headset when one is connected, else the loudspeaker (never the earpiece). */
    private fun route(am: AudioManager) {
        if (Build.VERSION.SDK_INT >= 31) {
            val prefer = listOf(android.media.AudioDeviceInfo.TYPE_BLE_HEADSET, android.media.AudioDeviceInfo.TYPE_BLUETOOTH_SCO,
                android.media.AudioDeviceInfo.TYPE_WIRED_HEADSET, android.media.AudioDeviceInfo.TYPE_USB_HEADSET,
                android.media.AudioDeviceInfo.TYPE_BUILTIN_SPEAKER)
            val devices = am.availableCommunicationDevices
            val pick = prefer.firstNotNullOfOrNull { t -> devices.firstOrNull { it.type == t } }
            if (pick != null && am.setCommunicationDevice(pick)) return
        }
        @Suppress("DEPRECATION")
        am.isSpeakerphoneOn = !(am.isWiredHeadsetOn || am.isBluetoothScoOn || am.isBluetoothA2dpOn)
    }

    fun stop() {
        wanted = false
        awake = false
        teardown()
        audio?.let {
            if (Build.VERSION.SDK_INT >= 31) it.clearCommunicationDevice()
            @Suppress("DEPRECATION")
            it.isSpeakerphoneOn = false
            it.mode = savedMode
        }
        emit(State.OFF)
    }

    @Volatile private var connecting = false

    private fun connect() {
        val c = ctx ?: return
        if (connecting) return
        connecting = true
        emit(State.CONNECTING)
        Hub.freshToken(c) { token ->
            if (!wanted) { connecting = false; return@freshToken }
            if (token == null) { connecting = false; schedule(); return@freshToken }
            val url = Protocol.audioUrl(Prefs(c).baseUrl, token, Prefs(c).duplex, Prefs(c).wakeWord)
            socket = Hub.client.newWebSocket(Request.Builder().url(url).build(), object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    if (socket != null && socket !== webSocket) { webSocket.close(1000, "replaced"); return }
                    retry = 2000L
                    startPlayback()
                    startCapture(webSocket)
                }

                override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                    if (socket !== webSocket) return
                    lastVoiceAt = System.currentTimeMillis()
                    playQueue.offer(bytes.toByteArray())
                }

                override fun onMessage(webSocket: WebSocket, text: String) {
                    if (socket === webSocket && text.contains("\"flush\"")) flush()
                }

                // Only the current socket's end matters: an old one closing late must not stop the new one.
                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) { if (socket == null || socket === webSocket) dropped() }
                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) { if (socket == null || socket === webSocket) dropped() }
            })
            connecting = false
        }
    }

    private fun dropped() {
        teardown()
        if (wanted) schedule()
    }

    private fun schedule() {
        emit(State.CONNECTING)
        main.postDelayed({ if (wanted && socket == null) connect() }, retry)
        retry = (retry * 2).coerceAtMost(30_000L)
    }

    private fun teardown() {
        socket?.close(1000, "bye"); socket = null
        try { record?.stop() } catch (e: Exception) { }
        record?.release(); record = null
        captureThread?.interrupt(); captureThread = null
        try { track?.stop() } catch (e: Exception) { }
        track?.release(); track = null
        playThread?.interrupt(); playThread = null
        playQueue.clear()
    }

    // ── microphone → PC ──────────────────────────────────────────────────────

    private fun startCapture(ws: WebSocket) {
        val minBuf = AudioRecord.getMinBufferSize(IN_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val rec = try {
            AudioRecord(MediaRecorder.AudioSource.VOICE_COMMUNICATION, IN_RATE, AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT, maxOf(minBuf, 4096) * 2)
        } catch (e: SecurityException) { return }
        if (rec.state != AudioRecord.STATE_INITIALIZED) { rec.release(); return }
        if (AcousticEchoCanceler.isAvailable()) AcousticEchoCanceler.create(rec.audioSessionId)?.enabled = true
        if (NoiseSuppressor.isAvailable()) NoiseSuppressor.create(rec.audioSessionId)?.enabled = true
        record = rec
        rec.startRecording()
        emit(State.LISTENING)
        val gate = if (ctx?.let { Prefs(it).saveData } != false) SpeechGate() else null
        captureThread = Thread {
            val buf = ByteArray(IN_RATE / 1000 * 2 * 40)                // 40 ms frames
            while (wanted && !Thread.currentThread().isInterrupted) {
                val n = rec.read(buf, 0, buf.size)
                if (n <= 0) break
                val level = Protocol.rms(buf, n)
                if (!muted && socket === ws) {
                    val frame = buf.copyOf(n)
                    // While Jarvis is talking, keep the line open so you can interrupt it.
                    if (gate != null && System.currentTimeMillis() - lastVoiceAt < 400) gate.hold()
                    val out = gate?.feed(frame, level) ?: listOf(frame)
                    for (f in out) ws.send(ByteString.of(*f))
                }
                val speaking = System.currentTimeMillis() - lastVoiceAt < 400
                emit(if (speaking) State.SPEAKING else State.LISTENING, if (speaking) 0.6f else (level * 4f).coerceAtMost(1f))
            }
        }.apply { name = "jarvis-capture"; isDaemon = true; start() }
    }

    // ── PC → speaker ─────────────────────────────────────────────────────────

    private fun startPlayback() {
        val minBuf = AudioTrack.getMinBufferSize(OUT_RATE, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val t = AudioTrack.Builder()
            .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            .setAudioFormat(AudioFormat.Builder().setSampleRate(OUT_RATE).setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                .setEncoding(AudioFormat.ENCODING_PCM_16BIT).build())
            .setTransferMode(AudioTrack.MODE_STREAM)
            .setBufferSizeInBytes(maxOf(minBuf, OUT_RATE / 2) * 2)        // about a second of cushion for network jitter
            .build()
        track = t
        t.play()
        playThread = Thread {
            while (wanted && !Thread.currentThread().isInterrupted) {
                val chunk = try { playQueue.poll(200, TimeUnit.MILLISECONDS) } catch (e: InterruptedException) { break } ?: continue
                t.write(chunk, 0, chunk.size)
            }
        }.apply { name = "jarvis-play"; isDaemon = true; start() }
    }

    /** The PC heard "Hey Jarvis" (or went back to waiting): chime, buzz, and show it. */
    fun onWake(nowAwake: Boolean, available: Boolean) {
        val was = awake
        awake = nowAwake
        wakeAvailable = available
        if (nowAwake && !was) cue()
        emit(state)
    }

    /** Tap on the orb: wake Jarvis without saying the phrase. */
    fun wakeNow() { socket?.send("""{"type":"wake_now"}""") }
    fun sleepNow() { socket?.send("""{"type":"sleep_now"}""") }

    /** Tap while Jarvis is talking: silence the speaker here at once and tell the PC to stop. */
    fun interruptNow() {
        flush()
        lastVoiceAt = 0L
        socket?.send("""{"type":"interrupt"}""")
        emit(State.LISTENING)
    }

    private fun cue() {
        val c = ctx ?: return
        if (!Prefs(c).chime) return
        try {
            android.media.ToneGenerator(AudioManager.STREAM_VOICE_CALL, 60)
                .startTone(android.media.ToneGenerator.TONE_PROP_ACK, 120)
        } catch (e: Exception) { }
        try {
            val v = if (Build.VERSION.SDK_INT >= 31) c.getSystemService(android.os.VibratorManager::class.java)?.defaultVibrator
                else @Suppress("DEPRECATION") c.getSystemService(android.os.Vibrator::class.java)
            v?.vibrate(android.os.VibrationEffect.createOneShot(35, android.os.VibrationEffect.DEFAULT_AMPLITUDE))
        } catch (e: Exception) { }
    }

    /** Jarvis was interrupted: drop everything queued and whatever the speaker still holds. */
    private fun flush() {
        playQueue.clear()
        val t = track ?: return
        try { t.pause(); t.flush(); t.play() } catch (e: Exception) { }
    }
}
