package org.sarmidev.kardano.crypto

import org.bouncycastle.crypto.digests.SHA512Digest
import org.bouncycastle.crypto.generators.PKCS5S2ParametersGenerator
import org.bouncycastle.crypto.params.KeyParameter

/**
 * JVM `actual`: BouncyCastle `PKCS5S2ParametersGenerator` over `SHA512Digest`.
 *
 * Deliberately does not use `javax.crypto.SecretKeyFactory` (the ADR-0009 Block 1.6b gate
 * result rejected the JCA `PBKDF2WithHmacSHA512` path for the Android target this `actual`
 * shares its implementation approach with). [password] and [salt] are passed to BouncyCastle as
 * raw bytes, matching the shared `expect` contract.
 */
internal actual fun pbkdf2HmacSha512(
    password: ByteArray,
    salt: ByteArray,
    iterations: Int,
    outputBytes: Int,
): ByteArray {
    val generator = PKCS5S2ParametersGenerator(SHA512Digest())
    generator.init(password, salt, iterations)
    val keyParameter = generator.generateDerivedParameters(outputBytes * 8) as KeyParameter
    return keyParameter.key
}
