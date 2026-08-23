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
    // STRICT lock state for compile/runtime classpaths only.
    // lockAllConfigurations() plus Configuration.resolve() cannot pick a
    // unique AGP variant for Android instrumented-test (and some app)
    // classpaths outside their task graph.
    dependencyLocking {
        lockMode.set(LockMode.STRICT)
    }
    configurations.matching { isLockableClasspath(it) }.configureEach {
        resolutionStrategy.activateDependencyLocking()
    }
}

// Resolve locks by running the real compile/test tasks so AGP/KMP
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
            ":desktopApp:compileKotlin",
        )
    dependsOn(lockTasks)
    // Pure-JVM :desktopApp compile can be UP-TO-DATE and skip resolution,
    // which leaves no gradle.lockfile. Resolve its lockable classpaths
    // after compileKotlin so STRICT mode has state to persist.
    doLast {
        project(":desktopApp").configurations
            .filter { isLockableClasspath(it) }
            .forEach { it.resolve() }
    }
}

fun isLockableClasspath(configuration: Configuration): Boolean {
    if (!configuration.isCanBeResolved) return false
    val name = configuration.name
    if (name.contains("AndroidTest", ignoreCase = true)) return false
    return name.endsWith("CompileClasspath") || name.endsWith("RuntimeClasspath")
}