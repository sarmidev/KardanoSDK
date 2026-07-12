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
import org.sarmidev.kardano.encoding.cbor.Cbor
import org.sarmidev.kardano.encoding.cbor.CborError
import org.sarmidev.kardano.encoding.hex.Hex
import org.sarmidev.kardano.encoding.hex.HexError
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.provider.ChainQueryProvider
import org.sarmidev.kardano.provider.ProtocolParameters
import org.sarmidev.kardano.provider.ProviderError
import org.sarmidev.kardano.provider.Utxo
import org.sarmidev.kardano.wallet.ReadOnlyWallet
import org.sarmidev.kardano.wallet.WalletBalance
import org.sarmidev.kardano.wallet.WalletError

// ---------------------------------------------------------------------------
// Display models — pure data, no Compose imports
// ---------------------------------------------------------------------------

/** A labeled key-value row for a structured result card. */
internal data class LabeledRow(val label: String, val value: String)

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

// ---------------------------------------------------------------------------
// Presenter — maps :core results to display models; no SDK logic of its own
// ---------------------------------------------------------------------------

/**
 * Maps results from `:core`, `:crypto`, `:provider`, and `:wallet` APIs to [AddressPresentation],
 * [HexPresentation], [CborPresentation], [WalletPresentation], [ProviderUtxosPresentation],
 * [ProviderParamsPresentation], and [WalletBalancePresentation] for display in
 * [PlaygroundScreen].
 *
 * This object only formats and labels results. It never re-parses, re-validates, or
 * reimplements any protocol rule, derivation, hashing, address-generation, or balance-summation
 * logic. All of that semantics comes from `:core`/`:crypto`/`:provider`/`:wallet`.
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
                HexPresentation.DecodeSuccess(bytes.size, Hex.encode(bytes))
            }
            is KardanoResult.Err -> HexPresentation.Failure(presentHexError(result.error))
        }

    /**
     * Encodes [bytes] to canonical lowercase hex.
     */
    fun presentHexEncode(bytes: ByteArray): HexPresentation =
        HexPresentation.EncodeSuccess(Hex.encode(bytes))

    private fun presentHexError(error: HexError): String = when (error) {
        is HexError.InputTooLong -> "Input too long: ${error.actual} chars (max ${error.max})"
        is HexError.OddLength -> "Odd length: ${error.length} chars"
        is HexError.InvalidCharacter -> "Invalid character '${error.char}' at index ${error.index}"
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
            val paymentFingerprintHex = Hex.encode(paymentDigest.toByteArray())
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
            val stakeFingerprintHex = Hex.encode(stakeDigest.toByteArray())
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
    )

    /**
     * Maps a [WalletError] to a human-readable single-line message, delegating to the
     * existing per-error-type presenters ([presentMnemonicError], [presentKeyDerivationError],
     * [presentCryptoError], [presentAddressError], [presentProviderError]) for every wrapped
     * variant, so no formatting logic is duplicated. [WalletError.BalanceOverflow] is the one
     * variant `:wallet` owns itself.
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
    }

    // --- Helpers ---

    private fun shortHex(bytes: ByteArray): String {
        val prefix = bytes.copyOf(minOf(SHORT_HEX_PREFIX_BYTES, bytes.size))
        return "${Hex.encode(prefix)}… (${bytes.size}B, structural only)"
    }
}
