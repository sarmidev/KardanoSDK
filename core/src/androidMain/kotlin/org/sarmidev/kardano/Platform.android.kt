package org.sarmidev.kardano

import android.os.Build

/** Android [Platform] implementation reporting the running Android API level. */
public class AndroidPlatform : Platform {
    override val name: String = "Android ${Build.VERSION.SDK_INT}"
}

/** Returns the Android [Platform] descriptor. */
public actual fun getPlatform(): Platform = AndroidPlatform()
