package org.sarmidev.kardano.crypto

import org.sarmidev.kardano.KardanoResult
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.fail

/**
 * Validation and structural tests for [Cip1852Path.of].
 */
class Cip1852PathTest {

    @Test
    fun of_validAccountRoleIndex_isOk() {
        val path = okPath(Cip1852Path.of(account = 0, role = Cip1852Role.EXTERNAL, index = 0))

        assertEquals(0, path.account)
        assertEquals(Cip1852Role.EXTERNAL, path.role)
        assertEquals(0, path.index)
    }

    @Test
    fun of_accountAtSoftIndexMax_isOk() {
        val result = Cip1852Path.of(
            account = Cip1852Path.SOFT_INDEX_MAX,
            role = Cip1852Role.EXTERNAL,
            index = 0,
        )

        assertEquals(true, result is KardanoResult.Ok)
    }

    @Test
    fun of_negativeAccount_isRejected() {
        val result = Cip1852Path.of(account = -1, role = Cip1852Role.EXTERNAL, index = 0)

        assertEquals(KardanoResult.Err(KeyDerivationError.IndexOutOfRange(-1)), result)
    }

    @Test
    fun of_accountAboveSoftIndexMax_isRejected() {
        // A value above Int.MAX_VALUE, only representable because `of` takes Long.
        val overLimit = Cip1852Path.SOFT_INDEX_MAX + 1

        val result = Cip1852Path.of(account = overLimit, role = Cip1852Role.EXTERNAL, index = 0)

        assertEquals(KardanoResult.Err(KeyDerivationError.IndexOutOfRange(overLimit)), result)
    }

    @Test
    fun of_negativeIndex_isRejected() {
        val result = Cip1852Path.of(account = 0, role = Cip1852Role.EXTERNAL, index = -1)

        assertEquals(KardanoResult.Err(KeyDerivationError.IndexOutOfRange(-1)), result)
    }

    @Test
    fun of_indexAboveSoftIndexMax_isRejected() {
        val overLimit = Cip1852Path.SOFT_INDEX_MAX + 1

        val result = Cip1852Path.of(account = 0, role = Cip1852Role.EXTERNAL, index = overLimit)

        assertEquals(KardanoResult.Err(KeyDerivationError.IndexOutOfRange(overLimit)), result)
    }

    @Test
    fun toString_rendersThePathString() {
        val path = okPath(Cip1852Path.of(account = 0, role = Cip1852Role.EXTERNAL, index = 1442))

        assertEquals("m/1852'/1815'/0'/0/1442", path.toString())
    }

    @Test
    fun fullDerivationIndices_appliesPrimeOffsetToPurposeCoinTypeAndAccountOnly() {
        val path = okPath(Cip1852Path.of(account = 7, role = Cip1852Role.INTERNAL, index = 3))

        val indices = path.fullDerivationIndices()

        assertEquals(
            listOf(
                Cip1852Path.PURPOSE + Cip1852Path.PRIME_INDEX_OFFSET,
                Cip1852Path.COIN_TYPE + Cip1852Path.PRIME_INDEX_OFFSET,
                7L + Cip1852Path.PRIME_INDEX_OFFSET,
                Cip1852Role.INTERNAL.value.toLong(),
                3L,
            ),
            indices,
        )
    }

    private fun okPath(
        result: KardanoResult<Cip1852Path, KeyDerivationError>,
    ): Cip1852Path = when (result) {
        is KardanoResult.Ok -> result.value
        is KardanoResult.Err -> fail("expected Ok but got Err(${result.error})")
    }
}
