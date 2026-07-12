import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    alias(libs.plugins.kotlinMultiplatform)
    alias(libs.plugins.androidMultiplatformLibrary)
}

kotlin {
    explicitApi()

    // Custom cinterop for CCKeyDerivationPBKDF (ADR-0009 Block 1.6b gate result): the shipped
    // platform.CoreCrypto binding maps its `password: const char*` parameter to a Kotlin
    // String, which cannot carry raw passphrase bytes losslessly. See
    // src/nativeInterop/cinterop/pbkdf2raw.def for the raw-byte interop shim
    // (kardano_ccpbkdf2_hmac_sha512) that delegates to CCKeyDerivationPBKDF.
    iosArm64 {
        compilations.getByName("main") {
            val pbkdf2raw by cinterops.creating {
                definitionFile.set(project.file("src/nativeInterop/cinterop/pbkdf2raw.def"))
                packageName("org.sarmidev.kardano.crypto.pbkdf2raw")
            }
        }
    }
    iosSimulatorArm64 {
        compilations.getByName("main") {
            val pbkdf2raw by cinterops.creating {
                definitionFile.set(project.file("src/nativeInterop/cinterop/pbkdf2raw.def"))
                packageName("org.sarmidev.kardano.crypto.pbkdf2raw")
            }
        }
    }

    jvm()

    androidLibrary {
        namespace = "org.sarmidev.kardano.crypto"
        compileSdk = libs.versions.android.compileSdk.get().toInt()
        minSdk = libs.versions.android.minSdk.get().toInt()

        compilerOptions {
            jvmTarget = JvmTarget.JVM_11
        }
        withHostTest {
        }
        // 1.6c-follow-up gate result: test-only device-test source set that verifies the
        // identus bip32-ed25519 coordinate's native library actually loads and derives
        // correctly on Android runtime (emulator/device), not just compiles, and that
        // KeyDerivation.publicKey() degrades to a typed error rather than crashing on Android
        // (see src/androidDeviceTest). No product/app code is added.
        withDeviceTest {
            instrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        }
    }

    sourceSets {
        commonMain.dependencies {
            implementation(projects.core)
            implementation(libs.kotlincrypto.blake2)
            implementation(libs.kotlincrypto.sha2)
            // Ed25519-BIP32 (CIP-1852) private derivation (ADR-0009 Block 1.6c gate result):
            // the wrapper's deriveBytes/deriveBytesPub/fromNonextended are directly callable
            // from commonMain on every target (Design A) — no expect/actual seam needed.
            implementation(libs.bip32.ed25519)
        }
        commonTest.dependencies {
            implementation(libs.kotlin.test)
        }
        jvmMain.dependencies {
            // PBKDF2-HMAC-SHA-512 platform-seam actual (ADR-0009 Block 1.6b gate result):
            // cryptography-kotlin's JDK provider routes through JCA
            // PBKDF2WithHmacSHA512, which is Android API 26+ and fails this module's
            // minSdk 24 target, so JVM and Android share a BouncyCastle-backed actual
            // that does not use SecretKeyFactory.
            implementation(libs.bouncycastle.bcprov)
            // Public-key projection actual (1.6c-follow-up gate result, ADR-0010): verified
            // against the cited addr_xvk vectors on JVM.
            implementation(libs.ionspin.libsodium)
            implementation(libs.kotlinx.coroutinesCore)
        }
        androidMain.dependencies {
            implementation(libs.bouncycastle.bcprov)
            // No libsodium dependency here: the androidMain PublicKeyProjection actual returns
            // KeyDerivationError.PublicKeyProjectionUnavailable without calling any backend
            // (ADR-0010 — the published Android native library lacks the needed symbols).
        }
        getByName("androidDeviceTest").dependencies {
            implementation(libs.kotlin.test)
            implementation(libs.androidx.test.runner)
            implementation(libs.androidx.testExt.junit)
        }
        // No shared iosMain source set in this project (matches the existing per-target
        // pbkdf2raw cinterop pattern): each iOS target gets its own PublicKeyProjection
        // actual, both dependency-identical.
        getByName("iosArm64Main").dependencies {
            // Public-key projection actual (1.6c-follow-up gate result, ADR-0010): the
            // ionspin klib's bundled static libsodium exports the required
            // crypto_scalarmult_ed25519_base_noclamp symbol (verified by symbol inspection;
            // iOS runtime execution itself is recorded as future work, same posture as the
            // 1.6b/1.6c iOS checkpoints — compile+link verified here).
            implementation(libs.ionspin.libsodium)
            implementation(libs.kotlinx.coroutinesCore)
        }
        getByName("iosSimulatorArm64Main").dependencies {
            implementation(libs.ionspin.libsodium)
            implementation(libs.kotlinx.coroutinesCore)
        }
    }
}