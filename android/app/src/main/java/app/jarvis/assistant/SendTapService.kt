package app.jarvis.assistant

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

/**
 * Jarvis's hands on the phone, used only when you ask: read what is on the screen, tap a button by its words,
 * scroll, type into the box in focus, go back / home / recents / notifications, take a screenshot, lock the
 * phone; and press WhatsApp's Send right after Jarvis opened a chat with a message you confirmed. Nothing it
 * sees is kept: a request reads the screen once and answers. Switched on in Settings > Accessibility.
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

        /** The words on screen now (buttons, labels, text), top to bottom; null when the service is off. */
        fun screenText(limit: Int = 2500): String? {
            val svc = instance ?: return null
            val root = svc.rootInActiveWindow ?: return ""
            val out = LinkedHashSet<String>()
            fun walk(n: AccessibilityNodeInfo?, depth: Int) {
                if (n == null || depth > 40 || out.sumOf { it.length } > limit) return
                if (n.isVisibleToUser) {
                    val t = (n.text ?: n.contentDescription)?.toString()?.trim()
                    if (!t.isNullOrEmpty()) out.add(if (n.isClickable) "[$t]" else t)
                }
                for (i in 0 until n.childCount) walk(n.getChild(i), depth + 1)
            }
            walk(root, 0)
            val app = root.packageName?.toString() ?: ""
            return "app: $app\n" + out.joinToString("\n").take(limit)
        }

        /** Tap the button or item whose words match (exact first, then contains). */
        fun tap(words: String): String {
            val svc = instance ?: return "off"
            val root = svc.rootInActiveWindow ?: return "nothing on screen"
            val want = words.trim().lowercase()
            val hits = root.findAccessibilityNodeInfosByText(words.trim()).filter { it.isVisibleToUser }
            val pick = hits.firstOrNull { (it.text ?: it.contentDescription)?.toString()?.trim()?.lowercase() == want }
                ?: hits.firstOrNull() ?: return "no \"$words\" on screen"
            var n: AccessibilityNodeInfo? = pick
            var hops = 0
            while (n != null && !n.isClickable && hops < 6) { n = n.parent; hops++ }
            return if (n != null && n.performAction(AccessibilityNodeInfo.ACTION_CLICK)) "tapped" else "couldn't tap it"
        }

        fun scroll(forward: Boolean): String {
            val svc = instance ?: return "off"
            val root = svc.rootInActiveWindow ?: return "nothing on screen"
            val queue = ArrayDeque<AccessibilityNodeInfo>()
            queue.add(root)
            var seen = 0
            while (queue.isNotEmpty() && seen < 400) {
                val n = queue.removeFirst(); seen++
                if (n.isScrollable && n.isVisibleToUser) {
                    val act = if (forward) AccessibilityNodeInfo.ACTION_SCROLL_FORWARD else AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
                    return if (n.performAction(act)) "scrolled" else "can't scroll further"
                }
                for (i in 0 until n.childCount) n.getChild(i)?.let { queue.add(it) }
            }
            return "nothing to scroll"
        }

        fun type(text: String): String {
            val svc = instance ?: return "off"
            val root = svc.rootInActiveWindow ?: return "nothing on screen"
            var box = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
            if (box == null || !box.isEditable) {
                val queue = ArrayDeque<AccessibilityNodeInfo>(); queue.add(root)
                while (queue.isNotEmpty() && box == null) {
                    val n = queue.removeFirst()
                    if (n.isEditable && n.isVisibleToUser) box = n
                    for (i in 0 until n.childCount) n.getChild(i)?.let { queue.add(it) }
                }
            }
            val target = box ?: return "no text box on screen"
            val args = android.os.Bundle().apply {
                putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
            }
            return if (target.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)) "typed" else "couldn't type there"
        }

        /** Phone-wide actions only an accessibility service may take: a screenshot, locking the screen. */
        fun global(action: Int): Boolean = instance?.performGlobalAction(action) == true
        @Volatile private var armedUntil = 0L
        /** Called just before opening a confirmed chat: the next WhatsApp window may have Send pressed. */
        fun arm(seconds: Int = 15) { armedUntil = System.currentTimeMillis() + seconds * 1000L }
        fun armedNow() = System.currentTimeMillis() < armedUntil
    }
}
