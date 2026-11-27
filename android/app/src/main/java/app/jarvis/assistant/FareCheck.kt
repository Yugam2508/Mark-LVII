package app.jarvis.assistant

import android.content.Context
import android.content.Intent
import android.graphics.Rect
import android.os.Bundle
import android.view.accessibility.AccessibilityNodeInfo
import org.json.JSONArray
import org.json.JSONObject

/**
 * "What's the cheapest cab to Changi?" — the phone half. Grab, Gojek, TADA and Zig publish no fare API, so
 * Jarvis does what you would: opens the app, types the destination where it asks "Where to?", picks the
 * first matching place, and reads the prices the app quotes (FareParse). Pickup is wherever the app puts
 * it, which is your current location. It goes through the same accessibility switch as "tap" and
 * "screen_read".
 *
 * IT NEVER BOOKS. It only taps words from the short lists below (a search box, "Not now", "Confirm pickup"),
 * never anything that books, orders, requests or pays, and once a price is on screen it taps nothing at
 * all. With leave_open it stops on the fares screen so you can press Book yourself.
 *
 * Each app's screens change with its updates, so every answer carries a trace of what was tapped and, when
 * it gets stuck, the words on screen: paste that back and the lists below are easy to adjust.
 */
object FareCheck {
    class Spec(val name: String, val packages: List<String>, val labels: List<String>, val openers: List<String>)

    /** Package names first; the launcher label is the fallback when an app is renamed or repackaged. */
    val apps = listOf(
        Spec("Grab", listOf("com.grabtaxi.passenger"), listOf("Grab"), listOf("Transport", "Car", "Rides")),
        Spec("Gojek", listOf("com.gojek.app"), listOf("Gojek"), listOf("GoCar", "Car", "Ride")),
        Spec("TADA", listOf("io.mvlchain.tada", "com.mvlchain.tada"), listOf("TADA"), listOf("Ride", "Car", "Taxi")),
        Spec("Zig", listOf("com.codigo.comfort", "com.cdgtaxi.zig", "sg.com.cdgtaxi.zig"), listOf("Zig", "CDG Zig", "ComfortDelGro"),
            listOf("Taxi", "Ride", "Car")),
    )

    /** What a ride app's destination box says before you type. */
    private val whereTo = listOf("Where to?", "Where to", "Where are you going", "Where are you heading", "Where would you like to go",
        "Search destination", "Enter destination", "Search for a destination", "Drop-off", "Drop off", "Going to", "Destination")

    /** Pop-ups in the way: promotions, rating prompts, tips. */
    private val dismiss = listOf("Not now", "Maybe later", "Later", "No thanks", "No, thanks", "Skip", "Close", "Dismiss", "Got it")

    /** On the fares screen a "Close" or "Dismiss" may well be the fares sheet itself, so only these. */
    private val softDismiss = listOf("Not now", "Maybe later", "No thanks", "No, thanks", "Got it")

    /** Steps between picking the place and seeing prices. */
    private val advance = listOf("Confirm pickup", "Confirm pick-up", "Confirm pickup point", "Choose this pickup", "Use this pickup",
        "Set pickup", "Confirm destination", "Choose this destination", "Done")

    /** Whatever the lists say, a tap whose words match this never happens. */
    private val neverTap = Regex("""\b(book|order|request|pay|checkout|check out|buy|call|subscribe|confirm booking|schedule)\b""",
        RegexOption.IGNORE_CASE)

    /** Places that are not the place: links to a map picker or saved places. */
    private val notAPlace = Regex("""\b(on map|on the map|saved places?|add home|add work|current location|set location|recent)\b""",
        RegexOption.IGNORE_CASE)

    private val accessHint = "That needs Jarvis switched on in Accessibility: open Jarvis → ⋮ → Permissions & setup → the Accessibility line"

    fun spec(name: String): Spec? {
        val want = name.trim().lowercase()
        return apps.firstOrNull { it.name.lowercase() == want || it.labels.any { l -> l.lowercase() == want } }
            ?: apps.firstOrNull { it.name.lowercase().contains(want) || want.contains(it.name.lowercase()) }
    }

    /** The installed package for this app, or null. */
    fun installed(context: Context, s: Spec): String? {
        val pm = context.packageManager
        s.packages.firstOrNull { pm.getLaunchIntentForPackage(it) != null }?.let { return it }
        val apps = pm.queryIntentActivities(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER), 0)
        return apps.firstOrNull { r -> s.labels.any { r.loadLabel(pm).toString().equals(it, ignoreCase = true) } }
            ?.activityInfo?.packageName
    }

    fun run(context: Context, appName: String, destination: String, leaveOpen: Boolean): PhoneActions.Result {
        val s = spec(appName) ?: return PhoneActions.Result(false, "I only know Grab, Gojek, TADA and Zig")
        val data = JSONObject().put("app", s.name)
        fun fail(status: String, why: String, screen: String? = null, trace: List<String> = emptyList()): PhoneActions.Result {
            data.put("status", status).put("trace", JSONArray(trace))
            if (screen != null) data.put("screen", screen.take(1500))
            return PhoneActions.Result(false, "${s.name}: $why", data)
        }
        if (destination.isBlank()) return fail("bad_request", "where to?")
        val svc = SendTapService.instance ?: return fail("no_access", accessHint)
        val keyguard = context.getSystemService(android.app.KeyguardManager::class.java)
        if (keyguard?.isKeyguardLocked == true) return fail("locked", "the phone is locked; unlock it and ask again")
        if (!android.provider.Settings.canDrawOverlays(context) && !MainActivity.visible)
            return fail("no_overlay", "Android won't let Jarvis open apps from the background yet. On the phone, open Jarvis → ⋮ → " +
                "Permissions & setup and switch on \"Open apps and sites when asked\"")
        val pkg = installed(context, s) ?: return fail("not_installed", "not installed")

        val trace = ArrayList<String>()
        val launch = context.packageManager.getLaunchIntentForPackage(pkg) ?: return fail("not_installed", "can't be opened")
        // A fresh start lands on the app's home screen, not wherever you last left it.
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
        context.startActivity(launch)
        trace.add("opened $pkg")

        fun root(): AccessibilityNodeInfo? = svc.rootInActiveWindow?.takeIf { it.packageName?.toString() == pkg }
        if (!waitFor(12_000) { root() != null }) return fail("no_open", "didn't come to the front", trace = trace)
        Thread.sleep(1500)                                          // splash screens

        // 1. Find the box to type the destination into.
        var box: AccessibilityNodeInfo? = null
        var openerTried = false
        var searching = false                                       // a "Where to?" was tapped: this is the search screen
        val until = System.currentTimeMillis() + 22_000
        while (System.currentTimeMillis() < until) {
            val r = root()
            if (r == null) { Thread.sleep(600); continue }
            box = destinationBox(r, searching)
            if (box != null) break
            val closed = tapFirst(r, dismiss)
            if (closed != null) { trace.add("tapped $closed"); Thread.sleep(800); continue }
            val search = tapFirst(r, whereTo)
            if (search != null) { trace.add("tapped $search"); searching = true; Thread.sleep(1300); continue }
            if (!openerTried) {
                openerTried = true
                val opened = tapFirst(r, s.openers)
                if (opened != null) { trace.add("tapped $opened"); Thread.sleep(1500); continue }
            }
            val words = lines(r)
            if (words.any { it.equals("Log in", true) || it.equals("Sign up", true) || it.equals("Sign in", true) } && words.size < 25)
                return fail("signed_out", "not signed in", screen(words), trace)
            Thread.sleep(700)
        }
        val target = box ?: return fail("no_search", "couldn't find where to type the destination", root()?.let { screen(lines(it)) }, trace)
        val args = Bundle().apply { putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, destination) }
        target.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
        if (!target.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args))
            return fail("no_type", "couldn't type the destination", root()?.let { screen(lines(it)) }, trace)
        trace.add("typed destination")

        // 2. Pick the first suggestion that matches what was asked for.
        Thread.sleep(1500)
        var place: String? = null
        if (!waitFor(9_000, 600) {
                val r = root() ?: return@waitFor false
                val pick = suggestion(r, destination) ?: return@waitFor false
                val clicked = clickable(pick.first)
                if (clicked != null && clicked.performAction(AccessibilityNodeInfo.ACTION_CLICK)) { place = pick.second; true } else false
            }) {
            // Some apps only search when you press the keyboard's Enter.
            val entered = android.os.Build.VERSION.SDK_INT >= 30 && target.refresh() &&
                target.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.id)
            if (!entered) return fail("no_place", "no place matching \"$destination\" came up", root()?.let { screen(lines(it)) }, trace)
            trace.add("pressed Enter")
        } else trace.add("picked ${place?.take(60)}")
        if (place != null) data.put("place", place!!.take(120))

        // 3. Wait for the fares. Once a price shows, nothing more is tapped.
        var last: List<FareParse.Option> = emptyList()
        var found: List<FareParse.Option> = emptyList()
        val fareUntil = System.currentTimeMillis() + 25_000
        var lastWords: List<String> = emptyList()
        while (System.currentTimeMillis() < fareUntil) {
            Thread.sleep(1000)
            val r = root() ?: continue
            lastWords = lines(r)
            val opts = FareParse.parse(lastWords)
            if (opts.isNotEmpty()) {
                if (opts == last) { found = opts; break }          // the same twice: the list has settled
                last = opts
                continue
            }
            val closed = tapFirst(r, softDismiss)
            if (closed != null) { trace.add("tapped $closed"); continue }
            tapFirst(r, advance)?.let { trace.add("tapped $it") }
        }
        if (found.isEmpty()) found = last
        if (found.isEmpty()) return fail("no_fares", "no prices showed up", screen(lastWords), trace)

        val list = JSONArray()
        for (o in found) list.put(JSONObject().put("product", o.product).put("low", o.low).put("high", o.high))
        data.put("status", "ok").put("options", list).put("trace", JSONArray(trace))
        if (!leaveOpen) SendTapService.global(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_HOME)
        val c = FareParse.cheapest(found)!!
        return PhoneActions.Result(true, "${s.name}: ${found.size} option(s), cheapest ${c.product} ${money(c)}", data)
    }

    fun money(o: FareParse.Option) = if (o.high > o.low) "S$%.2f–%.2f".format(o.low, o.high) else "S$%.2f".format(o.low)

    // ── reading and tapping ──────────────────────────────────────────────────

    private fun waitFor(ms: Long, step: Long = 400, ok: () -> Boolean): Boolean {
        val until = System.currentTimeMillis() + ms
        while (System.currentTimeMillis() < until) {
            if (ok()) return true
            Thread.sleep(step)
        }
        return false
    }

    private fun walk(root: AccessibilityNodeInfo, visit: (AccessibilityNodeInfo) -> Unit) {
        val queue = ArrayDeque<Pair<AccessibilityNodeInfo, Int>>()
        queue.add(root to 0)
        var seen = 0
        while (queue.isNotEmpty() && seen < 1500) {
            val (n, depth) = queue.removeFirst(); seen++
            if (n.isVisibleToUser) visit(n)
            if (depth < 50) for (i in 0 until n.childCount) n.getChild(i)?.let { queue.add(it to depth + 1) }
        }
    }

    /** The words on screen, in reading order (top to bottom, then left to right). */
    private fun lines(root: AccessibilityNodeInfo): List<String> {
        val items = ArrayList<Pair<Rect, String>>()
        walk(root) { n ->
            val t = (n.text ?: n.contentDescription)?.toString()?.trim()
            if (!t.isNullOrEmpty()) { val b = Rect(); n.getBoundsInScreen(b); items.add(b to t) }
        }
        // The same words in two places (two rides both at S$12.40) are two lines; only exact repeats go.
        return items.distinctBy { "${it.first.flattenToString()}|${it.second}" }
            .sortedWith(compareBy({ it.first.top / 12 }, { it.first.left })).map { it.second }
    }

    private fun screen(words: List<String>) = words.joinToString("\n").take(1500)

    private fun label(n: AccessibilityNodeInfo) = (n.text ?: n.contentDescription ?: n.hintText)?.toString()?.trim() ?: ""

    private fun clickable(n: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        var c: AccessibilityNodeInfo? = n
        var hops = 0
        while (c != null && !c.isClickable && hops < 6) { c = c.parent; hops++ }
        return c
    }

    /** Taps the first visible item whose words are one of these (exact, then starting with it). Returns what it tapped. */
    private fun tapFirst(root: AccessibilityNodeInfo, words: List<String>): String? {
        for (w in words) {
            val hits = root.findAccessibilityNodeInfosByText(w).filter { it.isVisibleToUser && !it.isEditable }
            val pick = hits.firstOrNull { label(it).equals(w, true) }
                ?: hits.firstOrNull { label(it).startsWith(w, true) && label(it).length <= w.length + 12 } ?: continue
            val l = label(pick)
            if (neverTap.containsMatchIn(l)) continue
            val c = clickable(pick) ?: continue
            if (neverTap.containsMatchIn(label(c))) continue
            if (c.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return l
        }
        return null
    }

    /**
     * An editable box that is for the destination: one whose hint says so, the focused one, or (only on the
     * search screen a "Where to?" opened) the last one. Not any box: a home screen's "Search the app" is not it.
     */
    private fun destinationBox(root: AccessibilityNodeInfo, searching: Boolean): AccessibilityNodeInfo? {
        val boxes = ArrayList<AccessibilityNodeInfo>()
        walk(root) { if (it.isEditable) boxes.add(it) }
        if (boxes.isEmpty()) return null
        val hinted = boxes.firstOrNull { b -> whereTo.any { label(b).contains(it, true) } || label(b).contains("destination", true) }
        if (hinted != null) return hinted
        boxes.firstOrNull { it.isFocused }?.let { return it }
        return if (searching) boxes.last() else null
    }

    /** The suggestion under the boxes that shares the most words with the destination; null until one appears. */
    private fun suggestion(root: AccessibilityNodeInfo, destination: String): Pair<AccessibilityNodeInfo, String>? {
        val tokens = destination.lowercase().split(Regex("[^\\p{L}\\p{N}]+")).filter { it.length >= 3 || it.any(Char::isDigit) }
        if (tokens.isEmpty()) return null
        var boxBottom = 0
        walk(root) { if (it.isEditable) { val b = Rect(); it.getBoundsInScreen(b); boxBottom = maxOf(boxBottom, b.bottom) } }
        var best: Triple<AccessibilityNodeInfo, String, Int>? = null
        var bestTop = Int.MAX_VALUE
        walk(root) { n ->
            if (n.isEditable) return@walk
            val t = (n.text ?: n.contentDescription)?.toString()?.trim() ?: return@walk
            if (t.length > 160 || notAPlace.containsMatchIn(t) || neverTap.containsMatchIn(t)) return@walk
            val b = Rect(); n.getBoundsInScreen(b)
            if (b.top < boxBottom) return@walk
            val low = t.lowercase()
            val score = tokens.count { low.contains(it) }
            if (score == 0) return@walk
            if (best == null || score > best!!.third || (score == best!!.third && b.top < bestTop)) {
                best = Triple(n, t, score); bestTop = b.top
            }
        }
        return best?.let { it.first to it.second }
    }
}
