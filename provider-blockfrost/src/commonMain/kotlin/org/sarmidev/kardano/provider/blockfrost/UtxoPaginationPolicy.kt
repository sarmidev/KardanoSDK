package org.sarmidev.kardano.provider.blockfrost

/**
 * Internal UTxO pagination bounds for [BlockfrostChainQueryProvider].
 *
 * Production uses [Default] (100 entries per page, 100 pages — 10_000 UTxOs). After
 * [maxPages] full pages the provider probes the next page for one item. Tests inject a
 * smaller policy so the cap/probe path can be exercised without allocating a 10_000-entry
 * page. Construction rejects non-positive bounds, `maxPages == Int.MAX_VALUE`
 * (`maxPages + 1` would overflow), and a `pageCount * maxPages` product that does not
 * fit in `Int`, before any arithmetic is used. This type is not part of the public API.
 *
 * @property pageCount entries requested per page (Blockfrost's maximum page size is 100).
 * @property maxPages upper bound on pages fetched, so a query never loops unbounded.
 */
internal class UtxoPaginationPolicy(
    val pageCount: Int,
    val maxPages: Int,
) {
    init {
        require(pageCount > 0) { "pageCount must be positive" }
        require(maxPages > 0) { "maxPages must be positive" }
        require(maxPages < Int.MAX_VALUE) {
            "maxPages must be less than Int.MAX_VALUE so maxPages + 1 cannot overflow"
        }
        val product = pageCount.toLong() * maxPages.toLong()
        require(product <= Int.MAX_VALUE.toLong()) {
            "pageCount * maxPages overflows Int"
        }
    }

    /** Maximum items this policy will accumulate (`pageCount * maxPages`). */
    val cap: Int = pageCount * maxPages

    internal companion object {
        val Default: UtxoPaginationPolicy = UtxoPaginationPolicy(pageCount = 100, maxPages = 100)
    }
}
