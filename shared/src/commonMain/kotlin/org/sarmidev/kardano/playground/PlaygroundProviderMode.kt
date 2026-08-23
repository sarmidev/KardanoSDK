package org.sarmidev.kardano.playground

/**
 * Which Playground provider actually served a provider-backed operation.
 *
 * [Mock] is the offline in-memory pair (including the case where the live switch is on but the
 * project id is still blank). [LivePreprod] is live Blockfrost preprod — only when the switch
 * is on *and* the project id is non-blank. This is sample-app provenance, not an SDK network
 * type.
 */
internal enum class PlaygroundProviderMode {
    Mock,
    LivePreprod,
}
