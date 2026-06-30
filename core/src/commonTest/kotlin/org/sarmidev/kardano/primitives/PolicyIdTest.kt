package org.sarmidev.kardano.primitives

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.encoding.hex.Hex
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

class PolicyIdTest {

    @Test
    fun ofAcceptsExactSize() {
        val ok = assertIs<KardanoResult.Ok<PolicyId>>(PolicyId.of(ByteArray(PolicyId.SIZE)))
        assertEquals(PolicyId.SIZE, ok.value.toByteArray().size)
    }

    @Test
    fun ofRejectsWrongSizes() {
        for (size in listOf(0, 27, 29)) {
            val err = assertIs<KardanoResult.Err<ByteSizeError>>(PolicyId.of(ByteArray(size)))
            assertEquals(ByteSizeError.Fixed(PolicyId.SIZE, size), err.error)
        }
    }

    @Test
    fun constructionMakesDefensiveCopy() {
        val source = ByteArray(PolicyId.SIZE) { 1 }
        val policyId = assertIs<KardanoResult.Ok<PolicyId>>(PolicyId.of(source)).value
        source[0] = 9
        assertEquals(1.toByte(), policyId.toByteArray()[0])
    }

    @Test
    fun accessorReturnsDefensiveCopy() {
        val policyId = assertIs<KardanoResult.Ok<PolicyId>>(PolicyId.of(ByteArray(PolicyId.SIZE) { 1 })).value
        val exposed = policyId.toByteArray()
        exposed[0] = 9
        assertEquals(1.toByte(), policyId.toByteArray()[0])
    }

    @Test
    fun equalContentIsEqual() {
        val a = assertIs<KardanoResult.Ok<PolicyId>>(PolicyId.of(ByteArray(PolicyId.SIZE) { it.toByte() })).value
        val b = assertIs<KardanoResult.Ok<PolicyId>>(PolicyId.of(ByteArray(PolicyId.SIZE) { it.toByte() })).value
        assertEquals(a, b)
        assertEquals(a.hashCode(), b.hashCode())
    }

    @Test
    fun differentContentIsNotEqual() {
        val a = assertIs<KardanoResult.Ok<PolicyId>>(PolicyId.of(ByteArray(PolicyId.SIZE) { 1 })).value
        val b = assertIs<KardanoResult.Ok<PolicyId>>(PolicyId.of(ByteArray(PolicyId.SIZE) { 2 })).value
        assertFalse(a == b)
    }

    @Test
    fun toStringDoesNotRenderBytes() {
        // Recognizable byte content (0xAB). The structural toString must not leak it.
        val policyId = assertIs<KardanoResult.Ok<PolicyId>>(
            PolicyId.of(ByteArray(PolicyId.SIZE) { 0xAB.toByte() }),
        ).value
        val text = policyId.toString()
        assertTrue(text.contains("size="), "toString should keep a structural marker")
        assertFalse(
            text.contains(Hex.encode(policyId.toByteArray())),
            "toString must not render the wrapped bytes",
        )
    }
}
