import org.jetbrains.kotlin.gradle.dsl.JvmTarget

// `:crypto-signing-backend` — permanent, project-owned Cardano extended Ed25519-BIP32 signing
// backend (ADR-0015 Block 1.10; adopted per ADR-0016 §9, Option R1). It replaces the disposable
// `scratch-signing-backend` provisioning spike (ADR-0016 §8).
//
// Option R1: NO Rust/Cargo/Gobley Gradle plugin runs here. The Rust wrapper crate
// (`kardano-ed25519-bip32-signing`, `Cargo.toml`) is built ahead of time, offline, into the
// committed native artifacts (`src/jvmMain/resources/<jna-prefix>/*.dylib`,
// `src/androidMain/jniLibs/<abi>/*.so`, `src/nativeInterop/libs/<target>/*.a`), and the UniFFI
// Kotlin bindings are pre-generated with the `gobley-uniffi-bindgen` CLI and committed under
// `src/{commonMain,jvmMain,nativeMain,androidMain}/kotlin/.../internal/`. See `README.md` for the
// exact regeneration commands and pinned toolchain versions. A Gobley-free module is required to
// keep everything in ONE module: Gobley 0.3.7 cannot coexist with an `androidLibrary {}` target
// under this repo's AGP 9.0.1 pin (ADR-0016 §8, `gobley/gobley#153`).
//
// JVM natives: committed `darwin-aarch64` / `darwin-x86-64` cdylibs. Linux x86-64 uses the
// JNA prefix `linux-x86-64/` and is rebuilt only on native Ubuntu (`x86_64-unknown-linux-gnu`);
// it is not in CHECKSUMS until promotion. Linux ARM and Windows JVM hosts are out of scope.
plugins {
    alias(libs.plugins.kotlinMultiplatform)
    alias(libs.plugins.androidMultiplatformLibrary)
    // The pre-generated UniFFI bindings use `kotlinx.atomicfu.AtomicLong` for the handle-map
    // counter (jvm/native/android source sets), exactly as the spike's Gobley-generated bindings
    // did.
    alias(libs.plugins.atomicfu)
}

kotlin {
    jvm()

    androidLibrary {
        namespace = "org.sarmidev.kardano.crypto.signing.backend"
        compileSdk = libs.versions.android.compileSdk.get().toInt()
        minSdk = libs.versions.android.minSdk.get().toInt()

        compilerOptions {
            jvmTarget = JvmTarget.JVM_11
        }
        // Real on-device KAT (ADR-0016 §7d/§9f): exercises the committed jniLibs `.so`s + the
        // pre-generated Kotlin/JNA bindings together, through the packaged wrapper.
        withDeviceTest {
            instrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        }
    }

    // iOS: Kotlin/Native cinterop over the committed per-target static library. The cinterop
    // package is fixed to `kardano_ed25519_bip32_signing.cinterop` by the `.def` (the generated
    // native bindings reference that exact FQN); the header dir and the per-target `.a` search
    // path are supplied here because the static lib differs between device and simulator.
    iosArm64 {
        compilations.getByName("main") {
            cinterops.create("uniffi") {
                definitionFile.set(project.file("src/nativeInterop/cinterop/kardano_ed25519_bip32_signing.def"))
                includeDirs(project.file("src/nativeInterop/cinterop/headers/kardano_ed25519_bip32_signing"))
                extraOpts("-libraryPath", project.file("src/nativeInterop/libs/iosArm64").absolutePath)
            }
        }
    }
    iosSimulatorArm64 {
        compilations.getByName("main") {
            cinterops.create("uniffi") {
                definitionFile.set(project.file("src/nativeInterop/cinterop/kardano_ed25519_bip32_signing.def"))
                includeDirs(project.file("src/nativeInterop/cinterop/headers/kardano_ed25519_bip32_signing"))
                extraOpts("-libraryPath", project.file("src/nativeInterop/libs/iosSimulatorArm64").absolutePath)
            }
        }
    }

    sourceSets {
        commonMain.dependencies {
            implementation(libs.kotlinx.atomicfu)
        }
        commonTest.dependencies {
            implementation(libs.kotlin.test)
        }
        jvmMain.dependencies {
            // JNA loads the committed cdylib from src/jvmMain/resources/<jna-prefix>/ via the
            // generated `Native.register("kardano_ed25519_bip32_signing")` bindings.
            implementation(libs.jna)
        }
        jvmTest.dependencies {
            implementation(libs.kotlin.test)
        }
        androidMain.dependencies {
            // JNA ships an `@aar` artifact so native loading works on Android; identical
            // dependency/version to crypto/build.gradle.kts's androidMain.
            implementation("net.java.dev.jna:jna:${libs.versions.jna.get()}@aar")
        }
        getByName("androidDeviceTest").dependencies {
            implementation(libs.kotlin.test)
            implementation(libs.androidx.test.runner)
            implementation(libs.androidx.testExt.junit)
        }
    }
}
