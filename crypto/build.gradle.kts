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
    }

    sourceSets {
        commonMain.dependencies {
            implementation(projects.core)
            implementation(libs.kotlincrypto.blake2)
            implementation(libs.kotlincrypto.sha2)
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
        }
        androidMain.dependencies {
            implementation(libs.bouncycastle.bcprov)
        }
    }
}