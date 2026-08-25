package org.sarmidev.kardano.provider.blockfrost

/**
 * Configuration for a [BlockfrostChainQueryProvider] or [BlockfrostTxSubmitProvider].
 *
 * The [projectId] is the Blockfrost project API key. It is a runtime value supplied by the
 * caller (for example from a text field, an environment variable, or a gitignored
 * `local.properties`); it is never committed to the repository and this type does not log or
 * persist it. [toString] redacts [projectId] so the key does not appear in logs, diagnostics,
 * assertion messages, or collection renderings that use [toString].
 *
 * This is a regular class, not a `data class`. Equality is referential (identity): two
 * instances with the same [projectId] and [network] are not equal, and [hashCode] is the
 * identity hash. That is deliberate. A generated value-equality / hash implementation would
 * retain the raw key, which is what a redacted [toString] is trying to keep out of
 * diagnostics. Call sites construct a config and pass it in; none currently compare, hash,
 * copy, or destructure it. Pre-alpha: `copy` / `componentN` are not generated.
 *
 * @property projectId the Blockfrost project API key sent as the `project_id` header.
 * @property network the Blockfrost network target; defaults to [BlockfrostNetwork.PREPROD].
 */
public class BlockfrostConfig(
    public val projectId: String,
    public val network: BlockfrostNetwork = BlockfrostNetwork.PREPROD,
) {

    /** Renders the config without exposing [projectId], so the key never lands in logs. */
    override fun toString(): String = "BlockfrostConfig(projectId=<redacted>, network=$network)"
}
