package app.jarvis.assistant

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ProtocolTest {
    @Test fun qrLinkGivesAddressAndKey() {
        val p = Protocol.parseAddress("http://100.89.195.89:8000/auto-login?key=abcd1234")!!
        assertEquals("http://100.89.195.89:8000", p.baseUrl)
        assertEquals("ABCD1234", p.key)
    }

    @Test fun bareAddressesGetSchemeAndPort() {
        assertEquals("http://100.89.195.89:8000", Protocol.parseAddress("100.89.195.89")!!.baseUrl)
        assertEquals("http://laptop.tail1234.ts.net:8000", Protocol.parseAddress(" laptop.tail1234.ts.net ")!!.baseUrl)
        assertEquals("http://10.0.0.5:9000", Protocol.parseAddress("10.0.0.5:9000/")!!.baseUrl)
        assertEquals("https://g14.tail1234.ts.net:8000", Protocol.parseAddress("https://g14.tail1234.ts.net")!!.baseUrl)
        assertNull(Protocol.parseAddress("   "))
        assertNull(Protocol.parseAddress("not an address"))
    }

    @Test fun keyShape() {
        assertTrue(Protocol.isKey("ABCD1234")); assertTrue(Protocol.isKey(" abcd1234 "))
        assertFalse(Protocol.isKey("ABC")); assertFalse(Protocol.isKey("ABCD-123"))
    }

    @Test fun socketAddress() {
        assertEquals("ws://100.1.2.3:8000/ws?token=T", Protocol.wsUrl("http://100.1.2.3:8000", "T"))
        assertEquals("wss://x.ts.net:8000/ws?token=T", Protocol.wsUrl("https://x.ts.net:8000", "T"))
    }

    @Test fun eventsFromThePc() {
        assertEquals(Protocol.Event.Said("jarvis", "Three things today."),
            Protocol.parseEvent("""{"type":"log","speaker":"jarvis","text":" Three things today. ","ts":"x"}"""))
        assertEquals(Protocol.Event.Said("user", "hello"), Protocol.parseEvent("""{"type":"log","speaker":"user","text":"hello"}"""))
        assertEquals(Protocol.Event.System("Paired: phone."), Protocol.parseEvent("""{"type":"sys","text":"Paired: phone."}"""))
        assertEquals(Protocol.Event.Status("sleeping"), Protocol.parseEvent("""{"type":"status","state":"sleeping"}"""))
        assertNull(Protocol.parseEvent("""{"type":"log","speaker":"jarvis","text":"  "}"""))
        assertNull(Protocol.parseEvent("""{"type":"mystery"}"""))
        assertNull(Protocol.parseEvent("not json"))
    }

    @Test fun authReplies() {
        val ok = Protocol.parseAuth("""{"ok":true,"token":"t","device_token":"d"}""")
        assertTrue(ok.ok); assertEquals("t", ok.token); assertEquals("d", ok.deviceToken)
        val bad = Protocol.parseAuth("""{"ok":false,"error":"Invalid or expired key"}""")
        assertFalse(bad.ok); assertEquals("Invalid or expired key", bad.error)
        assertFalse(Protocol.parseAuth("<html>").ok)
    }

    @Test fun bodiesAreValidJson() {
        assertEquals("""{"pin":"ABCD1234","name":"OnePlus 13"}""", Protocol.pairBody(" abcd1234", "OnePlus 13"))
        assertEquals("""{"type":"command","text":"what's \"up\""}""", Protocol.commandBody("what's \"up\""))
    }
}
