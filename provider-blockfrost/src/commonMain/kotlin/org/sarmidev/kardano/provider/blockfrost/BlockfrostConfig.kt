package org.sarmidev.kardano.provider.blockfrost

/**
 * Configuration for a [BlockfrostChainQueryProvider].
 *
 * The [projectId] is the Blockfrost project API key. It is a runtime value supplied by the
 * caller (for example from a text field, an environment variable, or a gitignored
 * `local.properties`); it is never committed to the repository and this type does not log or
 * persist it. [toString] redacts [projectId] so the key does not appear in logs or diagnostics
 * (note that `equals`/`hashCode` still use it, as for any data class).
 *
 * @property projectId the Blockfrost project API key sent as the `project_id` header.
 * @property network the Blockfrost network target; defaults to [BlockfrostNetwork.PREPROD].
 */
public data class BlockfrostConfig(
    public val projectId: String,
    public val network: BlockfrostNetwork = BlockfrostNetwork.PREPROD,
) {

    /** Renders the config without exposing [projectId], so the key never lands in logs. */
    override fun toString(): String = "BlockfrostConfig(projectId=<redacted>, network=$network)"
}
