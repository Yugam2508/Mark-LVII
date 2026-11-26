package app.jarvis.assistant

/**
 * Sends the microphone to the PC only while someone is talking, so an always-listening phone doesn't
 * stream silence all day (about 110 MB an hour of mobile data otherwise).
 *
 * It keeps the last few hundred milliseconds before speech starts (so the first word isn't clipped),
 * opens when the sound rises clearly above the room's own noise level, and stays open for a while after
 * the last word so the PC hears the pause that ends a sentence. Plain logic, no Android types: unit-tested.
 */
class SpeechGate(
    private val preRollFrames: Int = 8,      // 8 x 40 ms = 320 ms kept from before the first word
    private val hangFrames: Int = 45,        // ~1.8 s of quiet sent after the last word
    private val minLevel: Float = 0.012f,    // never treat anything quieter than this as speech
    private val overFloor: Float = 2.5f,     // speech is this many times louder than the room
) {
    private val pre = ArrayDeque<ByteArray>()
    private var floor = 0.01f
    private var quiet = 0
    var open = false
        private set

    /** The frames to send now for this 40 ms frame and its loudness (0..1). Often none. */
    fun feed(frame: ByteArray, level: Float): List<ByteArray> {
        // The room's noise level: follows quiet moments quickly, loud ones only slowly.
        floor = if (level < floor) floor * 0.6f + level * 0.4f else floor * 0.998f + level * 0.002f
        val speech = level > maxOf(floor * overFloor, minLevel)
        if (open) {
            if (speech) quiet = 0 else quiet++
            if (quiet > hangFrames) { open = false; quiet = 0; pre.clear() }
            return listOf(frame)
        }
        if (speech) {
            open = true
            quiet = 0
            val out = ArrayList<ByteArray>(pre.size + 1)
            out.addAll(pre); out.add(frame)
            pre.clear()
            return out
        }
        pre.addLast(frame)
        while (pre.size > preRollFrames) pre.removeFirst()
        return emptyList()
    }

    /** Let everything through for a while (e.g. right after Jarvis asks a question). */
    fun hold() { open = true; quiet = 0 }
}
