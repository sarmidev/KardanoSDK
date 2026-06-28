package org.sarmidev.kardano

/**
 * Describes the platform the SDK core is currently running on.
 *
 * This is a UI-free, read-only descriptor used for diagnostics and platform-aware
 * behavior. It does not expose device identifiers or anything sensitive.
 */
public interface Platform {
    /** Human-readable platform name, for example `"Android 36"` or `"Java 17"`. */
    public val name: String
}

/**
 * Returns the [Platform] for the current target.
 *
 * Each Kotlin Multiplatform target provides its own implementation via `actual`.
 *
 * @return the current [Platform] descriptor. Never throws.
 */
public expect fun getPlatform(): Platform
