package org.sarmidev.kardano.playground

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.address.AddressCredential
import org.sarmidev.kardano.address.AddressError
import org.sarmidev.kardano.crypto.derivation.ExtendedPrivateKey
import org.sarmidev.kardano.crypto.derivation.ExtendedPublicKey
import org.sarmidev.kardano.crypto.derivation.IcarusMasterKey
import org.sarmidev.kardano.crypto.derivation.KeyDerivation
import org.sarmidev.kardano.crypto.derivation.KeyDerivationError
import org.sarmidev.kardano.crypto.hashing.CryptoError
import org.sarmidev.kardano.crypto.hashing.Hashing
import org.sarmidev.kardano.crypto.mnemonic.Mnemonic
import org.sarmidev.kardano.crypto.mnemonic.MnemonicError
import org.sarmidev.kardano.crypto.signing.SigningError
import org.sarmidev.kardano.encoding.cbor.Cbor
import org.sarmidev.kardano.encoding.cbor.CborError
import org.sarmidev.kardano.encoding.hex.Hex
import org.sarmidev.kardano.encoding.hex.HexError
import org.sarmidev.kardano.getOrNull
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.provider.ChainQueryProvider
import org.sarmidev.kardano.provider.InMemoryChainQueryProvider
import org.sarmidev.kardano.provider.ProtocolParameters
import org.sarmidev.kardano.provider.ProviderError
import org.sarmidev.kardano.provider.SubmitError
import org.sarmidev.kardano.provider.TxSubmitProvider
import org.sarmidev.kardano.provider.Utxo
import org.sarmidev.kardano.tx.TransactionBuildRequest
import org.sarmidev.kardano.tx.TransactionBuilder
import org.sarmidev.kardano.tx.TransactionDraft
import org.sarmidev.kardano.tx.TransactionOutput
import org.sarmidev.kardano.tx.TxBuildError
import org.sarmidev.kardano.wallet.ExperimentalKardanoSigningScope
import org.sarmidev.kardano.wallet.ReadOnlyWallet
import org.sarmidev.kardano.wallet.SigningScopeViolationReason
import org.sarmidev.kardano.wallet.WalletBalance
import org.sarmidev.kardano.wallet.WalletError
import org.sarmidev.kardano.wallet.WalletSignedTransaction

// ---------------------------------------------------------------------------
// Display models — pure data, no Compose imports
// ---------------------------------------------------------------------------

/** A labeled key-value row for a structured result card. */
internal data class LabeledRow(val label: String, val value: String)

/**
 * The exact message [PlaygroundPresenter.presentSubmitError] returns for
 * [SubmitError.SubmissionNotSupported] — the mock submit provider's honest "no network here"
 * response. Extracted to a named constant (Block 1.12-pre-e) so
 * [org.sarmidev.kardano.playground.mvi.PlaygroundDemoFlow] can recognize this specific,
 * expected mock outcome and present it as a neutral "stopped on purpose" state instead of a
 * generic error, without duplicating or guessing at the literal text.
 */
internal const val MOCK_SUBMISSION_NOT_SUPPORTED_MESSAGE: String =
    "This provider does not support submission (mock) — enable live Blockfrost " +
        "preprod to submit for real."

/** Result of presenting an [Address.parse] call. */
internal sealed interface AddressPresentation {
    data object Empty : AddressPresentation
    data class Success(val rows: List<LabeledRow>) : AddressPresentation
    data class Failure(val message: String) : AddressPresentation
}

/** Result of presenting a [Hex] encode or decode operation. */
internal sealed interface HexPresentation {
    data class EncodeSuccess(val hex: String) : HexPresentation
    data class DecodeSuccess(val byteCount: Int, val hex: String) : HexPresentation
    data class Failure(val message: String) : HexPresentation
}

/** Result of presenting a [Cbor] decode + re-encode pair. */
internal sealed interface CborPresentation {
    data class Success(val summary: String, val roundTripOk: Boolean) : CborPresentation
    data class Failure(val message: String) : CborPresentation
}

/**
 * Result of presenting the test-wallet derivation and address-generation checkpoint
 * ([TestWalletFixture]).
 *
 * Carries only public metadata: the payment and stake CIP-1852 paths, the Blake2b-224
 * credential hash of each derived public key, the generated testnet base address, and its
 * structural round-trip status. Never the mnemonic, entropy, seed, root/private key bytes, or
 * the raw 32-byte public key.
 */
internal sealed interface WalletPresentation {
    data object Empty : WalletPresentation
    data class Success(
        val rows: List<LabeledRow>,
        val fingerprintMatchesVector: Boolean,
    ) : WalletPresentation
    data class Failure(val message: String) : WalletPresentation
}

/** Result of presenting a [ChainQueryProvider.getUtxos] call (mock or live provider). */
internal sealed interface ProviderUtxosPresentation {
    data object Empty : ProviderUtxosPresentation
    data object Loading : ProviderUtxosPresentation
    data class Success(val rows: List<LabeledRow>) : ProviderUtxosPresentation
    data class NoUtxos(val message: String) : ProviderUtxosPresentation
    data class Failure(val message: String) : ProviderUtxosPresentation
}

/** Result of presenting a [ChainQueryProvider.getProtocolParameters] call. */
internal sealed interface ProviderParamsPresentation {
    data object Empty : ProviderParamsPresentation
    data object Loading : ProviderParamsPresentation
    data class Success(val rows: List<LabeledRow>) : ProviderParamsPresentation
    data class Failure(val message: String) : ProviderParamsPresentation
}

/**
 * Result of presenting the read-only wallet-balance checkpoint ([ReadOnlyWallet], Block 1.8b).
 *
 * Carries only public metadata: the generated `addr_test1...` address, the queried UTxO
 * count, and the summed balance in lovelace. Never the mnemonic, entropy, seed, root/private
 * key bytes, or a raw public key. A zero balance/UTxO count is a normal [Success], not a
 * failure — the default in-memory mock provider has no fake UTxOs seeded for the generated
 * wallet address (ADR-0013 §7), so it is expected to show `0`.
 */
internal sealed interface WalletBalancePresentation {
    data object Empty : WalletBalancePresentation
    data object Loading : WalletBalancePresentation
    data class Success(val rows: List<LabeledRow>) : WalletBalancePresentation
    data class Failure(val message: String) : WalletBalancePresentation
}

/**
 * Result of presenting the unsigned minimal-ADA transaction-draft checkpoint
 * ([TransactionBuilder], Block 1.9c).
 *
 * Carries only public metadata about the [TransactionDraft] `:tx` built: selected input/output
 * counts, the fee and optional change amount in lovelace, the encoded body size in bytes, and a
 * truncated hex preview of the body bytes. [TransactionDraft] is itself a structural, unsigned
 * artifact only (ADR-0014 §2) — this presenter formats it, it never signs it, builds a witness
 * set, computes a transaction id, or submits it. [Failure] covers both provider-boundary errors
 * (for example no UTxOs, a network mismatch) and every [TxBuildError] `:tx` can return (for
 * example insufficient funds, an amount below minimum ADA); its message text distinguishes the
 * cause.
 */
internal sealed interface TransactionDraftPresentation {
    data object Empty : TransactionDraftPresentation
    data object Loading : TransactionDraftPresentation
    data class Success(val rows: List<LabeledRow>) : TransactionDraftPresentation
    data class Failure(val message: String) : TransactionDraftPresentation
}

/**
 * Result of presenting the signed-transaction checkpoint
 * ([ReadOnlyWallet.signTestnetFixtureTransaction], Block 1.10c).
 *
 * Carries only public metadata about the [WalletSignedTransaction] built: the 32-byte
 * transaction id (hex), the witness count, a truncated hex preview of the full signed
 * `transaction` CBOR, and an explicit not-submitted/testnet/fixture label. Never the mnemonic,
 * seed, private/root key bytes, or the full (untruncated) signed CBOR. [Failure] covers both
 * the same draft-building errors [TransactionDraftPresentation.Failure] can report and every
 * [WalletError] [ReadOnlyWallet.signTestnetFixtureTransaction] itself can return (for example a
 * signing or transaction-assembly failure); its message text distinguishes the cause. This
 * checkpoint never submits anything — submission is Block 1.11.
 */
internal sealed interface SignedTransactionPresentation {
    data object Empty : SignedTransactionPresentation
    data object Loading : SignedTransactionPresentation
    data class Success(val rows: List<LabeledRow>) : SignedTransactionPresentation
    data class Failure(val message: String) : SignedTransactionPresentation
}

/**
 * Result of presenting the submit-transaction checkpoint ([TxSubmitProvider.submit], Block
 * 1.11c).
 *
 * Carries only public metadata: the accepted transaction id returned by the provider, the
 * locally-signed transaction id computed by [ReadOnlyWallet.signTestnetFixtureTransaction]
 * (Block 1.10c), whether the two match, and an explicit submitted/preprod/test-fixture label.
 * Never the mnemonic, seed, private/root key bytes, or the full (untruncated) signed CBOR. [Failure]
 * covers every [SubmitError] variant [TxSubmitProvider.submit] can return, plus the same
 * draft-building and signing failures [SignedTransactionPresentation.Failure] can report —
 * building and signing happen first, so this checkpoint only calls `submit` on an
 * already-signed draft.
 */
internal sealed interface SubmitTransactionPresentation {
    data object Empty : SubmitTransactionPresentation
    data object Loading : SubmitTransactionPresentation
    data class Success(val rows: List<LabeledRow>) : SubmitTransactionPresentation
    data class Failure(val message: String) : SubmitTransactionPresentation
}

// ---------------------------------------------------------------------------
// Presenter — maps :core results to display models; no SDK logic of its own
// ---------------------------------------------------------------------------

/**
 * Maps results from `:core`, `:crypto`, `:provider`, `:wallet`, and `:tx` APIs to
 * [AddressPresentation], [HexPresentation], [CborPresentation], [WalletPresentation],
 * [ProviderUtxosPresentation], [ProviderParamsPresentation], [WalletBalancePresentation],
 * [TransactionDraftPresentation], [SignedTransactionPresentation], and
 * [SubmitTransactionPresentation] for display in [PlaygroundScreen].
 *
 * This object only formats and labels results. It never re-parses, re-validates, or
 * reimplements any protocol rule, derivation, hashing, address-generation, balance-summation,
 * coin-selection, fee/change, or CBOR-encoding logic. All of that semantics comes from
 * `:core`/`:crypto`/`:provider`/`:wallet`/`:tx`.
 *
 * This is sample/diagnostic code in `:shared`. It is not part of the SDK public API.
 */
internal object PlaygroundPresenter {

    /** Bytes of a credential hash shown as a short hex prefix in the UI. */
    private const val SHORT_HEX_PREFIX_BYTES: Int = 6

    // --- Address ---

    /**
     * Maps an [Address.parse] result to an [AddressPresentation].
     *
     * Structural validation only — [Address.parse] makes no claim about on-chain existence,
     * ownership, or spendability; this presenter carries the same limitation forward.
     */
    fun presentAddress(result: KardanoResult<Address, AddressError>): AddressPresentation =
        when (result) {
            is KardanoResult.Ok -> buildSuccess(result.value)
            is KardanoResult.Err -> AddressPresentation.Failure(presentAddressError(result.error))
        }

    private fun buildSuccess(address: Address): AddressPresentation.Success {
        val rows = buildList {
            add(LabeledRow("Network", address.network.name))
            add(LabeledRow("Type", address.type.name))
            add(LabeledRow("HRP", address.hrp.value))
            address.paymentCredential?.let { cred ->
                add(LabeledRow("Payment credential", cred.kind.name))
                add(LabeledRow("Payment hash (prefix)", shortHex(cred.hashBytes())))
            }
            address.stakeCredential?.let { cred ->
                add(LabeledRow("Stake credential", cred.kind.name))
                add(LabeledRow("Stake hash (prefix)", shortHex(cred.hashBytes())))
            }
            address.pointer?.let { ptr ->
                add(LabeledRow("Pointer slot", ptr.slot.toString()))
                add(LabeledRow("Pointer tx index", ptr.transactionIndex.toString()))
                add(LabeledRow("Pointer cert index", ptr.certificateIndex.toString()))
            }
        }
        return AddressPresentation.Success(rows)
    }

    /**
     * Maps an [AddressError] to a human-readable single-line message.
     *
     * Internal so tests can exercise all error variants by constructing them directly,
     * without needing a specific input string to trigger each one.
     */
    internal fun presentAddressError(error: AddressError): String = when (error) {
        is AddressError.Bech32 ->
            "Bech32 error: ${error.error}"
        is AddressError.InvalidBitConversion ->
            "Bit conversion error: ${error.error}"
        is AddressError.EmptyPayload ->
            "Empty payload: no header byte to inspect"
        is AddressError.UnsupportedAddressType ->
            "Unsupported address type (header nibble ${error.headerTypeNibble})"
        is AddressError.UnsupportedNetworkId ->
            "Unsupported network id: ${error.error}"
        is AddressError.HrpNetworkMismatch ->
            "HRP/network mismatch: hrp=${error.hrp.value}, header network=${error.headerNetwork.name}"
        is AddressError.HrpFamilyMismatch ->
            "HRP/family mismatch: hrp=${error.hrp.value}, type=${error.type.name}"
        is AddressError.InvalidPayloadLength ->
            "Invalid payload length: expected ${error.expected}, got ${error.actual} (type=${error.type.name})"
        is AddressError.InvalidCredentialLength ->
            "Invalid credential length: expected ${error.expected}, got ${error.actual}"
        is AddressError.TruncatedPointer ->
            "Pointer truncated: payload ended before all pointer fields were read"
        is AddressError.PointerValueOutOfRange ->
            "Pointer value out of range: field=${error.field.name}"
        is AddressError.NonCanonicalPointer ->
            "Non-canonical pointer encoding: field=${error.field.name}"
        is AddressError.TrailingPointerBytes ->
            "Trailing bytes after pointer: consumed ${error.consumed}, total ${error.actual}"
    }

    // --- Hex ---

    /**
     * Attempts to decode [input] as a hex string.
     *
     * Returns [HexPresentation.DecodeSuccess] with the byte count and re-encoded hex on
     * success, or [HexPresentation.Failure] on [HexError].
     */
    fun presentHexDecode(input: String): HexPresentation =
        when (val result = Hex.decode(input.trim())) {
            is KardanoResult.Ok -> {
                val bytes = result.value
                // Hex.decode's own input limit bounds bytes.size to at most
                // Hex.MAX_ENCODE_INPUT_BYTES (Hex.MAX_INPUT_CHARS / 2), so this re-encode
                // cannot exceed Hex.encode's own limit; the Err branch is not reachable here,
                // but is still handled rather than assumed.
                when (val encoded = Hex.encode(bytes)) {
                    is KardanoResult.Ok -> HexPresentation.DecodeSuccess(bytes.size, encoded.value)
                    is KardanoResult.Err -> HexPresentation.Failure(presentHexError(encoded.error))
                }
            }
            is KardanoResult.Err -> HexPresentation.Failure(presentHexError(result.error))
        }

    /**
     * Encodes [bytes] to canonical lowercase hex.
     */
    fun presentHexEncode(bytes: ByteArray): HexPresentation =
        when (val result = Hex.encode(bytes)) {
            is KardanoResult.Ok -> HexPresentation.EncodeSuccess(result.value)
            is KardanoResult.Err -> HexPresentation.Failure(presentHexError(result.error))
        }

    private fun presentHexError(error: HexError): String = when (error) {
        is HexError.InputTooLong -> "Input too long: ${error.actual} chars (max ${error.max})"
        is HexError.EncodeInputTooLong -> "Input too long: ${error.actual} bytes (max ${error.max})"
        is HexError.OddLength -> "Odd length: ${error.length} chars"
        is HexError.InvalidCharacter -> "Invalid character '${error.char}' at index ${error.index}"
    }

    /**
     * Encodes [bytes] to lowercase hex for display, or a bracketed placeholder if [bytes]
     * somehow exceeded [Hex.MAX_ENCODE_INPUT_BYTES].
     *
     * Every call site of this helper passes a small, internally-bounded array — a Blake2b
     * digest (28 or 32 bytes) or a short preview-prefix slice — so the placeholder branch is
     * not expected to be reachable from any current Playground flow; it exists so this
     * presenter never throws instead of silently assuming [Hex.encode] cannot fail.
     */
    private fun hexOrPlaceholder(bytes: ByteArray): String = when (val result = Hex.encode(bytes)) {
        is KardanoResult.Ok -> result.value
        is KardanoResult.Err -> "<hex encode error: ${presentHexError(result.error)}>"
    }

    // --- CBOR ---

    /**
     * Decodes [hexInput] as hex, then decodes the resulting bytes as CBOR, and reports
     * whether a canonical re-encode round-trips to the same bytes.
     *
     * Returns [CborPresentation.Failure] on any hex or CBOR decode error.
     */
    fun presentCbor(hexInput: String): CborPresentation {
        val bytes = when (val hexResult = Hex.decode(hexInput.trim())) {
            is KardanoResult.Ok -> hexResult.value
            is KardanoResult.Err ->
                return CborPresentation.Failure("Hex error: ${presentHexError(hexResult.error)}")
        }
        val value = when (val cborResult = Cbor.decode(bytes)) {
            is KardanoResult.Ok -> cborResult.value
            is KardanoResult.Err ->
                return CborPresentation.Failure("CBOR error: ${presentCborError(cborResult.error)}")
        }
        val summary = value.toString()
        val roundTripOk = when (val encResult = Cbor.encode(value)) {
            is KardanoResult.Ok -> encResult.value.contentEquals(bytes)
            is KardanoResult.Err -> false
        }
        return CborPresentation.Success(summary, roundTripOk)
    }

    private fun presentCborError(error: CborError): String = error.toString()

    // --- Test wallet + address generation checkpoint (Block 1.6d, extended by Block 1.7b) ---

    /**
     * Restores [TestWalletFixture]'s cited test-only mnemonic, derives the payment
     * ([TestWalletFixture.paymentPath]) and stake ([TestWalletFixture.stakePath]) keys,
     * hashes each derived public key to a credential, builds a testnet base address from the
     * two credentials, and immediately re-parses that address — displaying only this public
     * metadata.
     *
     * Delegates entirely to `:crypto` ([Mnemonic], [IcarusMasterKey], [KeyDerivation],
     * [Hashing]) and `:core` ([AddressCredential], [Address]); this presenter does not
     * reimplement or duplicate any derivation, hashing, or address-encoding logic. This is
     * **structural address generation only** (Block 1.7a/1.7b): it does not sign anything,
     * build a transaction, or prove the generated address is owned, funded, or registered.
     * Never surfaces the mnemonic, entropy, seed, root/private key bytes, or a raw public key
     * — only path strings, credential-hash hex, and the generated/re-parsed address.
     */
    fun presentTestWallet(): WalletPresentation = presentTestWalletWithWords(TestWalletFixture.words)

    /**
     * Same chain as [presentTestWallet], but over an arbitrary [words] list instead of the
     * fixture's cited mnemonic. Exists so invalid-input handling can be exercised (including in
     * tests) without changing [TestWalletFixture] itself. [Mnemonic.parse] runs first and
     * rejects malformed input before any native derivation call is reached.
     */
    fun presentTestWalletWithWords(words: List<String>): WalletPresentation {
        val mnemonic = when (val result = Mnemonic.parse(words)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> return WalletPresentation.Failure(presentMnemonicError(result.error))
        }
        var master: IcarusMasterKey? = null
        var paymentPrivateKey: ExtendedPrivateKey? = null
        var paymentPublicKey: ExtendedPublicKey? = null
        var stakePrivateKey: ExtendedPrivateKey? = null
        var stakePublicKey: ExtendedPublicKey? = null
        try {
            master = when (val result = IcarusMasterKey.fromMnemonic(mnemonic)) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err ->
                    return WalletPresentation.Failure(presentKeyDerivationError(result.error))
            }
            val derivation = KeyDerivation.default()

            paymentPrivateKey = when (
                val result = derivation.derivePrivate(master, TestWalletFixture.paymentPath)
            ) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err ->
                    return WalletPresentation.Failure(presentKeyDerivationError(result.error))
            }
            paymentPublicKey = when (val result = derivation.publicKey(paymentPrivateKey)) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err ->
                    return WalletPresentation.Failure(presentKeyDerivationError(result.error))
            }
            val paymentDigest = when (
                val result = Hashing.default().blake2b224(paymentPublicKey.publicKeyBytes())
            ) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err -> return WalletPresentation.Failure(presentCryptoError(result.error))
            }
            val paymentFingerprintHex = hexOrPlaceholder(paymentDigest.toByteArray())
            val paymentCredential = when (
                val result = AddressCredential.keyHash(paymentDigest.toByteArray())
            ) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err -> return WalletPresentation.Failure(presentAddressError(result.error))
            }

            stakePrivateKey = when (
                val result = derivation.derivePrivate(master, TestWalletFixture.stakePath)
            ) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err ->
                    return WalletPresentation.Failure(presentKeyDerivationError(result.error))
            }
            stakePublicKey = when (val result = derivation.publicKey(stakePrivateKey)) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err ->
                    return WalletPresentation.Failure(presentKeyDerivationError(result.error))
            }
            val stakeDigest = when (
                val result = Hashing.default().blake2b224(stakePublicKey.publicKeyBytes())
            ) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err -> return WalletPresentation.Failure(presentCryptoError(result.error))
            }
            val stakeFingerprintHex = hexOrPlaceholder(stakeDigest.toByteArray())
            val stakeCredential = when (
                val result = AddressCredential.keyHash(stakeDigest.toByteArray())
            ) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err -> return WalletPresentation.Failure(presentAddressError(result.error))
            }

            val generatedAddress = when (
                val result = Address.baseAddress(Network.TESTNET, paymentCredential, stakeCredential)
            ) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err -> return WalletPresentation.Failure(presentAddressError(result.error))
            }
            val generatedBech32 = generatedAddress.toBech32()
            val roundTripOk = when (val result = Address.parse(generatedBech32)) {
                is KardanoResult.Ok -> result.value == generatedAddress
                is KardanoResult.Err -> false
            }

            val rows = listOf(
                LabeledRow("Payment path", TestWalletFixture.paymentPath.toString()),
                LabeledRow("Payment credential (Blake2b-224)", paymentFingerprintHex),
                LabeledRow("Stake path", TestWalletFixture.stakePath.toString()),
                LabeledRow("Stake credential (Blake2b-224)", stakeFingerprintHex),
                LabeledRow("Generated address", generatedBech32),
                LabeledRow("Address round-trip", if (roundTripOk) "ok" else "mismatch"),
            )
            return WalletPresentation.Success(
                rows = rows,
                fingerprintMatchesVector = paymentFingerprintHex == TestWalletFixture.GOLDEN_FINGERPRINT_HEX,
            )
        } finally {
            mnemonic.clear()
            master?.clear()
            paymentPrivateKey?.clear()
            paymentPublicKey?.clear()
            stakePrivateKey?.clear()
            stakePublicKey?.clear()
        }
    }


    /** Maps a [MnemonicError] to a human-readable single-line message. */
    internal fun presentMnemonicError(error: MnemonicError): String = when (error) {
        is MnemonicError.InvalidWordCount -> "Invalid word count: ${error.count}"
        is MnemonicError.WordNotInWordlist -> "Word not in wordlist at position ${error.position}"
        is MnemonicError.ChecksumMismatch -> "Mnemonic checksum mismatch"
        is MnemonicError.InvalidCharacters -> "Invalid characters at word position ${error.position}"
        is MnemonicError.InputTooLong ->
            "Mnemonic phrase too long: ${error.actual} chars (max ${error.max})"
    }

    /** Maps a [KeyDerivationError] to a human-readable single-line message. */
    internal fun presentKeyDerivationError(error: KeyDerivationError): String = when (error) {
        is KeyDerivationError.InvalidKeyMaterial ->
            "Invalid key material: expected ${error.expectedBytes}B, got ${error.actualBytes}B"
        is KeyDerivationError.IndexOutOfRange -> "Derivation index out of range: ${error.value}"
        is KeyDerivationError.SoftDerivationRequired -> "Soft derivation required for this index"
        is KeyDerivationError.DerivationFailed -> "Derivation failed: ${error.message}"
        is KeyDerivationError.PublicKeyProjectionUnavailable ->
            "Public-key projection is not available on this platform"
    }

    /** Maps a [CryptoError] to a human-readable single-line message. */
    internal fun presentCryptoError(error: CryptoError): String = when (error) {
        is CryptoError.InputTooLong ->
            "Hash input too long: max ${error.max}B, got ${error.actual}B"
        is CryptoError.HashingFailed -> "Hashing failed: ${error.message}"
        is CryptoError.InvalidDigestLength ->
            "Invalid digest length: expected ${error.expected}B, got ${error.actual}B"
    }

    // --- Provider (read-only; provider-agnostic: mock or live) ---

    /**
     * Parses [addressInput] and queries [provider] for its UTxOs, mapping the result to a
     * [ProviderUtxosPresentation]. A parse failure is reported as
     * [ProviderUtxosPresentation.Failure]; an empty (but valid) result is reported as
     * [ProviderUtxosPresentation.NoUtxos], not an error.
     *
     * This is provider-agnostic: it works with any [ChainQueryProvider]. The caller decides
     * whether [provider] is the in-memory mock (fake/test-only) or a live provider (for example
     * Blockfrost preprod); this presenter does not know or care which.
     */
    suspend fun presentProviderUtxos(
        provider: ChainQueryProvider,
        addressInput: String,
    ): ProviderUtxosPresentation {
        val address = when (val parsed = Address.parse(addressInput.trim())) {
            is KardanoResult.Ok -> parsed.value
            is KardanoResult.Err ->
                return ProviderUtxosPresentation.Failure(presentAddressError(parsed.error))
        }
        return mapUtxosResult(provider.getUtxos(address))
    }

    /**
     * Queries [provider] for protocol parameters and maps the result to a
     * [ProviderParamsPresentation]. Provider-agnostic: the caller decides whether [provider] is
     * the in-memory mock (fake/test-only) or a live provider (for example Blockfrost preprod).
     */
    suspend fun presentProviderParams(
        provider: ChainQueryProvider,
    ): ProviderParamsPresentation = mapParamsResult(provider.getProtocolParameters())

    /**
     * Maps a raw `getUtxos` result to a [ProviderUtxosPresentation]. An empty (but Ok) result
     * is [ProviderUtxosPresentation.NoUtxos], not a failure. Non-suspend and `internal` so it
     * can be unit-tested by constructing results directly.
     */
    internal fun mapUtxosResult(
        result: KardanoResult<List<Utxo>, ProviderError>,
    ): ProviderUtxosPresentation = when (result) {
        is KardanoResult.Ok ->
            if (result.value.isEmpty()) {
                ProviderUtxosPresentation.NoUtxos("No UTxOs for this address.")
            } else {
                ProviderUtxosPresentation.Success(result.value.map(::utxoRow))
            }
        is KardanoResult.Err ->
            ProviderUtxosPresentation.Failure(presentProviderError(result.error))
    }

    /**
     * Maps a raw `getProtocolParameters` result to a [ProviderParamsPresentation]. Non-suspend
     * and `internal` so it can be unit-tested by constructing results directly.
     */
    internal fun mapParamsResult(
        result: KardanoResult<ProtocolParameters, ProviderError>,
    ): ProviderParamsPresentation = when (result) {
        is KardanoResult.Ok -> ProviderParamsPresentation.Success(paramsRows(result.value))
        is KardanoResult.Err ->
            ProviderParamsPresentation.Failure(presentProviderError(result.error))
    }

    private fun utxoRow(utxo: Utxo): LabeledRow {
        val ref = "${shortHex(utxo.ref.txHash.toByteArray())}#${utxo.ref.outputIndex}"
        return LabeledRow(ref, "${utxo.value.coin.value} lovelace")
    }

    private fun paramsRows(params: ProtocolParameters): List<LabeledRow> = listOf(
        LabeledRow("minFeeCoefficient", params.minFeeCoefficient.toString()),
        LabeledRow("minFeeConstant", params.minFeeConstant.toString()),
        LabeledRow("keyDeposit", params.keyDeposit.toString()),
        LabeledRow("poolDeposit", params.poolDeposit.toString()),
        LabeledRow("maxTxSize", params.maxTxSize.toString()),
        LabeledRow("coinsPerUtxoByte", params.coinsPerUtxoByte.toString()),
    )

    /** Maps a [ProviderError] to a human-readable single-line message. */
    internal fun presentProviderError(error: ProviderError): String = when (error) {
        is ProviderError.Transport -> "Transport error: ${error.message}"
        is ProviderError.RemoteStatus -> "Remote status: ${error.code}"
        is ProviderError.NotFound -> "Not found"
        is ProviderError.Deserialization -> "Decode error: ${error.detail}"
        is ProviderError.RateLimited -> "Rate limited"
        is ProviderError.NetworkMismatch ->
            "Network mismatch: provider=${error.expected.name}, address=${error.actual.name}"
        is ProviderError.Unknown -> "Unknown provider error"
    }

    // --- Wallet balance (read-only; Block 1.8b) ---

    /**
     * Restores [TestWalletFixture]'s cited test-only mnemonic through
     * [ReadOnlyWallet.restore], always with [Network.TESTNET] — this checkpoint never
     * constructs, displays, or restores a mainnet wallet (Phase 1 no-mainnet boundary,
     * ADR-0005 §7) — then queries [provider] for that wallet's balance.
     *
     * Delegates entirely to `:wallet` ([ReadOnlyWallet]); this presenter does not reimplement
     * mnemonic parsing, key derivation, hashing, address generation, or balance summation —
     * it only formats the result. Provider-agnostic: the caller decides whether [provider] is
     * the in-memory mock (fake/test-only, and expected to show a zero balance for this
     * generated address per ADR-0013 §7) or a live provider (for example Blockfrost preprod,
     * which can show a non-zero balance only after the generated address is funded from a
     * preprod faucet).
     */
    suspend fun presentWalletBalance(provider: ChainQueryProvider): WalletBalancePresentation {
        val wallet = when (val result = ReadOnlyWallet.restore(TestWalletFixture.words, Network.TESTNET)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> return WalletBalancePresentation.Failure(presentWalletError(result.error))
        }
        return mapWalletBalanceResult(wallet.address, wallet.balance(provider))
    }

    /**
     * Maps a raw [ReadOnlyWallet.balance] result (for [address]) to a
     * [WalletBalancePresentation]. Non-suspend and `internal` so it can be unit-tested by
     * constructing a [WalletBalance] or [WalletError] directly, without restoring a mnemonic
     * or reaching native cryptography.
     */
    internal fun mapWalletBalanceResult(
        address: Address,
        result: KardanoResult<WalletBalance, WalletError>,
    ): WalletBalancePresentation = when (result) {
        is KardanoResult.Ok -> WalletBalancePresentation.Success(walletBalanceRows(address, result.value))
        is KardanoResult.Err -> WalletBalancePresentation.Failure(presentWalletError(result.error))
    }

    private fun walletBalanceRows(address: Address, balance: WalletBalance): List<LabeledRow> = listOf(
        LabeledRow("Address", address.toBech32()),
        LabeledRow("UTxO count", balance.utxoCount.toString()),
        LabeledRow("Balance", "${balance.coin.value} lovelace"),
        LabeledRow("Test ADA", LovelaceDisplay.ada(balance.coin)),
    )

    /**
     * Maps a [WalletError] to a human-readable single-line message, delegating to the
     * existing per-error-type presenters ([presentMnemonicError], [presentKeyDerivationError],
     * [presentCryptoError], [presentAddressError], [presentProviderError], [presentSigningError],
     * [presentTxBuildError]) for every wrapped variant, so no formatting logic is duplicated.
     * [WalletError.BalanceOverflow] is the one variant `:wallet` owns itself.
     *
     * Internal so tests can exercise all variants by constructing them directly.
     */
    internal fun presentWalletError(error: WalletError): String = when (error) {
        is WalletError.Mnemonic -> presentMnemonicError(error.error)
        is WalletError.Derivation -> presentKeyDerivationError(error.error)
        is WalletError.Hashing -> presentCryptoError(error.error)
        is WalletError.AddressBuild -> presentAddressError(error.error)
        is WalletError.Provider -> presentProviderError(error.error)
        is WalletError.BalanceOverflow ->
            "Balance overflow after summing ${error.partialCount} UTxO(s)"
        is WalletError.Signing -> "Signing failed: ${presentSigningError(error.error)}"
        is WalletError.TransactionAssembly ->
            "Transaction assembly failed: ${presentTxBuildError(error.error)}"
        is WalletError.InvariantViolation -> "Internal error: ${error.detail}"
        is WalletError.SigningScopeViolation -> presentSigningScopeViolation(error.reason)
    }

    /**
     * Maps a [SigningScopeViolationReason] to a human-readable single-line message. Names the
     * rejected network or scope without implying a readiness claim (ADR-0019).
     */
    internal fun presentSigningScopeViolation(reason: SigningScopeViolationReason): String =
        when (reason) {
            is SigningScopeViolationReason.UnsupportedDraftScope ->
                "Signing rejected: draft scope ${reason.scope} is not the Phase 1 ADA-only " +
                    "single-payment path."
            is SigningScopeViolationReason.UnsupportedDraftNetwork ->
                "Signing rejected: draft was built for ${reason.draftNetwork.name}, not testnet."
            is SigningScopeViolationReason.DeclaredNetworkMismatch ->
                "Signing rejected: declared network ${reason.declared.name} does not match " +
                    "draft network ${reason.draftNetwork.name}."
            is SigningScopeViolationReason.UnsupportedDraftShape ->
                "Signing rejected: draft shape is not the Phase 1 ADA-only single-payment " +
                    "path (${reason.detail})."
        }

    /**
     * Maps a [SigningError] to a human-readable single-line message. Never renders key,
     * signature, or message bytes — [SigningError] itself carries none.
     *
     * Internal so tests can exercise all variants by constructing them directly.
     */
    internal fun presentSigningError(error: SigningError): String = when (error) {
        is SigningError.InvalidBodyHashLength ->
            "Invalid body hash length: expected ${error.expectedBytes}B, got ${error.actualBytes}B"
        is SigningError.InvalidKeyMaterial ->
            "Invalid key material: expected ${error.expectedBytes}B, got ${error.actualBytes}B"
        is SigningError.BackendFailed -> "Signing backend failed: ${error.message}"
        is SigningError.SigningUnavailable -> "Signing is not available on this platform"
    }

    // --- Transaction Draft (unsigned; Block 1.9c) ---

    /**
     * The fixed test-only payment recipient for the transaction-draft checkpoint: the same
     * cited CIP-19 testnet vector already used as [InMemoryChainQueryProvider.SEED_ADDRESS_EMPTY]
     * elsewhere in this Playground. Reused here as a payment destination rather than an
     * invented address; the role it plays there (an address with no seeded UTxOs) does not
     * conflict with also being a valid destination for this unrelated draft's single payment.
     */
    private val transactionDraftRecipient: Address = requireNotNull(
        Address.parse(InMemoryChainQueryProvider.SEED_ADDRESS_EMPTY).getOrNull(),
    ) { "InMemoryChainQueryProvider.SEED_ADDRESS_EMPTY is a fixed, already-valid CIP-19 vector" }

    /** The fixed test-only payment amount for the transaction-draft checkpoint: 2 ADA. */
    private val transactionDraftPaymentAmount: Lovelace = requireNotNull(
        Lovelace.of(2_000_000L).getOrNull(),
    ) { "2,000,000 lovelace is a fixed, in-range constant" }

    /** Bytes of the body-CBOR hex preview shown in the UI before truncating with "…". */
    private const val BODY_HEX_PREVIEW_BYTES: Int = 24

    /**
     * Restores [TestWalletFixture]'s cited test-only mnemonic through [ReadOnlyWallet.restore]
     * (always [Network.TESTNET] — the Phase 1 no-mainnet boundary, ADR-0005 §7), queries
     * [provider] for that wallet's candidate UTxOs and the current protocol parameters, then
     * calls [TransactionBuilder.build] for a minimal, single-payment, unsigned transaction
     * draft paying [transactionDraftPaymentAmount] to [transactionDraftRecipient] with change
     * returned to the restored wallet's own address.
     *
     * Delegates entirely to `:wallet` ([ReadOnlyWallet]) and `:tx` ([TransactionBuilder]); this
     * presenter does not select inputs, estimate a fee, decide change, or encode any CBOR
     * itself — it only builds the request and formats the result. **No signing, no witness
     * construction, no transaction id hashing, no submission**: [TransactionDraft] is a
     * structural, unsigned artifact only (ADR-0014 §2). Provider-agnostic: the caller decides
     * whether [provider] is the in-memory mock (fake/test-only) or a live provider (for example
     * Blockfrost preprod). Under the default [InMemoryChainQueryProvider], the restored
     * wallet's self-generated address has no fake UTxOs seeded for it (same honest-empty
     * behavior as [presentWalletBalance], ADR-0013 §7), so this normally reports the resulting
     * [TxBuildError.NoInputs] as a [TransactionDraftPresentation.Failure] — not a crash. Fund
     * that address via a live Blockfrost preprod faucet to see a
     * [TransactionDraftPresentation.Success].
     */
    suspend fun presentTransactionDraft(provider: ChainQueryProvider): TransactionDraftPresentation =
        when (val outcome = buildTransactionDraft(provider)) {
            is DraftBuildOutcome.Built -> mapTransactionDraftResult(outcome.result)
            is DraftBuildOutcome.Failed -> TransactionDraftPresentation.Failure(outcome.message)
        }

    /** The outcome of [buildTransactionDraft]: either a `:tx` build result, or an already-formatted failure. */
    private sealed interface DraftBuildOutcome {
        data class Built(val result: KardanoResult<TransactionDraft, TxBuildError>) : DraftBuildOutcome
        data class Failed(val message: String) : DraftBuildOutcome
    }

    /**
     * Restores [TestWalletFixture]'s cited test-only mnemonic through [ReadOnlyWallet.restore]
     * (always [Network.TESTNET]), queries [provider] for that wallet's candidate UTxOs and the
     * current protocol parameters, and calls [TransactionBuilder.build] for the same minimal,
     * single-payment, unsigned transaction draft [presentTransactionDraft] builds (Block 1.9c).
     *
     * Shared by [presentTransactionDraft] and [presentSignedTransaction] (Block 1.10c) so both
     * checkpoints build the identical draft through one code path — this presenter still does
     * not select inputs, estimate a fee, decide change, or encode any CBOR itself.
     */
    private suspend fun buildTransactionDraft(provider: ChainQueryProvider): DraftBuildOutcome {
        val wallet = when (val result = ReadOnlyWallet.restore(TestWalletFixture.words, Network.TESTNET)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> return DraftBuildOutcome.Failed(presentWalletError(result.error))
        }
        val candidateInputs = when (val result = provider.getUtxos(wallet.address)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> return DraftBuildOutcome.Failed(presentProviderError(result.error))
        }
        val protocolParameters = when (val result = provider.getProtocolParameters()) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> return DraftBuildOutcome.Failed(presentProviderError(result.error))
        }
        val request = TransactionBuildRequest(
            network = Network.TESTNET,
            candidateInputs = candidateInputs,
            payment = TransactionOutput(transactionDraftRecipient, transactionDraftPaymentAmount),
            changeAddress = wallet.address,
            protocolParameters = protocolParameters,
            ttl = null,
        )
        return DraftBuildOutcome.Built(TransactionBuilder.build(request))
    }

    /**
     * Maps a raw [TransactionBuilder.build] result to a [TransactionDraftPresentation].
     * Non-suspend and `internal` so it can be unit-tested by constructing a [TransactionDraft]
     * or [TxBuildError] directly, without restoring a mnemonic, reaching native cryptography,
     * or querying a provider.
     */
    internal fun mapTransactionDraftResult(
        result: KardanoResult<TransactionDraft, TxBuildError>,
    ): TransactionDraftPresentation = when (result) {
        is KardanoResult.Ok -> TransactionDraftPresentation.Success(transactionDraftRows(result.value))
        is KardanoResult.Err -> TransactionDraftPresentation.Failure(presentTxBuildError(result.error))
    }

    private fun transactionDraftRows(draft: TransactionDraft): List<LabeledRow> {
        val bodyBytes = draft.bodyCbor()
        val paymentOutput = draft.outputs.getOrNull(0)
        val changeOutput = draft.outputs.getOrNull(1)
        return buildList {
            add(LabeledRow("Selected inputs", draft.selectedInputs.size.toString()))
            add(LabeledRow("Outputs", draft.outputs.size.toString()))
            add(LabeledRow("Fee", "${draft.fee.value} lovelace"))
            changeOutput?.let { add(LabeledRow("Change", "${it.amount.value} lovelace")) }
            add(LabeledRow("Body size", "${bodyBytes.size} bytes"))
            add(LabeledRow("Body CBOR (preview)", bodyHexPreview(bodyBytes)))
            add(LabeledRow("Status", "Unsigned draft — not signed, not submitted"))
            paymentOutput?.let { add(LabeledRow("Payment", LovelaceDisplay.ada(it.amount))) }
            add(LabeledRow("Network cost", LovelaceDisplay.ada(draft.fee)))
            changeOutput?.let { add(LabeledRow("Change back", LovelaceDisplay.ada(it.amount))) }
        }
    }

    private fun bodyHexPreview(bytes: ByteArray): String {
        val prefixLength = minOf(BODY_HEX_PREVIEW_BYTES, bytes.size)
        val hex = hexOrPlaceholder(bytes.copyOf(prefixLength))
        return if (bytes.size > prefixLength) "$hex… (${bytes.size}B total)" else hex
    }

    /**
     * Maps a [TxBuildError] to a human-readable single-line message, distinguishing the cause
     * (no inputs, insufficient funds, below minimum ADA, and so on, plus the Block 1.10b
     * witness/assembly variants — [TxBuildError.InvalidVerificationKeyLength],
     * [TxBuildError.InvalidSignatureLength], [TxBuildError.EmptyWitnessSet] — reachable via
     * [WalletError.TransactionAssembly]) in the text.
     *
     * [TxBuildError.UnsupportedFeature] (Block 1.11d, narrowed in 1.11d-2) gets a dedicated,
     * plain-language message rather than the generic `"Unsupported feature: ..."` phrasing
     * every other variant's message pattern might suggest, because — as of this block — it has
     * exactly one reachable cause: *every* candidate UTxO carried native assets/tokens, leaving
     * no ADA-only UTxO to build from at all (see that variant's KDoc). A wallet with a *mix* of
     * ADA-only and native-asset UTxOs never reaches this branch: [TransactionBuilder.build]
     * builds from the ADA-only ones instead, or reports [TxBuildError.InsufficientFunds] (whose
     * message below is unchanged) if even those cannot cover `payment + fee`. If a future block
     * adds a second, unrelated cause for [TxBuildError.UnsupportedFeature], this mapping must be
     * revisited to distinguish them (for example by inspecting
     * [TxBuildError.UnsupportedFeature.detail]).
     *
     * Internal so tests can exercise all variants by constructing them directly.
     */
    internal fun presentTxBuildError(error: TxBuildError): String = when (error) {
        is TxBuildError.NoInputs -> "No UTxOs available to build a transaction from."
        is TxBuildError.NoOutputs -> "No outputs to encode (internal: missing payment output)."
        is TxBuildError.InvalidProtocolParameters ->
            "Invalid protocol parameters: ${error.field} = ${error.value}"
        is TxBuildError.FeeEstimateDidNotConverge ->
            "Fee estimate did not converge: encoded ${error.encodedFee}, " +
                "recomputed ${error.recomputedFee} lovelace"
        is TxBuildError.InsufficientFunds ->
            "Insufficient funds: need ${error.required} lovelace, have ${error.available} lovelace"
        is TxBuildError.InvalidOutputAmount ->
            "Payment amount ${error.amount} lovelace is below the minimum ADA " +
                "(${error.minRequired}) for this output"
        is TxBuildError.ChangeBelowMinimum ->
            "Change ${error.change} lovelace is below the minimum ADA " +
                "(${error.minRequired}) for the change output"
        is TxBuildError.ExceedsMaxTxSize ->
            "Estimated transaction size ${error.size} bytes exceeds the maximum ${error.max} bytes"
        is TxBuildError.FeeCalculationOverflow -> "Fee calculation overflow"
        is TxBuildError.Serialization -> "Serialization error: ${presentCborError(error.error)}"
        is TxBuildError.NetworkMismatch ->
            "Network mismatch: expected ${error.expected.name}, got ${error.actual.name}"
        is TxBuildError.UnsupportedFeature ->
            "This wallet has no ADA-only UTxOs to spend — only UTxOs containing native " +
                "assets/tokens. Phase 1 only builds ADA-only transactions. (${error.detail})"
        is TxBuildError.DuplicateInput -> "Duplicate input detected"
        is TxBuildError.InvalidVerificationKeyLength ->
            "Invalid verification key length: expected ${error.expectedBytes}B, got ${error.actualBytes}B"
        is TxBuildError.InvalidSignatureLength ->
            "Invalid signature length: expected ${error.expectedBytes}B, got ${error.actualBytes}B"
        is TxBuildError.EmptyWitnessSet -> "Witness set is empty"
    }

    // --- Signed Transaction (not submitted; Block 1.10c) ---

    /** Bytes of the signed-transaction CBOR hex preview shown before truncating with "…". */
    private const val SIGNED_CBOR_PREVIEW_BYTES: Int = BODY_HEX_PREVIEW_BYTES

    /**
     * The explicit not-submitted label shown alongside every successfully signed transaction:
     * this checkpoint (Block 1.10c) never submits anything — submission is Block 1.11.
     */
    private const val SIGNED_NOT_SUBMITTED_LABEL: String =
        "signed, not submitted — testnet-only, test fixture, no real funds"

    /**
     * Builds the same unsigned minimal-ADA draft as [presentTransactionDraft] (Block 1.9c) via
     * [buildTransactionDraft], then signs it through
     * [ReadOnlyWallet.signTestnetFixtureTransaction] using [TestWalletFixture]'s cited
     * test-only mnemonic and [Network.TESTNET] explicitly — the same fixture-only/testnet-only
     * call-site discipline [presentTransactionDraft] and [presentWalletBalance] already follow
     * (ADR-0015 §2a: `:wallet` itself is not fixture-aware, so this call site supplies both
     * explicitly). The [OptIn] below is this call site's explicit acknowledgment of
     * [ExperimentalKardanoSigningScope] (ADR-0018) — see that annotation's KDoc for exactly
     * what it does and does not mean.
     *
     * Delegates entirely to `:tx` ([TransactionBuilder]) for the draft and `:wallet`
     * ([ReadOnlyWallet.signTestnetFixtureTransaction], which itself delegates to `:crypto`'s
     * `Signing` and `:tx`'s `TransactionAssembler`) for signing; this presenter does not hash,
     * sign, or assemble anything itself, and it never submits the result — submission is out of
     * scope (Block 1.11). Provider-agnostic: the caller decides whether [provider] is the
     * in-memory mock (fake/test-only) or a live provider (for example Blockfrost preprod).
     * Under the default [InMemoryChainQueryProvider], the restored wallet's address has no fake
     * UTxOs seeded for it, so the shared draft-building step normally fails with
     * [TxBuildError.NoInputs] before signing is ever attempted — reported the same way
     * [presentTransactionDraft] reports it. Fund that address via a live Blockfrost preprod
     * faucet to see a [SignedTransactionPresentation.Success].
     */
    @OptIn(ExperimentalKardanoSigningScope::class)
    suspend fun presentSignedTransaction(provider: ChainQueryProvider): SignedTransactionPresentation {
        val draft = when (val outcome = buildTransactionDraft(provider)) {
            is DraftBuildOutcome.Failed -> return SignedTransactionPresentation.Failure(outcome.message)
            is DraftBuildOutcome.Built -> when (val result = outcome.result) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err ->
                    return SignedTransactionPresentation.Failure(presentTxBuildError(result.error))
            }
        }
        val signResult = ReadOnlyWallet.signTestnetFixtureTransaction(TestWalletFixture.words, Network.TESTNET, draft)
        return mapSignedTransactionResult(signResult)
    }

    /**
     * Maps a raw [ReadOnlyWallet.signTestnetFixtureTransaction] result to a
     * [SignedTransactionPresentation]. Non-suspend and `internal` so it can be unit-tested by
     * constructing a [WalletError] directly, without restoring a mnemonic, reaching native
     * cryptography, or querying a provider.
     */
    internal fun mapSignedTransactionResult(
        result: KardanoResult<WalletSignedTransaction, WalletError>,
    ): SignedTransactionPresentation = when (result) {
        is KardanoResult.Ok -> SignedTransactionPresentation.Success(signedTransactionRows(result.value))
        is KardanoResult.Err -> SignedTransactionPresentation.Failure(presentWalletError(result.error))
    }

    private fun signedTransactionRows(signed: WalletSignedTransaction): List<LabeledRow> = listOf(
        LabeledRow("Transaction id", hexOrPlaceholder(signed.transactionId.toByteArray())),
        LabeledRow("Witnesses", signed.witnessCount.toString()),
        LabeledRow(
            "Signed tx CBOR (preview)",
            signedCborPreview(signed.signedTransaction.cbor()),
        ),
        LabeledRow("Status", SIGNED_NOT_SUBMITTED_LABEL),
    )

    private fun signedCborPreview(bytes: ByteArray): String {
        val prefixLength = minOf(SIGNED_CBOR_PREVIEW_BYTES, bytes.size)
        val hex = hexOrPlaceholder(bytes.copyOf(prefixLength))
        return if (bytes.size > prefixLength) "$hex… (${bytes.size}B total)" else hex
    }

    // --- Submit Transaction (Block 1.11c) ---

    /**
     * The explicit submitted label shown alongside every accepted submission: this checkpoint
     * always targets preprod, this fixture, and never real funds.
     */
    private const val SUBMITTED_LABEL: String =
        "submitted to preprod — testnet-only, test fixture, no real funds"

    /**
     * Builds the same unsigned draft as [presentTransactionDraft] (Block 1.9c) via
     * [buildTransactionDraft], signs it exactly as [presentSignedTransaction] (Block 1.10c)
     * does — [TestWalletFixture]'s cited test-only mnemonic and [Network.TESTNET] explicit at
     * this call site — and, only once that signed draft exists, calls
     * [TxSubmitProvider.submit] with its CBOR bytes.
     *
     * Delegates entirely to `:tx` ([TransactionBuilder]) for the draft, `:wallet`
     * ([ReadOnlyWallet.signTestnetFixtureTransaction]) for signing, and `:provider`
     * ([TxSubmitProvider.submit]) for submission; this presenter does not build, sign, or
     * submit anything itself — it only sequences the three calls and formats the result. No
     * new `:wallet` orchestration method is added for this (ADR-0017 "Non-goals"): the
     * id-comparison in [mapSubmitTransactionResult] lives here, in the presenter. The [OptIn]
     * below is this call site's explicit acknowledgment of [ExperimentalKardanoSigningScope]
     * (ADR-0018).
     *
     * [queryProvider] is the provider-agnostic read boundary the earlier checkpoints already
     * use (mock or live Blockfrost preprod). [submitProvider] is the provider-agnostic submit
     * boundary from Block 1.11a/b: the caller decides whether it is
     * [org.sarmidev.kardano.provider.InMemoryTxSubmitProvider] (fake/test-only — it always
     * returns [SubmitError.SubmissionNotSupported], never a fake accepted id, per ADR-0017) or
     * a live [org.sarmidev.kardano.provider.blockfrost.BlockfrostTxSubmitProvider] (real
     * preprod submission, test funds only).
     *
     * **No polling.** Once a submission is accepted, this checkpoint displays the accepted
     * transaction id for a manual explorer lookup and stops — Block 1.11's scope (ADR-0017,
     * `PHASE_1_PLAN.md` §1.11) treats polling as optional and only worth adding with an
     * explicit justification; a single-shot submit-and-display checkpoint has none yet, so
     * none is added here.
     */
    @OptIn(ExperimentalKardanoSigningScope::class)
    suspend fun presentSubmitTransaction(
        queryProvider: ChainQueryProvider,
        submitProvider: TxSubmitProvider,
    ): SubmitTransactionPresentation {
        val draft = when (val outcome = buildTransactionDraft(queryProvider)) {
            is DraftBuildOutcome.Failed -> return SubmitTransactionPresentation.Failure(outcome.message)
            is DraftBuildOutcome.Built -> when (val result = outcome.result) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err ->
                    return SubmitTransactionPresentation.Failure(presentTxBuildError(result.error))
            }
        }
        val signed = when (
            val result = ReadOnlyWallet.signTestnetFixtureTransaction(TestWalletFixture.words, Network.TESTNET, draft)
        ) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err ->
                return SubmitTransactionPresentation.Failure(presentWalletError(result.error))
        }
        val submitResult = submitProvider.submit(signed.signedTransaction.cbor())
        return mapSubmitTransactionResult(signed.transactionId, submitResult)
    }

    /**
     * Maps a raw [TxSubmitProvider.submit] result (for a transaction whose locally-computed id
     * is [localTransactionId]) to a [SubmitTransactionPresentation]. Non-suspend and `internal`
     * so it can be unit-tested by constructing a [TxHash] (a plain `:core` value, no native
     * call needed — unlike [WalletSignedTransaction], whose constructor is `:wallet`-internal)
     * and a [SubmitError] directly, without restoring a mnemonic, reaching native cryptography,
     * or querying a provider.
     */
    internal fun mapSubmitTransactionResult(
        localTransactionId: TxHash,
        result: KardanoResult<TxHash, SubmitError>,
    ): SubmitTransactionPresentation = when (result) {
        is KardanoResult.Ok ->
            SubmitTransactionPresentation.Success(submitTransactionRows(localTransactionId, result.value))
        is KardanoResult.Err -> SubmitTransactionPresentation.Failure(presentSubmitError(result.error))
    }

    private fun submitTransactionRows(
        localTransactionId: TxHash,
        acceptedTransactionId: TxHash,
    ): List<LabeledRow> {
        val matches = localTransactionId == acceptedTransactionId
        return buildList {
            add(LabeledRow("Accepted transaction id", hexOrPlaceholder(acceptedTransactionId.toByteArray())))
            add(
                LabeledRow(
                    "Locally signed transaction id",
                    hexOrPlaceholder(localTransactionId.toByteArray()),
                ),
            )
            add(LabeledRow("Ids match", if (matches) "yes" else "no"))
            if (!matches) {
                add(
                    LabeledRow(
                        "Note",
                        "Accepted id differs from the locally computed id — use the accepted id " +
                            "for explorer lookup.",
                    ),
                )
            }
            add(LabeledRow("Status", SUBMITTED_LABEL))
        }
    }

    /**
     * Maps a [SubmitError] to a human-readable single-line message, distinguishing every cause
     * (not-supported mock, empty transaction, rejection, transport, remote status, rate limit,
     * deserialization, unknown).
     *
     * Internal so tests can exercise all variants by constructing them directly.
     */
    internal fun presentSubmitError(error: SubmitError): String = when (error) {
        is SubmitError.SubmissionNotSupported -> MOCK_SUBMISSION_NOT_SUPPORTED_MESSAGE
        is SubmitError.EmptyTransaction -> "Empty transaction: nothing to submit"
        is SubmitError.Rejected -> "Transaction rejected (status ${error.code}): ${error.detail}"
        is SubmitError.Transport -> "Transport error: ${error.message}"
        is SubmitError.RemoteStatus ->
            if (error.detail != null) {
                "Remote status: ${error.code} (${error.detail})"
            } else {
                "Remote status: ${error.code}"
            }
        is SubmitError.RateLimited -> "Rate limited"
        is SubmitError.Deserialization -> "Decode error: ${error.detail}"
        is SubmitError.Unknown -> "Unknown submission error"
    }

    // --- Helpers ---

    private fun shortHex(bytes: ByteArray): String {
        val prefix = bytes.copyOf(minOf(SHORT_HEX_PREFIX_BYTES, bytes.size))
        return "${hexOrPlaceholder(prefix)}… (${bytes.size}B, structural only)"
    }
}
