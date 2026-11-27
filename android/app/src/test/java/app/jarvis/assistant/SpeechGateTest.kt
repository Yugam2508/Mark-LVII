package app.jarvis.assistant

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SpeechGateTest {
    private fun frame(tag: Int) = ByteArray(4) { tag.toByte() }

    @Test fun silenceSendsNothing() {
        val g = SpeechGate()
        repeat(200) { assertTrue(g.feed(frame(it), 0.003f).isEmpty()) }
        assertFalse(g.open)
    }

    @Test fun speechSendsPreRollThenEverythingUntilTheHangRunsOut() {
        val g = SpeechGate(preRollFrames = 3, hangFrames = 5)
        repeat(50) { g.feed(frame(1), 0.003f) }                  // a quiet room
        val first = g.feed(frame(9), 0.2f)                       // the first word
        assertEquals(4, first.size)                              // 3 frames from before + this one
        assertEquals(9, first.last()[0].toInt())
        assertEquals(1, g.feed(frame(9), 0.15f).size)            // still talking
        var sent = 0
        repeat(5) { sent += g.feed(frame(2), 0.003f).size }      // the pause after a sentence is sent
        assertEquals(5, sent)
        assertTrue(g.open)
        g.feed(frame(2), 0.003f)                                 // hang time over
        assertFalse(g.open)
        assertTrue(g.feed(frame(2), 0.003f).isEmpty())
    }

    @Test fun aNoisyRoomRaisesTheBar() {
        val g = SpeechGate()
        repeat(300) { g.feed(frame(1), 0.03f) }                  // a fan or the TV, steadily
        assertTrue(g.feed(frame(1), 0.035f).isEmpty())          // a little louder than the room: not speech
        assertTrue(g.feed(frame(1), 0.2f).isNotEmpty())         // someone talking: speech
    }
}
