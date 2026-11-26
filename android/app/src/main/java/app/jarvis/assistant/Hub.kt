package app.jarvis.assistant

import android.content.Context
import android.os.Build
import android.os.Handler
import android.os.Looper
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.io.IOException
import java.util.concurrent.CopyOnWriteArraySet
import java.util.concurrent.TimeUnit

/**
 * The link to the Jarvis PC. One instance for the whole app, so the main screen and the
 * assistant overlay share a single connection and a single history.
 *
 * Traffic is plain HTTP/WS because the PC's dashboard speaks plain HTTP on port 8000. It is
 * meant to travel inside Tailscale, which is encrypted end to end (WireGuard).
 */
object Hub {
    interface Listener {
        fun onEvent(event: Protocol.Event)
        fun onConnection(connected: Boolean, detail: String)
    }

    private val JSON = "application/json".toMediaType()
    private val http = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .pingInterval(25, TimeUnit.SECONDS)
        .build()
    private val main = Handler(Looper.getMainLooper())
    private val listeners = CopyOnWriteArraySet<Listener>()

    private var socket: WebSocket? = null
    private var wantConnected = false
    private var retry = 2000L
    private var prefs: Prefs? = null
    private var appContext: Context? = null
    private val worker = java.util.concurrent.Executors.newSingleThreadExecutor()

    /** The last lines of conversation, so a screen that opens late is not blank. */
    val history = ArrayDeque<Protocol.Event.Said>()

    @Volatile var connected = false
        private set

    fun add(l: Listener) { listeners.add(l); l.onConnection(connected, if (connected) "Connected" else "Not connected") }
    fun remove(l: Listener) { listeners.remove(l) }

    private fun emitConnection(ok: Boolean, detail: String) {
        connected = ok
        main.post { listeners.forEach { it.onConnection(ok, detail) } }
    }

    private fun emit(e: Protocol.Event) {
        if (e is Protocol.Event.Said) {
            history.addLast(e)
            while (history.size > 60) history.removeFirst()
        }
        main.post { listeners.forEach { it.onEvent(e) } }
    }

    /** The shared HTTP client (the audio socket uses it too). */
    val client: OkHttpClient get() = http

    /** A fresh session token for this paired phone, or null (unreachable, or the PC forgot the phone). */
    fun freshToken(context: Context, done: (String?) -> Unit) {
        val p = Prefs(context)
        if (!p.paired) { done(null); return }
        val login = Request.Builder().url("${p.baseUrl}/api/device-login")
            .post("""{"device_token":"${p.deviceToken}"}""".toRequestBody(JSON)).build()
        http.newCall(login).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) = done(null)
            override fun onResponse(call: Call, response: Response) {
                done(Protocol.parseAuth(response.body?.string().orEmpty()).token)
            }
        })
    }

    // ── pairing ──────────────────────────────────────────────────────────────

    /** Trade the one-time key shown on the PC for a durable device token. */
    fun pair(context: Context, baseUrl: String, key: String, done: (Boolean, String) -> Unit) {
        val req = Request.Builder().url("$baseUrl/api/pair")
            .post(Protocol.pairBody(key, Build.MODEL).toRequestBody(JSON)).build()
        http.newCall(req).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                main.post { done(false, "Couldn't reach the PC at $baseUrl. Is Tailscale on, and Jarvis running?") }
            }

            override fun onResponse(call: Call, response: Response) {
                val reply = Protocol.parseAuth(response.body?.string().orEmpty())
                if (reply.ok && reply.deviceToken != null) {
                    val p = Prefs(context)
                    p.baseUrl = baseUrl
                    p.deviceToken = reply.deviceToken
                    main.post { done(true, "Paired") }
                } else {
                    main.post { done(false, reply.error ?: "The PC refused the key") }
                }
            }
        })
    }

    // ── connection ───────────────────────────────────────────────────────────

    fun connect(context: Context) {
        appContext = context.applicationContext
        prefs = Prefs(context)
        if (prefs?.paired != true) { emitConnection(false, "Not paired yet"); return }
        if (wantConnected && socket != null) return
        wantConnected = true
        openSocket()
    }

    fun disconnect() {
        wantConnected = false
        socket?.close(1000, "bye")
        socket = null
        emitConnection(false, "Disconnected")
    }

    private fun openSocket() {
        val p = prefs ?: return
        val login = Request.Builder().url("${p.baseUrl}/api/device-login")
            .post("""{"device_token":"${p.deviceToken}"}""".toRequestBody(JSON)).build()
        http.newCall(login).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) = scheduleRetry("Can't reach the PC")

            override fun onResponse(call: Call, response: Response) {
                val body = response.body?.string().orEmpty()
                if (response.code == 401) {
                    // The PC says it doesn't know this phone (revoked, or an older Jarvis that
                    // forgot paired phones when it restarted): pair again with a new key.
                    wantConnected = false
                    p.forgetDevice()
                    emitConnection(false, "The PC no longer knows this phone. Press Remote Control on it and enter the new key.")
                    return
                }
                val reply = Protocol.parseAuth(body)
                if (!reply.ok || reply.token == null) { scheduleRetry("Login failed"); return }
                socket = http.newWebSocket(
                    Request.Builder().url(Protocol.wsUrl(p.baseUrl, reply.token)).build(),
                    object : WebSocketListener() {
                        override fun onOpen(webSocket: WebSocket, response: Response) {
                            retry = 2000L
                            emitConnection(true, "Connected")
                            // Tell the PC this phone is here and what it can do.
                            webSocket.send(Protocol.helloBody(Build.MODEL, PhoneActions.abilities))
                        }

                        override fun onMessage(webSocket: WebSocket, text: String) {
                            val e = Protocol.parseEvent(text) ?: return
                            if (e is Protocol.Event.PhoneAction) handle(webSocket, e) else emit(e)
                        }

                        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                            socket = null; scheduleRetry("Connection closed")
                        }

                        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                            socket = null; scheduleRetry("Connection lost")
                        }
                    })
            }
        })
    }

    /** The PC asked this phone to do something: do it off the main thread and answer. */
    private fun handle(ws: WebSocket, a: Protocol.Event.PhoneAction) {
        val ctx = appContext ?: return
        worker.execute {
            val r = PhoneActions.run(ctx, a.action, a.args)
            ws.send(Protocol.resultBody(a.id, r.ok, r.text, r.data))
        }
    }

    private fun scheduleRetry(why: String) {
        emitConnection(false, why)
        if (!wantConnected) return
        main.postDelayed({ if (wantConnected && socket == null) openSocket() }, retry)
        retry = (retry * 2).coerceAtMost(30_000L)
    }

    // ── sending ──────────────────────────────────────────────────────────────

    /** A raw JSON message for the PC (a notification that just arrived). False when not connected. */
    fun sendRaw(json: String): Boolean {
        val s = socket ?: return false
        return connected && s.send(json)
    }

    /** Say something to Jarvis as text. Returns false when there is no connection. */
    fun send(text: String): Boolean {
        val s = socket ?: return false
        if (!connected) return false
        return s.send(Protocol.commandBody(text))
    }
}
