package org.sarmidev.kardano.wallet

import org.sarmidev.kardano.KardanoResult
import org.sarmidev.kardano.address.Address
import org.sarmidev.kardano.address.AddressCredential
import org.sarmidev.kardano.crypto.derivation.Cip1852Path
import org.sarmidev.kardano.crypto.derivation.Cip1852Role
import org.sarmidev.kardano.crypto.derivation.ExtendedPrivateKey
import org.sarmidev.kardano.crypto.derivation.ExtendedPublicKey
import org.sarmidev.kardano.crypto.derivation.IcarusMasterKey
import org.sarmidev.kardano.crypto.derivation.KeyDerivation
import org.sarmidev.kardano.crypto.derivation.KeyDerivationError
import org.sarmidev.kardano.crypto.hashing.Hashing
import org.sarmidev.kardano.crypto.mnemonic.Mnemonic
import org.sarmidev.kardano.crypto.signing.Signing
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.primitives.Network
import org.sarmidev.kardano.primitives.TxHash
import org.sarmidev.kardano.provider.ChainQueryProvider
import org.sarmidev.kardano.provider.Utxo
import org.sarmidev.kardano.tx.TransactionAssembler
import org.sarmidev.kardano.tx.TransactionDraft
import org.sarmidev.kardano.tx.TransactionDraftScope
import org.sarmidev.kardano.tx.TransactionWitnessSet
import org.sarmidev.kardano.tx.VerificationKeyWitness

/**
 * A read-only handle over a restored wallet's public metadata: its [network], its testnet/
 * mainnet base [address], and the two fixed CIP-1852 paths ([paymentPath], [stakePath]) that
 * address was derived from.
 *
 * Instances are created exclusively through [restore], which composes `:crypto` (mnemonic
 * restoration, key derivation, hashing) with `:core` (credential and address construction).
 * A [ReadOnlyWallet] retains no mnemonic, seed, entropy, root/private key bytes, or raw public
 * key bytes — only [network], the built [Address], and the two [Cip1852Path] values, none of
 * which are secret. See
 * [ADR-0013](../../../../../../docs/DECISIONS/0013-wallet-boundary-and-read-only-state.md) for
 * the full design rationale, including why this module exists and why it does not depend on
 * `:provider-blockfrost`.
 *
 * This type can restore a wallet, derive its address, query a provider for a balance
 * ([balance]), and — as of Block 1.10b, ADR-0015 §1 — sign an already-built
 * [org.sarmidev.kardano.tx.TransactionDraft] into a signed, unsubmitted artifact
 * ([signTestnetFixtureTransaction]). Its scope-explicit name and [ExperimentalKardanoSigningScope]
 * opt-in requirement (ADR-0018) remain a compiler/IDE-visible signal that it is not a
 * general-purpose wallet signing API; ADR-0019 additionally binds [TransactionDraft] to
 * network/scope and rejects a mismatched or mainnet draft before any mnemonic is parsed. See
 * [signTestnetFixtureTransaction]'s own KDoc for the exact checks. This type never submits a
 * transaction (submission is Block 1.11) and introduces no persistence: an instance lives only
 * as long as the caller keeps the in-memory reference.
 *
 * @property network the network [address] was generated for.
 * @property address the wallet's generated testnet/mainnet base address.
 * @property paymentPath the CIP-1852 path the payment credential was derived from
 *   (`m/1852'/1815'/0'/0/0`).
 * @property stakePath the CIP-1852 path the stake credential was derived from
 *   (`m/1852'/1815'/0'/2/0`).
 */
public class ReadOnlyWallet private constructor(
    public val network: Network,
    public val address: Address,
    public val paymentPath: Cip1852Path,
    public val stakePath: Cip1852Path,
) {

    /**
     * Queries [provider] for [address]'s UTxOs and sums their ADA amounts into a
     * [WalletBalance].
     *
     * Reaches no native cryptography: this delegates entirely to [provider]. An address with no
     * UTxOs (for example a wallet address that a mock provider has no fake data seeded for)
     * returns [KardanoResult.Ok] with a zero [WalletBalance], not an error — see ADR-0013 §7 for
     * why a restored wallet's address reads as zero-balance under the default
     * [org.sarmidev.kardano.provider.InMemoryChainQueryProvider] and is not made to look funded.
     *
     * @param provider the read-only chain query boundary to query; mock or live, chosen by the
     *   caller.
     * @return [KardanoResult.Ok] with the summed [WalletBalance], or [KardanoResult.Err] with
     *   [WalletError.Provider] if the query failed, or [WalletError.BalanceOverflow] if the sum
     *   would have exceeded [Lovelace]'s representable range. Never throws.
     */
    public suspend fun balance(provider: ChainQueryProvider): KardanoResult<WalletBalance, WalletError> {
        val utxos = when (val result = provider.getUtxos(address)) {
            is KardanoResult.Ok -> result.value
            is KardanoResult.Err -> return KardanoResult.Err(WalletError.Provider(result.error))
        }
        return sumBalance(utxos)
    }

    /** Structural description that renders no path or address bytes beyond their own [toString]s. */
    override fun toString(): String =
        "ReadOnlyWallet(network=$network, address=$address, paymentPath=$paymentPath, stakePath=$stakePath)"

    public companion object {

        /**
         * The fixed payment CIP-1852 path every restored wallet uses: `m/1852'/1815'/0'/0/0`.
         *
         * Used only by [of]'s test-support defaults. [restore] and
         * [signTestnetFixtureTransaction] compute their own copy via [fixedPath] inline instead
         * of referencing this constant, so that a (not reachable with valid input) validation
         * failure surfaces as a typed [WalletError] returned from those public functions,
         * rather than a throw at this property's first-access class-init time.
         */
        private val PAYMENT_PATH: Cip1852Path = fixedPathOrThrow(Cip1852Role.EXTERNAL)

        /**
         * The fixed stake CIP-1852 path every restored wallet uses: `m/1852'/1815'/0'/2/0`.
         *
         * See [PAYMENT_PATH]'s KDoc: used only by [of]'s test-support defaults.
         */
        private val STAKE_PATH: Cip1852Path = fixedPathOrThrow(Cip1852Role.STAKING)

        /**
         * Restores [words] as a BIP-39 mnemonic, derives its account-0 payment and stake keys
         * (both fixed CIP-1852 paths, computed via [fixedPath]), hashes each derived public key
         * to a 28-byte credential, and builds a base [Address] for [network].
         *
         * Delegates entirely to `:crypto` ([Mnemonic], [IcarusMasterKey], [KeyDerivation],
         * [Hashing]) and `:core` ([AddressCredential], [Address]); this module does not
         * reimplement or duplicate any derivation, hashing, or address-encoding logic, and
         * performs no handwritten cryptography. The mnemonic, master key, and both derived
         * private/public key handles are cleared before returning, on every path (success or
         * failure); the returned [ReadOnlyWallet] retains none of them.
         *
         * Accepts either SDK [Network] as a pure wallet/address construction operation, the
         * same policy [Address.baseAddress] already uses (ADR-0012 §2): this factory itself
         * makes no mainnet/testnet judgment, so `:core`'s own vector tests can restore against
         * either. That is a `:wallet`-level statement only — it does not authorize mainnet use
         * anywhere in this project's Phase 1 sample/UI surface. Every Phase 1 sample/UI caller
         * (the Android Playground checkpoint, Block 1.8b) must pass [Network.TESTNET]; no
         * Phase 1 checkpoint constructs, displays, or restores a mainnet wallet.
         *
         * @param words the candidate BIP-39 mnemonic words. This SDK restores mnemonics only;
         *   it never generates one.
         * @param network the network to build the address for. Phase 1 sample/UI callers must
         *   pass [Network.TESTNET].
         * @return [KardanoResult.Ok] with the restored [ReadOnlyWallet], or [KardanoResult.Err]
         *   with a [WalletError] describing the first failure ([WalletError.Mnemonic],
         *   [WalletError.Derivation], [WalletError.Hashing], or [WalletError.AddressBuild]).
         *   Never throws.
         */
        public fun restore(
            words: List<String>,
            network: Network,
        ): KardanoResult<ReadOnlyWallet, WalletError> {
            val mnemonic = when (val result = Mnemonic.parse(words)) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err -> return KardanoResult.Err(WalletError.Mnemonic(result.error))
            }
            var master: IcarusMasterKey? = null
            var paymentPrivateKey: ExtendedPrivateKey? = null
            var paymentPublicKey: ExtendedPublicKey? = null
            var stakePrivateKey: ExtendedPrivateKey? = null
            var stakePublicKey: ExtendedPublicKey? = null
            try {
                // Not reachable with valid input: EXTERNAL/STAKING at account 0, index 0 are
                // always in Cip1852Path.of's valid range. Computed via KardanoResult rather
                // than a shared throwing constant, so this can never crash restore().
                val paymentPath = when (val result = fixedPath(Cip1852Role.EXTERNAL)) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.Derivation(result.error))
                }
                val stakePath = when (val result = fixedPath(Cip1852Role.STAKING)) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.Derivation(result.error))
                }

                master = when (val result = IcarusMasterKey.fromMnemonic(mnemonic)) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.Derivation(result.error))
                }
                val derivation = KeyDerivation.default()

                paymentPrivateKey = when (val result = derivation.derivePrivate(master, paymentPath)) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.Derivation(result.error))
                }
                paymentPublicKey = when (val result = derivation.publicKey(paymentPrivateKey)) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.Derivation(result.error))
                }
                val paymentDigest = when (
                    val result = Hashing.default().blake2b224(paymentPublicKey.publicKeyBytes())
                ) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.Hashing(result.error))
                }
                val paymentCredential = when (
                    val result = AddressCredential.keyHash(paymentDigest.toByteArray())
                ) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.AddressBuild(result.error))
                }

                stakePrivateKey = when (val result = derivation.derivePrivate(master, stakePath)) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.Derivation(result.error))
                }
                stakePublicKey = when (val result = derivation.publicKey(stakePrivateKey)) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.Derivation(result.error))
                }
                val stakeDigest = when (
                    val result = Hashing.default().blake2b224(stakePublicKey.publicKeyBytes())
                ) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.Hashing(result.error))
                }
                val stakeCredential = when (
                    val result = AddressCredential.keyHash(stakeDigest.toByteArray())
                ) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.AddressBuild(result.error))
                }

                val address = when (
                    val result = Address.baseAddress(network, paymentCredential, stakeCredential)
                ) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.AddressBuild(result.error))
                }

                return KardanoResult.Ok(ReadOnlyWallet(network, address, paymentPath, stakePath))
            } finally {
                mnemonic.clear()
                master?.clear()
                paymentPrivateKey?.clear()
                paymentPublicKey?.clear()
                stakePrivateKey?.clear()
                stakePublicKey?.clear()
            }
        }

        /**
         * Signs [draft] with the payment key derived from [words], returning the full signed
         * `transaction` and the transaction id (ADR-0015 §1-§3, Block 1.10b).
         *
         * This is **not** a general-purpose wallet signing API (ADR-0015 §2a, ADR-0019): it
         * authorizes signing only for the Phase 1 testnet test-fixture flow — `Network.TESTNET`,
         * the cited test-only mnemonic, and an ADA-only single-payment [TransactionDraft]
         * produced by `TransactionBuilder`/`TransactionBodySerializer`. Before [Mnemonic.parse]
         * or any key derivation, this function rejects the call when:
         * 1. [TransactionDraft.scope] is not
         *    [org.sarmidev.kardano.tx.TransactionDraftScope.Phase1AdaOnlySinglePayment];
         * 2. [TransactionDraft.network] is not [Network.TESTNET];
         * 3. the declared [network] argument does not equal [TransactionDraft.network];
         * 4. the draft's input/output counts are not the Phase 1 ADA-only single-payment shape.
         *
         * After those checks, this function derives the payment public key through the same
         * [KeyDerivation] / [Hashing] / [AddressCredential] path [restore] uses and compares
         * the CIP-19 payment-credential fingerprint to [Phase1FixtureIdentity]. A different
         * structurally valid BIP-39 mnemonic fails with
         * [SigningScopeViolationReason.UnrecognizedFixtureIdentity] before [Signing.sign].
         * The fixture mnemonic phrase is not stored in this module.
         *
         * Those checks close the ADR-0018 compiled-artifact gap (a mainnet-built draft
         * signed under a declared-`TESTNET` argument, or an arbitrary mnemonic). Scope and
         * network failures return [WalletError.SigningScopeViolation] and do not parse
         * [words]. The required
         * [ExperimentalKardanoSigningScope] opt-in remains a Kotlin-compiler intent signal
         * (ADR-0018) and does not replace these runtime checks; it also does not carry over as
         * a Swift compile-time gate (ADR-0019).
         *
         * Derives the account-0 payment key ([PAYMENT_PATH]) exactly as [restore] does, then:
         * hashes [draft]'s body ([Hashing.blake2b256]) to the 32-byte `bodyHash` / transaction
         * id; signs that hash with the derived payment key ([Signing.sign]) — never the raw
         * body bytes; projects the payment public key ([KeyDerivation.publicKey]) for the
         * witness's `vkey`; and assembles the single-witness [TransactionWitnessSet] and full
         * signed `transaction` CBOR through [TransactionAssembler.assemble]. [draft]'s body and
         * fee are read, never rebuilt or altered (ADR-0015 §3): the exact
         * [TransactionDraft.bodyCbor] bytes are what is hashed, signed, and embedded.
         *
         * The mnemonic, master key, and both derived payment key handles are cleared before
         * returning, on every path (success or failure); the returned
         * [WalletSignedTransaction] retains none of them.
         *
         * @param words the candidate BIP-39 mnemonic words for the signing key. Phase 1
         *   call sites must pass the cited test-only fixture.
         * @param network the network this call site declares it is signing for. Cross-checked
         *   against [TransactionDraft.network]; must be [Network.TESTNET].
         * @param draft the already-built, unsigned draft to sign. Not rebuilt or altered.
         *   Must be a testnet Phase 1 ADA-only single-payment draft.
         * @return [KardanoResult.Ok] with the [WalletSignedTransaction], or
         *   [KardanoResult.Err] with a [WalletError] describing the first failure
         *   ([WalletError.SigningScopeViolation], [WalletError.Mnemonic],
         *   [WalletError.Derivation], [WalletError.Hashing], [WalletError.Signing], or
         *   [WalletError.TransactionAssembly]). Never throws.
         */
        @ExperimentalKardanoSigningScope
        public fun signTestnetFixtureTransaction(
            words: List<String>,
            network: Network,
            draft: TransactionDraft,
        ): KardanoResult<WalletSignedTransaction, WalletError> {
            validateSigningScope(network, draft)?.let { return KardanoResult.Err(it) }

            val mnemonic = when (val result = Mnemonic.parse(words)) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err -> return KardanoResult.Err(WalletError.Mnemonic(result.error))
            }
            var master: IcarusMasterKey? = null
            var paymentPrivateKey: ExtendedPrivateKey? = null
            var paymentPublicKey: ExtendedPublicKey? = null
            try {
                // Not reachable with valid input: EXTERNAL at account 0, index 0 is always in
                // Cip1852Path.of's valid range. See restore()'s identical comment.
                val paymentPath = when (val result = fixedPath(Cip1852Role.EXTERNAL)) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.Derivation(result.error))
                }

                master = when (val result = IcarusMasterKey.fromMnemonic(mnemonic)) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.Derivation(result.error))
                }
                val derivation = KeyDerivation.default()

                paymentPrivateKey = when (val result = derivation.derivePrivate(master, paymentPath)) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.Derivation(result.error))
                }
                paymentPublicKey = when (val result = derivation.publicKey(paymentPrivateKey)) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.Derivation(result.error))
                }

                val paymentCredentialHash = when (
                    val result = Hashing.default().blake2b224(paymentPublicKey.publicKeyBytes())
                ) {
                    is KardanoResult.Ok -> result.value.toByteArray()
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.Hashing(result.error))
                }
                val paymentCredential = when (
                    val result = AddressCredential.keyHash(paymentCredentialHash)
                ) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.AddressBuild(result.error))
                }
                if (!Phase1FixtureIdentity.matchesPaymentCredential(paymentCredential.hashBytes())) {
                    return KardanoResult.Err(
                        WalletError.SigningScopeViolation(
                            SigningScopeViolationReason.UnrecognizedFixtureIdentity,
                        ),
                    )
                }

                val bodyHash = when (val result = Hashing.default().blake2b256(draft.bodyCbor())) {
                    is KardanoResult.Ok -> result.value.toByteArray()
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.Hashing(result.error))
                }

                val signature = when (val result = Signing.default().sign(bodyHash, paymentPrivateKey)) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.Signing(result.error))
                }

                val witness = when (
                    val result = VerificationKeyWitness.of(paymentPublicKey.publicKeyBytes(), signature)
                ) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.TransactionAssembly(result.error))
                }
                val witnessSet = when (val result = TransactionWitnessSet.of(listOf(witness))) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.TransactionAssembly(result.error))
                }
                val signedTransaction = when (val result = TransactionAssembler.assemble(draft, witnessSet)) {
                    is KardanoResult.Ok -> result.value
                    is KardanoResult.Err -> return KardanoResult.Err(WalletError.TransactionAssembly(result.error))
                }

                val transactionId = when (val result = TxHash.of(bodyHash)) {
                    is KardanoResult.Ok -> result.value
                    // Not reachable with valid input: Hashing.blake2b256 always returns a
                    // 32-byte HashDigest, and TxHash.SIZE is 32. Returned as a typed error
                    // rather than thrown, so this defensive check cannot crash the caller.
                    is KardanoResult.Err -> return KardanoResult.Err(
                        WalletError.InvariantViolation("blake2b256 body hash is unexpectedly not 32 bytes"),
                    )
                }

                return KardanoResult.Ok(WalletSignedTransaction(signedTransaction, transactionId))
            } finally {
                mnemonic.clear()
                master?.clear()
                paymentPrivateKey?.clear()
                paymentPublicKey?.clear()
            }
        }

        /**
         * ADR-0019 §2: reject a draft that is not the Phase 1 testnet ADA-only path, or whose
         * bound network disagrees with [declaredNetwork], before [Mnemonic.parse].
         *
         * @return the [WalletError.SigningScopeViolation] to return, or `null` when the draft
         *   may proceed to mnemonic parsing.
         */
        private fun validateSigningScope(
            declaredNetwork: Network,
            draft: TransactionDraft,
        ): WalletError.SigningScopeViolation? {
            if (draft.scope !is TransactionDraftScope.Phase1AdaOnlySinglePayment) {
                return WalletError.SigningScopeViolation(
                    SigningScopeViolationReason.UnsupportedDraftScope(draft.scope),
                )
            }
            if (draft.network != Network.TESTNET) {
                return WalletError.SigningScopeViolation(
                    SigningScopeViolationReason.UnsupportedDraftNetwork(draft.network),
                )
            }
            if (declaredNetwork != draft.network) {
                return WalletError.SigningScopeViolation(
                    SigningScopeViolationReason.DeclaredNetworkMismatch(
                        declared = declaredNetwork,
                        draftNetwork = draft.network,
                    ),
                )
            }
            if (draft.selectedInputs.isEmpty() || draft.outputs.size !in 1..2) {
                return WalletError.SigningScopeViolation(
                    SigningScopeViolationReason.UnsupportedDraftShape(
                        "expected at least one input and 1 or 2 ADA-only outputs, " +
                            "got inputs=${draft.selectedInputs.size} outputs=${draft.outputs.size}",
                    ),
                )
            }
            return null
        }

        /**
         * Assembles a [ReadOnlyWallet] directly from an already-built [address], without
         * restoring a mnemonic or reaching native cryptography.
         *
         * Module-internal: used only by this module's own tests to exercise [balance] against a
         * hand-built or already-parsed [Address], so that coverage stays free of native
         * derivation/hashing calls. Production callers use [restore].
         *
         * @param network the network [address] belongs to.
         * @param address the address to assemble the wallet around.
         * @param paymentPath the payment path to report; defaults to the fixed
         *   `m/1852'/1815'/0'/0/0` path every [restore]d wallet uses.
         * @param stakePath the stake path to report; defaults to the fixed
         *   `m/1852'/1815'/0'/2/0` path every [restore]d wallet uses.
         * @return the assembled [ReadOnlyWallet]. Never fails.
         */
        internal fun of(
            network: Network,
            address: Address,
            paymentPath: Cip1852Path = PAYMENT_PATH,
            stakePath: Cip1852Path = STAKE_PATH,
        ): ReadOnlyWallet = ReadOnlyWallet(network, address, paymentPath, stakePath)

        /**
         * Builds the fixed CIP-1852 path `m/1852'/1815'/0'/<role>/0` for [role], as a typed
         * result rather than a throwing constant: [restore] and [signTestnetFixtureTransaction]
         * call this directly and propagate a (not reachable with valid input) failure as
         * [WalletError.Derivation], so no public wallet operation can crash on this check.
         */
        private fun fixedPath(role: Cip1852Role): KardanoResult<Cip1852Path, KeyDerivationError> =
            Cip1852Path.of(account = 0, role = role, index = 0)

        /**
         * Unwraps [fixedPath], throwing only if `0/<role>/0` were somehow out of range — a
         * programming error in this fixed constant, not a runtime condition. Used exclusively
         * to initialize [PAYMENT_PATH]/[STAKE_PATH], which back only [of]'s test-support
         * defaults (see their KDoc); never called from [restore] or
         * [signTestnetFixtureTransaction], which use [fixedPath] directly instead.
         */
        private fun fixedPathOrThrow(role: Cip1852Role): Cip1852Path =
            when (val result = fixedPath(role)) {
                is KardanoResult.Ok -> result.value
                is KardanoResult.Err -> error("ReadOnlyWallet's fixed path is invalid: ${result.error}")
            }
    }
}

/**
 * Sums [utxos]' lovelace amounts into a [WalletBalance], checking for `Long` overflow before
 * each addition rather than after, so the total is rejected rather than silently truncated or
 * wrapped if it would exceed [Lovelace]'s representable range (ADR-0013 §5).
 *
 * File-private: the only caller is [ReadOnlyWallet.balance].
 */
private fun sumBalance(utxos: List<Utxo>): KardanoResult<WalletBalance, WalletError> {
    var total = 0L
    for ((index, utxo) in utxos.withIndex()) {
        val next = utxo.value.coin.value
        if (total > Long.MAX_VALUE - next) {
            return KardanoResult.Err(WalletError.BalanceOverflow(partialCount = index))
        }
        total += next
    }
    val coin = when (val result = Lovelace.of(total)) {
        is KardanoResult.Ok -> result.value
        // Not reachable with valid input: `total` only ever accumulates non-negative
        // Lovelace.value amounts and overflow is rejected above, so it can never be negative
        // here. Returned as a typed error rather than thrown, so this defensive check cannot
        // crash the caller.
        is KardanoResult.Err -> return KardanoResult.Err(
            WalletError.InvariantViolation("wallet balance total is unexpectedly negative: $total"),
        )
    }
    return KardanoResult.Ok(WalletBalance(coin = coin, utxoCount = utxos.size))
}
