package org.sarmidev.kardano.crypto

import org.bouncycastle.crypto.digests.SHA512Digest
import org.bouncycastle.crypto.generators.PKCS5S2ParametersGenerator
import org.bouncycastle.crypto.params.KeyParameter

/**
 * Android `actual`: BouncyCastle `PKCS5S2ParametersGenerator` over `SHA512Digest`.
 *
 * Per the ADR-0009 Block 1.6b gate result, this deliberately does not use
 * `javax.crypto.SecretKeyFactory.getInstance("PBKDF2WithHmacSHA512")`: that JCA algorithm is
 * only guaranteed from Android API level 26, while this module's `minSdk = 24`, and
 * `:crypto:testAndroidHostTest` (which runs on the host JVM) cannot detect that gap. Using
 * BouncyCastle's classes directly avoids `SecretKeyFactory`/JCA provider lookup entirely, so
 * this path is not subject to that API-level restriction. [password] and [salt] are passed as
 * raw bytes, matching the shared `expect` contract (this is the same implementation approach as
 * the JVM `actual`; kept as a separate file per target rather than a shared intermediate source
 * set, to keep this diff's Gradle source-set changes minimal).
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
