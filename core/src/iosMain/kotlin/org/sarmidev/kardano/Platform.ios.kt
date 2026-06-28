package org.sarmidev.kardano

import platform.UIKit.UIDevice

/** iOS [Platform] implementation reporting the running system name and version. */
public class IOSPlatform : Platform {
    override val name: String =
        UIDevice.currentDevice.systemName() + " " + UIDevice.currentDevice.systemVersion
}

/** Returns the iOS [Platform] descriptor. */
public actual fun getPlatform(): Platform = IOSPlatform()
