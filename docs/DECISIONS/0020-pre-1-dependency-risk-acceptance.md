# ADR-0020: Pre-1.0 And Pre-Release Dependency Risk Acceptance

| Field   | Value |
|---------|--------|
| Status  | **Accepted** (2026-08-23). Records why named 0.x / pre-release
          load-bearing pins are retained. Does not claim upstream
          maturity changed. |
| Scope   | W5-4 follow-up on `fix/build-and-ci-reproducibility`. Review of
          KotlinCrypto, IonSpin, Bouncy Castle, JNA, atomicfu,
          bip32-ed25519, LazySodium, and the Rust signing crates. |
| Phase   | Pre-release hygiene |
| Updated | 2026-08-23 |

---

## Context

The 2026-08-22 audit (W5-4) noted that several pinned dependencies were
still 0.x or otherwise pre-1.0. Pinning (not upgrading to an unpublished
1.0) was the original remediation. This ADR reviews each load-bearing
coordinate against Maven Central / crates.io on 2026-08-23, upgrades
only compatible reviewed 1.x patches, and **accepts** the remaining 0.x
pins with an explicit replacement trigger.

This is documented acceptance of current upstream versioning. It is not
a statement that those libraries have become 1.0.

## Decision

### Upgraded in this commit (1.x patches, KATs re-run)

| Coordinate | Before | After | Why | KAT after change |
|---|---|---|---|---|
| `org.bouncycastle:bcprov-jdk18on` | 1.84 | 1.85.2 | Maven Central latest `jdk18on`. 1.85.2 restores Android API &lt; 33 `intValueExact` after a 1.85 regression and does not change the PBKDF2-HMAC-SHA-512 seam this repo calls. | `:crypto:jvmTest` after the bump, then again with the JNA bump |
| `net.java.dev.jna:jna` | 5.17.0 | 5.19.1 | Maven Central latest. 5.19.1 restores pre-API-26 Android after 5.19.0 used `MethodHandle`. Loader only; no signing algorithm change. | `:crypto-signing-backend:jvmTest` (4), `:crypto:jvmTest`, `:wallet:jvmTest` |

Sources: Bouncy Castle `releasenotes.html` / 7 August 2026 1.85.2 notes;
JNA `CHANGES.md` 5.19.1 (`#1730` / `#1731`).

### Reviewed and left at the current pin

| Coordinate | Current | Latest seen 2026-08-23 | Why retained | Monitoring trigger | Replacement criteria |
|---|---|---|---|---|---|
| `org.kotlincrypto.hash:blake2` / `:sha2` | 0.8.0 | 0.8.0 (no 1.x) | Latest published. Hashing KATs (CIP-19 / Plutus goldens) already pin this backend. No 1.0 replacement exists. | A `1.0.0` (or later stable) of the same `org.kotlincrypto.hash` artifacts | Adopt only with a dedicated review and a re-run of `HashingVectorsTest` / `HashInputBoundTest` |
| `com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings` | 0.9.5 | 0.9.5 (no 1.x) | Latest published. JVM/iOS public-key projection (ADR-0010). Android uses LazySodium instead. | A 1.x of this coordinate, or a documented swap that still exports `crypto_scalarmult_ed25519_base_noclamp` | Dedicated review + ADR-0010 projection KATs on JVM (and iOS compile) |
| `org.jetbrains.kotlinx:atomicfu` | 0.26.1 | 0.33.0 | Generated UniFFI bindings in `:crypto-signing-backend` were produced against 0.26.1 (ADR-0016 §8/§9). A 0.26 → 0.33 jump is not a reviewed drop-in. | Gobley/bindgen regeneration that records a new atomicfu pin, or an upstream 1.x used by a new binding generation | Regen bindings + `SigningBackendKatTest` + checksum manifest |
| `ed25519-bip32` (crate) | 0.4.2 (`Cargo.lock`) | 0.4.3 | 0.4.3 exists. The eight committed native artifacts were built from 0.4.2. Changing the crate without rebuilding those binaries would desynchronize source and artifacts. | A decision to rebuild all eight artifacts from a newer crate + toolchain | Offline rebuild commands in `crypto-signing-backend/README.md`, new `CHECKSUMS.sha256`, ADR-0016 D1_H0 KAT on JVM (and Android device when available) |
| `uniffi` (crate) | `=0.29.5` (`Cargo.toml` + `Cargo.lock`) | 0.32.0 | Bindings and `gobley-uniffi-bindgen` 0.3.7 target the 0.29 line. 0.32 requires a new bindgen and committed Kotlin/C stubs. | New bindgen version that matches a chosen UniFFI release | Same rebuild + KAT + checksum bar as the crate row |
| `org.jetbrains.compose.material3:material3` | 1.11.0-alpha07 | 1.12.0-alpha03 (still alpha) | Playground UI only. Kept in the Compose 1.11.1 group (commit 2). Not a protocol backend. | A stable `material3` that matches the pinned Compose Multiplatform line | UI compile + Playground unit tests; no protocol KAT |

Also reviewed and already at latest **1.x / 5.x** (no change):

- `org.hyperledger.identus:bip32-ed25519` 1.8.8
- `com.goterl:lazysodium-android` 5.2.0

## KAT evidence referenced

- Hashing: `HashingVectorsTest`, `HashInputBoundTest` (cited CIP-19 / Plutus vectors).
- Mnemonic / PBKDF2 / CIP-1852: `MnemonicVectorsTest`, `IcarusMasterKeyVectorsTest`,
  `KeyDerivationVectorsTest`.
- Signing backend: ADR-0016 §3 `D1_H0` in `SigningBackendKatTest` (4 cases) and
  `:crypto` `Ed25519Bip32SigningKatTest`.

Device execution of Android projection / signing KATs is **not** claimed
by this ADR.

## Consequences

- W5-4 remains a version-maturity observation. This ADR closes the
  "unreviewed pre-1.0 pin" part: each remaining 0.x pin has a dated
  reason, a trigger, and replacement criteria.
- Do not replace a hashing, projection, or signing backend in a
  catch-all upgrade. Use a dedicated change with the KAT list above.
