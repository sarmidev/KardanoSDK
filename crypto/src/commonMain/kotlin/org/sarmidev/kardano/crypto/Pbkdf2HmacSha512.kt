package org.sarmidev.kardano.crypto

/**
 * Platform-seam PBKDF2-HMAC-SHA-512, module-internal to [IcarusMasterKey].
 *
 * Per the ADR-0009 Block 1.6b gate result: `cryptography-kotlin` 0.6.0's JDK-backed provider
 * routes through JCA `SecretKeyFactory.getInstance("PBKDF2WithHmacSHA512")`, which the Android
 * platform only guarantees from API level 26 — below this module's `minSdk = 24` — and a host
 * JVM test cannot detect that gap (the host JVM has the algorithm). This SDK therefore uses the
 * documented platform-seam fallback (ADR-0009 §3) instead of a single common dependency: a
 * BouncyCastle-backed `actual` shared by JVM and Android (it does not call `SecretKeyFactory`),
 * and an Apple CommonCrypto (`CCKeyDerivationPBKDF`) `actual` on iOS. PBKDF2 itself remains a
 * delegated cryptographic primitive on every target; no PBKDF2 step is hand-written here.
 *
 * [password] and [salt] are always passed as raw bytes on every target — never decoded to or
 * from a `String` — because the Icarus master-key password is the raw passphrase bytes and the
 * salt is raw BIP-39 entropy bytes, neither of which is in general valid text (ADR-0009 §2).
 *
 * @param password the PBKDF2 password bytes. Not modified.
 * @param salt the PBKDF2 salt bytes. Not modified.
 * @param iterations the PBKDF2 iteration count.
 * @param outputBytes the number of derived bytes to produce.
 * @return a fresh [outputBytes]-byte array. May throw on backend failure; the sole caller,
 *   [IcarusMasterKey.fromMnemonic], maps any throwable to a typed [KeyDerivationError] and never
 *   lets it escape the public API.
 */
internal expect fun pbkdf2HmacSha512(
    password: ByteArray,
    salt: ByteArray,
    iterations: Int,
    outputBytes: Int,
): ByteArray
