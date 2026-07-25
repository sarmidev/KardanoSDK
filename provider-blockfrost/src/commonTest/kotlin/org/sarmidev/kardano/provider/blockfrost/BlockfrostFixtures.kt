package org.sarmidev.kardano.provider.blockfrost

/**
 * Sanitized, structurally-valid sample Blockfrost response bodies used by the MockEngine
 * tests. These are **not** captured from a live account: they contain no `project_id`, no
 * real keys, and make no real-funds claim. The transaction hashes are fixed 64-hex-character
 * placeholders and the amounts are illustrative.
 *
 * They live as string constants (rather than resource files) because reading test resources
 * from a Kotlin Multiplatform `commonTest` source set is not portable across the JVM,
 * Android host, and iOS test runtimes; string constants keep the fixtures committed, shared,
 * and platform-independent.
 */
internal object BlockfrostFixtures {

    /** A valid 32-byte (64 hex char) placeholder transaction hash. */
    const val TX_HASH_A: String =
        "1111111111111111111111111111111111111111111111111111111111111111"

    /** A second valid 32-byte placeholder transaction hash. */
    const val TX_HASH_B: String =
        "2222222222222222222222222222222222222222222222222222222222222222"

    /**
     * A single UTxO page (fewer than the page size, so it is the only page). The second entry
     * carries a native asset alongside lovelace: only the lovelace component is summed into
     * `Value.coin`, but (Block 1.11d) its presence is flagged via `Value.hasNativeAssets`
     * rather than silently dropped.
     */
    val UTXOS_SINGLE_PAGE: String =
        """
        [
          {
            "tx_hash": "$TX_HASH_A",
            "output_index": 0,
            "amount": [
              { "unit": "lovelace", "quantity": "5000000" }
            ],
            "block": "sanitized"
          },
          {
            "tx_hash": "$TX_HASH_B",
            "output_index": 1,
            "amount": [
              { "unit": "lovelace", "quantity": "2000000" },
              { "unit": "abc123policyidplusassetname", "quantity": "10" }
            ],
            "block": "sanitized"
          }
        ]
        """.trimIndent()

    /** A single lovelace-only UTxO page entry (Block 1.11d): must not flag native assets. */
    val UTXOS_LOVELACE_ONLY: String =
        """
        [
          {
            "tx_hash": "$TX_HASH_A",
            "output_index": 0,
            "amount": [
              { "unit": "lovelace", "quantity": "3000000" }
            ],
            "block": "sanitized"
          }
        ]
        """.trimIndent()

    /**
     * A single UTxO page entry carrying lovelace plus two distinct native-asset units
     * (Block 1.11d): must flag native assets exactly once, regardless of how many non-lovelace
     * units are present. Quantities/policy ids/asset names are still not represented.
     */
    val UTXOS_LOVELACE_PLUS_MULTIPLE_TOKENS: String =
        """
        [
          {
            "tx_hash": "$TX_HASH_A",
            "output_index": 0,
            "amount": [
              { "unit": "lovelace", "quantity": "3000000" },
              { "unit": "abc123policyidplusassetnameone", "quantity": "1" },
              { "unit": "def456policyidplusassetnametwo", "quantity": "2" }
            ],
            "block": "sanitized"
          }
        ]
        """.trimIndent()

    /** A UTxO entry with a too-short (non-32-byte) tx_hash, to exercise decode failure. */
    val UTXOS_BAD_HASH: String =
        """
        [
          {
            "tx_hash": "abcd",
            "output_index": 0,
            "amount": [ { "unit": "lovelace", "quantity": "5000000" } ]
          }
        ]
        """.trimIndent()

    /** A `GET /epochs/latest/parameters` sample with the mapped subset plus ignored fields. */
    val EPOCH_PARAMETERS: String =
        """
        {
          "epoch": 42,
          "min_fee_a": 44,
          "min_fee_b": 155381,
          "key_deposit": "2000000",
          "pool_deposit": "500000000",
          "max_tx_size": 16384,
          "coins_per_utxo_size": "4310",
          "extra_field_ignored": "ok"
        }
        """.trimIndent()

    /** Epoch parameters with a non-numeric string deposit, to exercise decode failure. */
    val EPOCH_PARAMETERS_MALFORMED: String =
        """
        {
          "min_fee_a": 44,
          "min_fee_b": 155381,
          "key_deposit": "not-a-number",
          "pool_deposit": "500000000",
          "max_tx_size": 16384,
          "coins_per_utxo_size": "4310"
        }
        """.trimIndent()

    /** A `GET /blocks/latest` sample with the mapped subset plus ignored fields. */
    val BLOCK_LATEST: String =
        """
        {
          "time": 1650000000,
          "height": 2000000,
          "hash": "sanitized",
          "slot": 50000000,
          "epoch": 42
        }
        """.trimIndent()

    /** Builds one UTxO array entry with the given output index and lovelace quantity. */
    fun utxoEntry(index: Int, lovelace: String): String =
        """{"tx_hash":"$TX_HASH_A","output_index":$index,"amount":[{"unit":"lovelace","quantity":"$lovelace"}]}"""

    /** Builds a UTxO page (JSON array) of [count] entries with distinct output indices. */
    fun utxoPage(count: Int): String =
        (0 until count).joinToString(separator = ",", prefix = "[", postfix = "]") {
            utxoEntry(it, "1000000")
        }

    /**
     * A sanitized, structurally-valid `POST /tx/submit` success response: a JSON string
     * containing a 64-hex-character placeholder transaction id, quoted exactly as the real
     * Blockfrost API returns it. Not captured from a live submission; no real funds involved.
     */
    val SUBMIT_ACCEPTED: String = "\"$TX_HASH_A\""

    /** A submit success body missing the surrounding quotes (still valid hex). */
    val SUBMIT_ACCEPTED_UNQUOTED: String = TX_HASH_A

    /** A submit success body whose "hex" is too short to be a 32-byte transaction id. */
    val SUBMIT_ACCEPTED_TOO_SHORT: String = "\"abcd\""

    /** A submit success body that is not valid hex at all. */
    val SUBMIT_ACCEPTED_NOT_HEX: String = "\"not-hex-at-all!!\""

    /**
     * A sanitized `400` Blockfrost error envelope, as returned when the node rejects a
     * malformed or conflicting transaction. Not a live capture; no real project id.
     */
    val SUBMIT_REJECTED_BODY: String =
        """
        {
          "status_code": 400,
          "error": "Bad Request",
          "message": "sanitized: transaction submit failed to validate"
        }
        """.trimIndent()

    /** A `403` Blockfrost error envelope (for example an invalid `project_id`). */
    val FORBIDDEN_BODY: String =
        """
        {
          "status_code": 403,
          "error": "Forbidden",
          "message": "sanitized: invalid project token"
        }
        """.trimIndent()
}
