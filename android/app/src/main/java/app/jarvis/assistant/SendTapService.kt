package app.jarvis.assistant

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

/**
 * Taps WhatsApp's Send button, only after Jarvis has just opened a chat with a message the user confirmed
 * on the PC; and, when the user asks, takes a phone screenshot or locks the screen (system actions only an
 * accessibility service may perform). It never reads or stores anything: it looks for the Send button and
 * presses it. The user turns it on in Settings > Accessibility; without it Jarvis still opens the chat with
 * the message typed in and the user taps Send.
 */
class SendTapService : AccessibilityService() {
    override fun onServiceConnected() { enabled = true; instance = this }
    override fun onUnbind(intent: android.content.Intent?): Boolean { enabled = false; instance = null; return super.onUnbind(intent) }
    override fun onInterrupt() {}

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (!armedNow()) return
        val root = rootInActiveWindow ?: return
        val pkg = root.packageName?.toString() ?: return
        if (!pkg.startsWith("com.whatsapp")) return
        val send = find(root)
        if (send != null && send.performAction(AccessibilityNodeInfo.ACTION_CLICK)) armedUntil = 0L
    }

    private fun find(root: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        for (id in listOf("com.whatsapp:id/send", "com.whatsapp.w4b:id/send")) {
            root.findAccessibilityNodeInfosByViewId(id).firstOrNull { it.isEnabled }?.let { return it }
        }
        return root.findAccessibilityNodeInfosByText("Send").firstOrNull { it.isClickable && it.isEnabled }
    }

    companion object {
        @Volatile var enabled = false
        @Volatile var instance: SendTapService? = null

        /** Phone-wide actions only an accessibility service may take: a screenshot, locking the screen. */
        fun global(action: Int): Boolean = instance?.performGlobalAction(action) == true
        @Volatile private var armedUntil = 0L
        /** Called just before opening a confirmed chat: the next WhatsApp window may have Send pressed. */
        fun arm(seconds: Int = 15) { armedUntil = System.currentTimeMillis() + seconds * 1000L }
        fun armedNow() = System.currentTimeMillis() < armedUntil
    }
}
