package org.sarmidev.kardano.crypto

import org.sarmidev.kardano.KardanoResult
import uniffi.ed25519_bip32_wrapper.DerivationException
import uniffi.ed25519_bip32_wrapper.deriveBytes

/**
 * The default [KeyDerivation] implementation. Private derivation is backed by
 * `org.hyperledger.identus:bip32-ed25519:1.8.8`'s `deriveBytes` (Ed25519-BIP32 V2/Icarus
 * private child derivation); public-key projection is backed by [PublicKeyProjection] (a
 * per-platform seam — see its doc for why, per the 1.6c-follow-up gate result / ADR-0010).
 *
 * This adapter is `internal`: the uniffi-generated wrapper types never appear in the public
 * API. Per the Block 1.6c gate result (ADR-0009 §4), the wrapper's `deriveBytes` function is
 * directly callable from `commonMain` on every target (no `expect`/`actual` seam needed), takes
 * the derivation index as a [UInt] (so a prime index is a plain `(offset + n).toUInt()`, never a
 * signed-`Int` bit-pattern trick), and returns exactly `{"secret_key": 64 bytes, "chain_code":
 * 32 bytes}`.
 */
internal class Bip32Ed25519KeyDerivation : KeyDerivation {

    override fun derivePrivate(
        master: IcarusMasterKey,
        path: Cip1852Path,
    ): KardanoResult<ExtendedPrivateKey, KeyDerivationError> {
        val root = master.rootExtendedKeyBytes()
        var sk = root.copyOfRange(0, ExtendedPrivateKey.XSK_BYTES)
        var chainCode = root.copyOfRange(ExtendedPrivateKey.XSK_BYTES, root.size)
        root.fill(0)

        try {
            for (index in path.fullDerivationIndices()) {
                val step = deriveBytes(sk, chainCode, index.toUInt())
                sk.fill(0)
                chainCode.fill(0)

                val nextSk = step[SECRET_KEY_MAP_KEY]
                val nextChainCode = step[CHAIN_CODE_MAP_KEY]
                if (nextSk == null || nextChainCode == null) {
                    // Wipe whichever of the two arrays the backend did return before
                    // discarding the step: a partial result must not outlive this scope
                    // as an unwiped copy (ADR-0004 §5 / ADR-0009 §7).
                    nextSk?.fill(0)
                    nextChainCode?.fill(0)
                    return KardanoResult.Err(
                        KeyDerivationError.InvalidKeyMaterial(
                            expectedBytes = ExtendedPrivateKey.XSK_BYTES,
                            actualBytes = nextSk?.size ?: 0,
                        ),
                    )
                }
                sk = nextSk
                chainCode = nextChainCode
            }
        } catch (t: Throwable) {
            sk.fill(0)
            chainCode.fill(0)
            return KardanoResult.Err(mapThrowable(t))
        }

        val result = ExtendedPrivateKey.of(sk, chainCode)
        sk.fill(0)
        chainCode.fill(0)
        return result
    }

    override fun publicKey(
        key: ExtendedPrivateKey,
    ): KardanoResult<ExtendedPublicKey, KeyDerivationError> {
        val (leftScalar, chainCode) = key.leftScalarAndChainCode()
        val projected = projectPublicKey(leftScalar)
        leftScalar.fill(0)

        return when (projected) {
            is KardanoResult.Ok -> {
                val result = ExtendedPublicKey.of(projected.value, chainCode)
                projected.value.fill(0)
                chainCode.fill(0)
                result
            }
            is KardanoResult.Err -> {
                chainCode.fill(0)
                KardanoResult.Err(projected.error)
            }
        }
    }

    internal companion object {

        /** The `deriveBytes` result map key for the derived extended private key. */
        private const val SECRET_KEY_MAP_KEY: String = "secret_key"

        /** The `deriveBytes` result map key for the derived chain code. */
        private const val CHAIN_CODE_MAP_KEY: String = "chain_code"

        /**
         * Maps a [Throwable] from the backend to a typed, backend-neutral [KeyDerivationError].
         *
         * Factored out from [derivePrivate] so the mapping itself is directly unit-testable
         * with synthetic exceptions, without invoking the native backend (see
         * `Bip32Ed25519KeyDerivationRuleTest`).
         *
         * @param t the caught throwable. Never rethrown; its message is not retained (a
         *   [DerivationException] carries no key material, but this stays neutral regardless).
         * @return a [KeyDerivationError.SoftDerivationRequired] for
         *   [DerivationException.ExpectedSoftDerivation], or [KeyDerivationError.DerivationFailed]
         *   with a short, backend-neutral category for anything else.
         */
        internal fun mapThrowable(t: Throwable): KeyDerivationError = when (t) {
            is DerivationException.ExpectedSoftDerivation -> KeyDerivationError.SoftDerivationRequired
            is DerivationException.InvalidAddition ->
                KeyDerivationError.DerivationFailed("invalid derivation addition")
            else -> KeyDerivationError.DerivationFailed("key derivation failed")
        }
    }
}
