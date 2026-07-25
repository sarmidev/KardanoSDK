

@file:Suppress("RemoveRedundantBackticks")

package org.sarmidev.kardano.crypto.signing.backend.internal

// Common helper code.
//
// Ideally this would live in a separate .kt file where it can be unittested etc
// in isolation, and perhaps even published as a re-useable package.
//
// However, it's important that the details of how this helper code works (e.g. the
// way that different builtin types are passed across the FFI) exactly match what's
// expected by the Rust code on the other side of the interface. In practice right
// now that means coming from the exact some version of `uniffi` that was used to
// compile the Rust component. The easiest way to ensure this is to bundle the Kotlin
// helpers directly inline like we're doing here.

public class InternalException(message: String) : kotlin.Exception(message)

// Public interface members begin here.


// Interface implemented by anything that can contain an object reference.
//
// Such types expose a `destroy()` method that must be called to cleanly
// dispose of the contained objects. Failure to call this method may result
// in memory leaks.
//
// The easiest way to ensure this method is called is to use the `.use`
// helper method to execute a block and destroy the object at the end.
@OptIn(ExperimentalStdlibApi::class)
public interface Disposable : AutoCloseable {
    public fun destroy()
    override fun close(): Unit = destroy()
    public companion object {
        internal fun destroy(vararg args: Any?) {
            for (arg in args) {
                when (arg) {
                    is Disposable -> arg.destroy()
                    is ArrayList<*> -> {
                        for (idx in arg.indices) {
                            val element = arg[idx]
                            if (element is Disposable) {
                                element.destroy()
                            }
                        }
                    }
                    is Map<*, *> -> {
                        for (element in arg.values) {
                            if (element is Disposable) {
                                element.destroy()
                            }
                        }
                    }
                    is Array<*> -> {
                        for (element in arg) {
                            if (element is Disposable) {
                                element.destroy()
                            }
                        }
                    }
                    is Iterable<*> -> {
                        for (element in arg) {
                            if (element is Disposable) {
                                element.destroy()
                            }
                        }
                    }
                }
            }
        }
    }
}

@OptIn(kotlin.contracts.ExperimentalContracts::class)
public inline fun <T : Disposable?, R> T.use(block: (T) -> R): R {
    kotlin.contracts.contract {
        callsInPlace(block, kotlin.contracts.InvocationKind.EXACTLY_ONCE)
    }
    return try {
        block(this)
    } finally {
        try {
            // N.B. our implementation is on the nullable type `Disposable?`.
            this?.destroy()
        } catch (e: Throwable) {
            // swallow
        }
    }
}

/** Used to instantiate an interface without an actual pointer, for fakes in tests, mostly. */
public object NoPointer











/**
 * Input-shape errors surfaced across the UniFFI boundary. Each variant mirrors a length check the
 * underlying `ed25519-bip32` crate itself performs (`PrivateKeyError`, `PublicKeyError`,
 * `SignatureError`); this wrapper adds no additional validation and no cryptographic logic.
 */
public sealed class SigningBackendException: kotlin.Exception() {

    /**
     * `xprv` was not the expected 96 bytes (64-byte extended scalar `kL||kR` + 32-byte chain
     * code).
     */
    public class InvalidExtendedPrivateKey(
    ) : SigningBackendException() {
        override val message: String
            get() = ""
    }

    /**
     * `xpub` was not the expected 64 bytes (32-byte public key + 32-byte chain code).
     */
    public class InvalidExtendedPublicKey(
    ) : SigningBackendException() {
        override val message: String
            get() = ""
    }

    /**
     * `signature` was not the expected 64 bytes.
     */
    public class InvalidSignature(
    ) : SigningBackendException() {
        override val message: String
            get() = ""
    }

}

/**
 * Derives the extended public key from an extended private key `xprv`, delegating to
 * `ed25519_bip32::XPrv::public`. Exposed only so backend tests can exercise `verify()` without
 * hardcoding a second key fixture; this is derivation — the same operation the shipped
 * `bip32-ed25519:1.8.8` wrapper already exposes and verifies (ADR-0016 §1) — not new
 * cryptographic logic.
 */
@Throws(SigningBackendException::class)
public expect fun `deriveXpub`(`xprv`: kotlin.ByteArray): kotlin.ByteArray

/**
 * Signs `message` with the Cardano extended Ed25519-BIP32 private key `xprv` (96 bytes),
 * delegating to `ed25519_bip32::XPrv::sign`. Returns the raw 64-byte signature. No handwritten
 * signing math.
 */
@Throws(SigningBackendException::class)
public expect fun `sign`(`xprv`: kotlin.ByteArray, `message`: kotlin.ByteArray): kotlin.ByteArray

/**
 * Verifies `signature` over `message` against the Cardano extended Ed25519-BIP32 public key
 * `xpub` (64 bytes), delegating to `ed25519_bip32::XPub::verify`. No handwritten verification
 * math.
 */
@Throws(SigningBackendException::class)
public expect fun `verify`(`xpub`: kotlin.ByteArray, `message`: kotlin.ByteArray, `signature`: kotlin.ByteArray): kotlin.Boolean
