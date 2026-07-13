//! Disposable Block 1.10b provisioning spike (ADR-0016 §7e).
//!
//! Exposes Cardano extended Ed25519-BIP32 `sign`/`verify` through UniFFI by
//! delegating directly to `ed25519_bip32::XPrv::sign` / `XPub::verify` — the
//! same reference primitive already cited by ADR-0016 §3 and CIP-3. This
//! crate performs no cryptographic computation of its own: it only validates
//! input byte lengths (which the underlying crate already rejects) and moves
//! bytes across the FFI boundary.
//!
//! This module is scratch/disposable: it is not part of the Kardano SDK, is
//! not published, and is expected to be deleted once the spike's evidence is
//! recorded in ADR-0016. See `scratch-signing-backend/README.md`.

use ed25519_bip32::{Signature, XPrv, XPub};

uniffi::setup_scaffolding!();

/// Input-shape errors surfaced across the UniFFI boundary. Each variant
/// mirrors a length check the underlying `ed25519-bip32` crate itself
/// performs (`PrivateKeyError`, `PublicKeyError`, `SignatureError`); this
/// wrapper adds no additional validation and no cryptographic logic.
#[derive(Debug, uniffi::Error)]
pub enum SigningBackendError {
    /// `xprv` was not the expected 96 bytes (64-byte extended scalar `kL||kR`
    /// + 32-byte chain code).
    InvalidExtendedPrivateKey,
    /// `xpub` was not the expected 64 bytes (32-byte public key + 32-byte
    /// chain code).
    InvalidExtendedPublicKey,
    /// `signature` was not the expected 64 bytes.
    InvalidSignature,
}

impl std::fmt::Display for SigningBackendError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SigningBackendError::InvalidExtendedPrivateKey => write!(
                f,
                "expected a 96-byte extended private key (kL||kR||chaincode)"
            ),
            SigningBackendError::InvalidExtendedPublicKey => {
                write!(f, "expected a 64-byte extended public key (pk||chaincode)")
            }
            SigningBackendError::InvalidSignature => write!(f, "expected a 64-byte signature"),
        }
    }
}

impl std::error::Error for SigningBackendError {}

/// Signs `message` with the Cardano extended Ed25519-BIP32 private key
/// `xprv` (96 bytes), delegating to `ed25519_bip32::XPrv::sign`. Returns the
/// raw 64-byte signature. No handwritten signing math.
#[uniffi::export]
fn sign(xprv: Vec<u8>, message: Vec<u8>) -> Result<Vec<u8>, SigningBackendError> {
    let xprv =
        XPrv::from_slice_verified(&xprv).map_err(|_| SigningBackendError::InvalidExtendedPrivateKey)?;
    let signature: Signature<Vec<u8>> = xprv.sign(&message);
    Ok(signature.as_ref().to_vec())
}

/// Derives the extended public key from an extended private key `xprv`,
/// delegating to `ed25519_bip32::XPrv::public`. Exposed only so Kotlin-side
/// tests can exercise `verify()` without hardcoding a second key fixture;
/// this is derivation, already exercised by the existing
/// `bip32-ed25519:1.8.8` wrapper (ADR-0016 §1), not new cryptographic logic.
#[uniffi::export]
fn derive_xpub(xprv: Vec<u8>) -> Result<Vec<u8>, SigningBackendError> {
    let xprv =
        XPrv::from_slice_verified(&xprv).map_err(|_| SigningBackendError::InvalidExtendedPrivateKey)?;
    Ok(xprv.public().as_ref().to_vec())
}

/// Verifies `signature` over `message` against the Cardano extended
/// Ed25519-BIP32 public key `xpub` (64 bytes), delegating to
/// `ed25519_bip32::XPub::verify`. No handwritten verification math.
#[uniffi::export]
fn verify(
    xpub: Vec<u8>,
    message: Vec<u8>,
    signature: Vec<u8>,
) -> Result<bool, SigningBackendError> {
    let xpub =
        XPub::from_slice(&xpub).map_err(|_| SigningBackendError::InvalidExtendedPublicKey)?;
    let signature: Signature<Vec<u8>> =
        Signature::from_slice(&signature).map_err(|_| SigningBackendError::InvalidSignature)?;
    Ok(xpub.verify(&message, &signature))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn from_hex(s: &str) -> Vec<u8> {
        (0..s.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
            .collect()
    }

    /// ADR-0016 §3 primary KAT: `ed25519-bip32` 0.4.2 `src/tests.rs`
    /// `xprv_sign` / `verify_signature`, the `D1_H0` fixture. Copied verbatim
    /// from the cited source, not invented.
    #[test]
    fn reproduces_adr_0016_primary_kat() {
        let extended_scalar = from_hex(
            "60d399da83ef80d8d4f8d223239efdc2b8fef387e1b5219137ffb4e8fbdea15adc9366b7d003af37c11396de9a83734e30e05e851efa32745c9cd7b42712c890",
        );
        let chain_code = from_hex("608763770eddf77248ab652984b21b849760d1da74a6f5bd633ce41adceef07a");
        let mut xprv_bytes = extended_scalar;
        xprv_bytes.extend_from_slice(&chain_code);
        assert_eq!(xprv_bytes.len(), 96);

        let message = b"Hello World".to_vec();
        let expected_signature = from_hex(
            "90194d57cde4fdadd01eb7cf161780c277e129fc7135b97779a3268837e4cd2e9444b9bb91c0e84d23bba870df3c4bda91a110ef735638fa7a34ea2046d4be04",
        );

        let signature = sign(xprv_bytes.clone(), message.clone()).expect("sign should succeed");
        assert_eq!(signature, expected_signature, "D1_H0_SIGNATURE mismatch");

        // The vector's own verify test derives the public key via
        // `XPrv::public()` rather than hardcoding it; do the same here.
        let xprv = XPrv::from_slice_verified(&xprv_bytes).unwrap();
        let xpub_bytes = xprv.public().as_ref().to_vec();
        let verified = verify(xpub_bytes, message, signature).expect("verify should succeed");
        assert!(verified, "signature must verify against the derived xpub");
    }

    #[test]
    fn rejects_wrong_length_inputs() {
        assert!(matches!(
            sign(vec![0u8; 10], b"msg".to_vec()),
            Err(SigningBackendError::InvalidExtendedPrivateKey)
        ));
        assert!(matches!(
            verify(vec![0u8; 10], b"msg".to_vec(), vec![0u8; 64]),
            Err(SigningBackendError::InvalidExtendedPublicKey)
        ));
        assert!(matches!(
            verify(vec![0u8; 64], b"msg".to_vec(), vec![0u8; 10]),
            Err(SigningBackendError::InvalidSignature)
        ));
    }
}
