package org.sarmidev.kardano

/** JVM/Desktop [Platform] implementation reporting the running Java version. */
public class JVMPlatform : Platform {
    override val name: String = "Java ${System.getProperty("java.version")}"
}

/** Returns the JVM/Desktop [Platform] descriptor. */
public actual fun getPlatform(): Platform = JVMPlatform()
