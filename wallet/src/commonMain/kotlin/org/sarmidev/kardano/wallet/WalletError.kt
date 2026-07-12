package org.sarmidev.kardano.wallet

import org.sarmidev.kardano.address.AddressError
import org.sarmidev.kardano.crypto.derivation.KeyDerivationError
import org.sarmidev.kardano.crypto.hashing.CryptoError
import org.sarmidev.kardano.crypto.mnemonic.MnemonicError
import org.sarmidev.kardano.primitives.Lovelace
import org.sarmidev.kardano.provider.ChainQueryProvider
import org.sarmidev.kardano.provider.ProviderError

/**
 * A typed error produced by [ReadOnlyWallet.restore] or [ReadOnlyWallet.balance].
 *
 * Every variant except [BalanceOverflow] wraps an already-typed error from the module that
 * produced it, rather than re-deriving a parallel taxonomy (ADR-0013 §6): a caller can always
 * pattern-match through to the original [MnemonicError], [KeyDerivationError], [CryptoError],
 * [AddressError], or [ProviderError]. [BalanceOverflow] is the one variant that originates in
 * this module's own balance-summation logic. See
 * [ADR-0013](../../../../../../docs/DECISIONS/0013-wallet-boundary-and-read-only-state.md).
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
}
