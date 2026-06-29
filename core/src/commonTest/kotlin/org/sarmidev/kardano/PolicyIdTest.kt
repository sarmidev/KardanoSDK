package org.sarmidev.kardano

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs

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
}
