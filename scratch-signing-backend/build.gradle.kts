// Disposable Block 1.10b provisioning spike (ADR-0016 §7e). Not part of the
// Kardano SDK: not published, not depended on by any SDK module, and meant
// to be deleted once the spike's evidence is recorded in ADR-0016.
//
// All plugin/dependency versions are pinned explicitly in this file rather
// than referencing the root `gradle/libs.versions.toml` catalog, so this
// experiment stays fully self-contained inside `scratch-signing-backend/`.
//
// NO ANDROID KOTLIN TARGET HERE — see README.md "Android: blocked at the
// Gradle/Gobley layer". This repo pins AGP 9.0.1, whose `com.android.library`
// plugin refuses to combine with `org.jetbrains.kotlin.multiplatform`
// (AGP 9 requires `com.android.kotlin.multiplatform.library` instead), and
// Gobley 0.3.7 does not yet support that newer plugin id
// (github.com/gobley/gobley/issues/153, open, no committed fix). Android
// evidence for this spike is instead gathered directly with `cargo ndk`
// (raw cross-compile + `nm`/`llvm-readelf` symbol proof), documented in
// README.md, without any Gradle/AGP involvement.
import gobley.gradle.GobleyHost
import gobley.gradle.cargo.dsl.jvm

plugins {
    kotlin("multiplatform") version "2.4.0"
    id("dev.gobley.cargo") version "0.3.7"
    id("dev.gobley.uniffi") version "0.3.7"
    kotlin("plugin.atomicfu") version "2.4.0"
}

kotlin {
    jvm()
    iosArm64()
    iosSimulatorArm64()

    sourceSets {
        commonTest {
            dependencies {
                implementation(kotlin("test"))
            }
        }
        jvmTest {
            dependencies {
                implementation(kotlin("test"))
            }
        }
    }
}

cargo {
    builds.jvm {
        // This spike only runs JVM tests on this host machine; no cross-host
        // JVM publishing is intended (see README "Disposal").
        embedRustLibrary = (GobleyHost.current.rustTarget == rustTarget)
    }
}

uniffi {
    generateFromLibrary {
        packageName = "scratch.signingbackend"
    }
}
