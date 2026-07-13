package org.sarmidev.kardano.provider

import org.sarmidev.kardano.getOrNull
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.primitives.UtxoRef
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Unit tests for [Value]'s [Value.hasNativeAssets] presence flag (Block 1.11d).
 *
 * These are purely structural: [Value] and [Utxo] carry no protocol logic of their own, so
 * these tests only check that the ADA-only default is preserved for every existing call site
 * and that native-asset presence — quantities, policy ids, and asset names are deliberately
 * **not** represented, per ADR-0005/ADR-0006's ADA-only-first-MVP scope — can be represented
 * at all. No protocol vectors are invented; the UTxO reference used below is a plain
 * structural fixture (fixed bytes), not a claim about any real on-chain output.
 */
class ValueTest {

    private fun lovelace(value: Long): Lovelace = requireNotNull(Lovelace.of(value).getOrNull())

    private fun utxoRef(fill: Byte, index: Long): UtxoRef {
        val txHash = requireNotNull(TxHash.of(ByteArray(TxHash.SIZE) { fill }).getOrNull())
        return requireNotNull(UtxoRef.of(txHash, index).getOrNull())
    }

    @Test
    fun defaultConstruction_isAdaOnly() {
        val value = Value(lovelace(5_000_000L))
        assertFalse(value.hasNativeAssets, "existing call sites must stay ADA-only by default")
    }

    @Test
    fun explicitAdaOnlyConstruction_reportsNoNativeAssets() {
        val value = Value(lovelace(5_000_000L), hasNativeAssets = false)
        assertFalse(value.hasNativeAssets)
        assertEquals(5_000_000L, value.coin.value)
    }

    @Test
    fun nativeAssetPresenceCanBeRepresented() {
        // Quantities, policy ids, and asset names are deliberately not modeled — only
        // presence. This is the minimal step ADR-0005/ADR-0006 anticipated, not full
        // multi-asset support.
        val value = Value(lovelace(2_000_000L), hasNativeAssets = true)
        assertTrue(value.hasNativeAssets)
        assertEquals(2_000_000L, value.coin.value)
    }

    @Test
    fun utxoCarryingNativeAssetPresence_exposesFlagThroughValue() {
        val ref = utxoRef(0x11, 0L)
        val utxo = Utxo(ref, Value(lovelace(1_500_000L), hasNativeAssets = true))
        assertTrue(utxo.value.hasNativeAssets)
    }

    @Test
    fun equalsAndHashCode_treatHasNativeAssetsAsSignificant() {
        val adaOnly = Value(lovelace(1_000_000L))
        val withAssets = Value(lovelace(1_000_000L), hasNativeAssets = true)
        assertTrue(adaOnly != withAssets, "same coin but different asset presence must not be equal")
    }
}
