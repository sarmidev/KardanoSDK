//! Standalone diagnostic binary — NOT part of the UniFFI wrapper surface.
//!
//! Cross-compiled with `cargo ndk` and pushed to a real Android
//! device/emulator via `adb push` + `adb shell` (see
//! `scratch-signing-backend/README.md` "Android: blocked at the
//! Gradle/Gobley layer"). Its only purpose is to prove that the
//! `ed25519-bip32 0.4.2` extended-signing primitive this spike wraps
//! actually executes correctly under Android's real ARM64 userspace/libc,
//! independent of the (currently blocked) Gradle/AGP/Gobley packaging path.
//! It calls the reference crate directly — no UniFFI, no JNI, no handwritten
//! crypto — and reproduces the exact ADR-0016 §3 primary KAT.

use ed25519_bip32::{Signature, XPrv};

fn from_hex(s: &str) -> Vec<u8> {
    (0..s.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
        .collect()
}

fn main() {
    let extended_scalar = from_hex(
        "60d399da83ef80d8d4f8d223239efdc2b8fef387e1b5219137ffb4e8fbdea15adc9366b7d003af37c11396de9a83734e30e05e851efa32745c9cd7b42712c890",
    );
    let chain_code = from_hex("608763770eddf77248ab652984b21b849760d1da74a6f5bd633ce41adceef07a");
    let mut xprv_bytes = extended_scalar;
    xprv_bytes.extend_from_slice(&chain_code);

    let message = b"Hello World".to_vec();
    let expected_signature = from_hex(
        "90194d57cde4fdadd01eb7cf161780c277e129fc7135b97779a3268837e4cd2e9444b9bb91c0e84d23bba870df3c4bda91a110ef735638fa7a34ea2046d4be04",
    );

    let xprv = XPrv::from_slice_verified(&xprv_bytes).expect("valid 96-byte xprv");
    let signature: Signature<Vec<u8>> = xprv.sign(&message);
    let signature_bytes = signature.as_ref().to_vec();

    if signature_bytes != expected_signature {
        eprintln!("ANDROID_RUNTIME_KAT: FAIL (signature mismatch)");
        std::process::exit(1);
    }

    let xpub = xprv.public();
    if !xpub.verify(&message, &signature) {
        eprintln!("ANDROID_RUNTIME_KAT: FAIL (verify)");
        std::process::exit(1);
    }

    println!("ANDROID_RUNTIME_KAT: PASS");
}
