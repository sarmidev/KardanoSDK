import org.gradle.api.artifacts.dsl.LockMode

plugins {
    // this is necessary to avoid the plugins to be loaded multiple times
    // in each subproject's classloader
    alias(libs.plugins.androidApplication) apply false
    alias(libs.plugins.androidMultiplatformLibrary) apply false
    alias(libs.plugins.composeMultiplatform) apply false
    alias(libs.plugins.composeCompiler) apply false
    alias(libs.plugins.kotlinJvm) apply false
    alias(libs.plugins.kotlinMultiplatform) apply false
}

allprojects {
    dependencyLocking {
        lockMode.set(LockMode.STRICT)
        // Every configuration Gradle can lock. Suffix filters missed
        // Kotlin/Native *CompileKlibraries, lint models, and KMP
        // androidDeviceTest classpaths. Unavoidable exclusions are
        // listed in docs/DEPENDENCY_REVIEW.md (none today).
        lockAllConfigurations()
    }
}

// Resolve locks by running the real compile/test/lint tasks so AGP/KMP
// variant attributes are present. Invoke as:
//   ./gradlew --no-configuration-cache resolveAndLockAll --write-locks
tasks.register("resolveAndLockAll") {
    notCompatibleWithConfigurationCache("Lock generation walks the task graph")
    doFirst {
        require(gradle.startParameter.isWriteDependencyLocks) {
            "$path must be run with --write-locks"
        }
    }
    val lockTasks =
        listOf(
            ":core:jvmTest",
            ":core:compileKotlinIosArm64",
            ":core:testAndroidHostTest",
            ":crypto:jvmTest",
            ":crypto:compileKotlinIosArm64",
            ":crypto:testAndroidHostTest",
            ":crypto-signing-backend:jvmTest",
            ":crypto-signing-backend:compileKotlinIosArm64",
            ":provider:jvmTest",
            ":provider:compileKotlinIosArm64",
            ":provider:testAndroidHostTest",
            ":provider-blockfrost:jvmTest",
            ":provider-blockfrost:compileKotlinIosArm64",
            ":provider-blockfrost:testAndroidHostTest",
            ":tx:jvmTest",
            ":tx:compileKotlinIosArm64",
            ":tx:testAndroidHostTest",
            ":wallet:jvmTest",
            ":wallet:compileKotlinIosArm64",
            ":wallet:testAndroidHostTest",
            ":shared:jvmTest",
            ":shared:compileKotlinIosArm64",
            ":shared:testAndroidHostTest",
            ":androidApp:assembleDebug",
            ":androidApp:assembleRelease",
            ":androidApp:compileDebugUnitTestKotlin",
            ":androidApp:lintDebug",
            ":androidApp:lintRelease",
            ":desktopApp:compileKotlin",
        )
    dependsOn(lockTasks)
}
