package org.sarmidev.kardano.provider

/**
 * A minimal view of the chain tip, used as an optional liveness/health signal for a
 * [ChainQueryProvider].
 *
 * It reports only the current [slot] and [blockHeight]. It makes no claim about
 * synchronization state, finality, or the correctness of any block; it is a coarse
 * "is the provider reachable and roughly current" signal only.
 *
 * @property slot the absolute slot number of the tip.
 * @property blockHeight the block height (block number) of the tip.
 */
public data class ChainTip(
    public val slot: Long,
    public val blockHeight: Long,
)
