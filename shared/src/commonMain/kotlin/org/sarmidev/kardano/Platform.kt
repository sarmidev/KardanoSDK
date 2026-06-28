package org.sarmidev.kardano

interface Platform {
    val name: String
}

expect fun getPlatform(): Platform