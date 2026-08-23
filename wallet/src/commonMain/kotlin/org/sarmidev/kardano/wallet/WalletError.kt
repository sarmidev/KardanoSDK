package org.sarmidev.kardano.wallet

import org.sarmidev.kardano.address.AddressError
import org.sarmidev.kardano.crypto.derivation.KeyDerivationError
import org.sarmidev.kardano.crypto.hashing.CryptoError
import org.sarmidev.kardano.crypto.mnemonic.MnemonicError
import org.sarmidev.kardano.crypto.signing.SigningError
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.provider.ChainQueryProvider
import org.sarmidev.kardano.provider.ProviderError
import org.sarmidev.kardano.tx.TxBuildError

/**
 * A typed error produced by [ReadOnlyWallet.restore], [ReadOnlyWallet.balance], or
 * [ReadOnlyWallet.signTestnetFixtureTransaction].
 *
 * Every variant except [BalanceOverflow], [InvariantViolation], and [SigningScopeViolation]
 * wraps an already-typed error from the module that produced it, rather than re-deriving a
 * parallel taxonomy (ADR-0013 §6): a caller can always pattern-match through to the original
 * [MnemonicError], [KeyDerivationError], [CryptoError], [AddressError], [ProviderError],
 * [SigningError], or [TxBuildError]. [BalanceOverflow] originates in this module's own
 * balance-summation logic; [SigningScopeViolation] is the Phase 1 signing-policy check
 * (ADR-0019 §2). See
 * [ADR-0013](../../../../../../docs/DECISIONS/0013-wallet-boundary-and-read-only-state.md) and,
 * for [Signing] and [TransactionAssembly] (Block 1.10b),
 * [ADR-0015](../../../../../../docs/DECISIONS/0015-transaction-signing.md) §5.
 */
public sealed interface WalletError {

    /**
     * [ReadOnlyWallet.restore] rejected its candidate words as BIP-39 mnemonic input.
     *
     * @property error the underlying mnemonic-parsing error.
     */
    public data class Mnemonic(public val error: MnemonicError) : WalletError

    /**
     * [ReadOnlyWallet.restore] failed while deriving the master, payment, or stake key.
     *
     * @property error the underlying key-derivation error.
     */
    public data class Derivation(public val error: KeyDerivationError) : WalletError

    /**
     * [ReadOnlyWallet.restore] failed while hashing a derived public key to a credential hash.
     *
     * @property error the underlying hashing error.
     */
    public data class Hashing(public val error: CryptoError) : WalletError

    /**
     * [ReadOnlyWallet.restore] failed while building or encoding the wallet's address from its
     * payment and stake credentials.
     *
     * @property error the underlying address construction/encoding error.
     */
    public data class AddressBuild(public val error: AddressError) : WalletError

    /**
     * [ReadOnlyWallet.balance] failed because the underlying [ChainQueryProvider] query failed.
     *
     * @property error the underlying provider error.
     */
    public data class Provider(public val error: ProviderError) : WalletError

    /**
     * [ReadOnlyWallet.balance] rejected the sum of the queried UTxOs' lovelace amounts because
     * it would have exceeded [Lovelace]'s non-negative `Long` range. The sum is never silently
     * truncated or wrapped.
     *
     * @property partialCount the number of UTxOs already summed before the overflow was
     *   detected (always less than the full queried UTxO count).
     */
    public data class BalanceOverflow(public val partialCount: Int) : WalletError

    /**
     * [ReadOnlyWallet.signTestnetFixtureTransaction] failed while signing the transaction body
     * hash with the derived payment key.
     *
     * @property error the underlying `:crypto` signing error.
     */
    public data class Signing(public val error: SigningError) : WalletError

    /**
     * [ReadOnlyWallet.signTestnetFixtureTransaction] failed while assembling the witness set or
     * full signed `transaction` CBOR from the computed witness.
     *
     * @property error the underlying `:tx` build error.
     */
    public data class TransactionAssembly(public val error: TxBuildError) : WalletError

    /**
     * An internal invariant this module relies on did not hold, even though the operation
     * that hit it (`Hashing.blake2b256` returning a digest of an unexpected length, or a
     * lovelace total that failed [Lovelace]'s non-negative-range check) is not reachable by
     * any current call path with valid input. Returned instead of throwing, so a defensive
     * check that should never fire in practice still cannot crash a public wallet operation.
     *
     * @property detail a short, human-readable description of which invariant did not hold.
     */
    public data class InvariantViolation(public val detail: String) : WalletError

    /**
     * [ReadOnlyWallet.signTestnetFixtureTransaction] rejected the call because the draft's
     * bound network, scope, or shape is outside the Phase 1 testnet ADA-only path, or the
     * declared network disagrees with the draft (ADR-0019 §2). Returned before the mnemonic
     * is parsed.
     *
     * @property reason the exact check that failed.
     */
    public data class SigningScopeViolation(
        public val reason: SigningScopeViolationReason,
    ) : WalletError
}
