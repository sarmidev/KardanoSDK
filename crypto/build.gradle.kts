import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    alias(libs.plugins.kotlinMultiplatform)
    alias(libs.plugins.androidMultiplatformLibrary)
}

kotlin {
    explicitApi()

    iosArm64()
    iosSimulatorArm64()

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
        }
        commonTest.dependencies {
            implementation(libs.kotlin.test)
        }
    }
}
