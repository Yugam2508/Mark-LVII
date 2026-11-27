package app.jarvis.assistant

/**
 * Reads ride options and their quoted prices out of the words on a ride app's screen ("JustGrab",
 * "S$12.40"; "GoCar · 4 min · $11.90 - $14.20"). Plain Kotlin with no Android in it, so it is tested on
 * the PC (FareParseTest). The ride apps change their screens often; prices are the one thing that is
 * always written out as text, so everything here starts from a price and looks back for its name.
 */
object FareParse {
    data class Option(val product: String, val low: Double, val high: Double)

    private const val NUM = """(\d{1,3}(?:[.,]\d{1,2})?)"""
    private const val CUR = """(?:S\$|SGD|\$)"""
    /** "S$12.40", "$12 - $15", "SGD 9.80", "S$ 11–14", "$12 to $15". */
    private val price = Regex("""$CUR\s?$NUM(?:\s?(?:-|–|—|~|to)\s?(?:$CUR)?\s?$NUM)?""", RegexOption.IGNORE_CASE)

    /** Lines whose price is not a fare: a discount, a balance, a top-up. */
    private val notAFare = Regex("""\b(off|save|saving|discount|balance|wallet|credits?|cashback|voucher|top.?up|points|reward|per km|/km)\b""",
        RegexOption.IGNORE_CASE)
    /** Words that are never a ride's name, though a fare's line may carry them. */
    private val notAName = Regex("""\b(fee|surcharge|tip|incl\.?|including|included)\b""", RegexOption.IGNORE_CASE)

    /** Parts of a row that are not the ride's name: ETAs, seats, times, distances, promo tags. */
    private val noise = Regex("""^(\d+\s?(min|mins|minutes|seats?|pax|km|m)\b.*|\d{1,2}:\d{2}.*|\d+[-–]\d+\s?(min|mins).*|promo.*|best.*|cheapest.*|fastest.*|recommended.*|eta.*|arrives?.*|est\.?.*|estimated.*|fare.*|price.*|total.*|cash|card|·|•|\W*)$""",
        RegexOption.IGNORE_CASE)

    private fun num(s: String) = s.replace(',', '.').toDouble()

    fun parse(lines: List<String>): List<Option> {
        val out = LinkedHashMap<String, Option>()
        val named = HashMap<Int, String>()
        for ((i, raw) in lines.withIndex()) {
            val line = raw.trim()
            if (line.isEmpty() || notAFare.containsMatchIn(line)) continue
            val hits = price.findAll(line).toList()
            if (hits.isEmpty()) continue
            // Two plain prices side by side and no dash between them: the old price struck through and the
            // promo price. The lower one is what you would pay.
            val lows = hits.map { num(it.groupValues[1]) }
            val highs = hits.map { h -> h.groupValues[2].takeIf { it.isNotEmpty() }?.let { num(it) } ?: num(h.groupValues[1]) }
            val k = lows.indices.minBy { lows[it] }
            val low = lows[k]; val high = maxOf(highs[k], low)
            if (low < 3.0 || high > 400.0) continue
            val name = nameOnLine(line, hits) ?: nameAbove(lines, i, named) ?: continue
            named[i] = name
            val prev = out[name.lowercase()]
            if (prev == null || low < prev.low) out[name.lowercase()] = Option(name, low, high)
        }
        return out.values.toList()
    }

    /** "JustGrab, 4 seats, 3 min, S$12.40" — the name is the first part that isn't a number or a tag. */
    private fun nameOnLine(line: String, hits: List<MatchResult>): String? {
        var rest = line
        for (h in hits.reversed()) rest = rest.removeRange(h.range)
        return rest.split(',', '·', '•', '|', '\n').map { it.trim() }.firstOrNull { looksLikeName(it) }
    }

    private fun nameAbove(lines: List<String>, i: Int, named: Map<Int, String>): String? {
        for (j in i - 1 downTo maxOf(0, i - 4)) {
            val l = lines[j].trim()
            // A price straight above with nothing between is the same ride's old (struck-through) price;
            // further up, it is the row above's.
            if (price.containsMatchIn(l)) return if (j == i - 1) named[j] else null
            l.split(',', '·', '•', '|').map { it.trim() }.firstOrNull { looksLikeName(it) }?.let { return it }
        }
        return null
    }

    private fun looksLikeName(s: String): Boolean =
        s.length in 2..40 && s.any { it.isLetter() } && !noise.matches(s) && !notAFare.containsMatchIn(s) && !notAName.containsMatchIn(s)

    /** The cheapest option on a screen, comparing the low end of each quoted range. */
    fun cheapest(options: List<Option>): Option? = options.minByOrNull { it.low }
}
