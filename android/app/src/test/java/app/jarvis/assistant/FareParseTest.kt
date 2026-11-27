package app.jarvis.assistant

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FareParseTest {
    private fun one(lines: List<String>, product: String) = FareParse.parse(lines).first { it.product == product }

    @Test fun nameAboveThePriceWithAnEtaBetween() {
        val opts = FareParse.parse(listOf("Choose a ride", "JustGrab", "4 seats · 3 min", "S$12.40",
            "GrabShare", "2 min", "S$9.80", "GrabCar Premium", "S$21"))
        assertEquals(listOf("JustGrab", "GrabShare", "GrabCar Premium"), opts.map { it.product })
        assertEquals(9.80, FareParse.cheapest(opts)!!.low, 0.001)
    }

    @Test fun rangesOnOneLine() {
        val o = one(listOf("GoCar · 4 min · $11.90 - $14.20"), "GoCar")
        assertEquals(11.90, o.low, 0.001)
        assertEquals(14.20, o.high, 0.001)
        val t = one(listOf("Taxi (Metered)", "S$ 18–22"), "Taxi (Metered)")
        assertEquals(18.0, t.low, 0.001); assertEquals(22.0, t.high, 0.001)
    }

    @Test fun aStruckThroughPriceGivesWayToThePromoPrice() {
        assertEquals(12.10, one(listOf("TADA Car", "S$15.20 S$12.10"), "TADA Car").low, 0.001)
        assertEquals(12.10, one(listOf("TADA Car", "S$15.20", "S$12.10"), "TADA Car").low, 0.001)
    }

    @Test fun discountsBalancesAndTinyAmountsAreNotFares() {
        val opts = FareParse.parse(listOf("GrabPay balance S$40.00", "Get $5 off your next ride", "JustGrab", "S$13.00",
            "Platform fee S$0.90"))
        assertEquals(1, opts.size)
        assertEquals("JustGrab", opts[0].product)
    }

    @Test fun aWholeRowInOneDescription() {
        val o = one(listOf("Zig Taxi, 4 seats, 5 min, S$16.50, incl. booking fee"), "Zig Taxi")
        assertEquals(16.50, o.low, 0.001)
    }

    @Test fun twoRidesAtTheSamePriceAreBothKept() {
        val opts = FareParse.parse(listOf("Economy", "$12.40", "Comfort", "$12.40"))
        assertEquals(2, opts.size)
    }

    @Test fun noPricesNoOptions() {
        assertTrue(FareParse.parse(listOf("Where to?", "Changi Airport Terminal 3", "Home")).isEmpty())
    }
}
