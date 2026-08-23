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
        compileSdk {
            version = release(libs.versions.android.compileSdk.get().toInt()) {
                minorApiLevel = libs.versions.android.compileSdkMinor.get().toInt()
            }
        }
        minSdk = libs.versions.android.minSdk.get().toInt()

        compilerOptions {
            jvmTarget = JvmTarget.JVM_11
        }
        withHostTest {
        }
        // 1.6c-follow-up / 1.6c-follow-up-2 gate results: test-only device-test source set that
        // verifies, on real Android runtime (emulator/device) rather than just host-JVM
        // compilation, that (a) the identus bip32-ed25519 coordinate's native library loads and
        // derives correctly, and (b) KeyDerivation.publicKey() returns Ok and reproduces the
        // cited addr_xvk golden via the lazysodium-android backend (see src/androidDeviceTest).
        // No product/app code is added.
        withDeviceTest {
            instrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        }
        // 1.6c-follow-up-2 (ADR-0010 Android-projection resolution): net.java.dev.jna:jna
        // publishes both a jar and an aar artifact for the same coordinate; depending on it from
        // both androidMain (transitively, via identus bip32-ed25519-android) and lazysodium's
        // own dependency metadata resolved to two different artifact types, which AGP's
        // duplicate-class check on the merged device-test APK correctly rejected. Excluding the
        // duplicated license-notice resource is the documented AGP workaround for the resulting
        // packaging clash; it does not change which JNA classes/symbols load at runtime.
        packaging {
            resources.excludes.add("META-INF/AL2.0")
            resources.excludes.add("META-INF/LGPL2.1")
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
            // Cardano extended Ed25519-BIP32 signing (ADR-0015 Block 1.10b, backend adopted per
            // ADR-0016 §9): bip32-ed25519:1.8.8 above has no signing function (ADR-0015 Context),
            // so signing delegates to this project-owned module's sign/verify/deriveXpub seam
            // instead. `:crypto-signing-backend`'s generated bindings are directly callable from
            // commonMain on every target — no additional expect/actual seam needed here.
            implementation(projects.cryptoSigningBackend)
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
            // Public-key projection actual (1.6c-follow-up-2 gate result, ADR-0010): unlike the
            // minimal libsodium build Ionspin ships for Android (JVM/iOS backend, above), the
            // lazysodium-android AAR bundles a full libsodium .so that exports
            // crypto_scalarmult_ed25519_base_noclamp on all four ABIs (verified by `nm -D` and
            // by an on-device probe reproducing the cited addr_xvk goldens on API 24, 35, and 36
            // runtimes). Its own Sodium/SodiumAndroid JNA interfaces do not declare that
            // function, so PublicKeyProjection.android.kt defines a minimal JNA Library
            // interface for it directly. net.java.dev.jna:jna is pinned explicitly (and forced
            // to the @aar artifact type) to reconcile with the identus-transitive jna dependency
            // and avoid a duplicate jar+aar artifact clash in the merged device-test APK.
            implementation("com.goterl:lazysodium-android:${libs.versions.lazysodium.android.get()}") {
                exclude(group = "net.java.dev.jna", module = "jna")
            }
            implementation("net.java.dev.jna:jna:${libs.versions.jna.get()}@aar")
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