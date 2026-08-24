# `LICENSES/` — Authoritative License Texts

This directory holds unmodified, verbatim license texts for the licenses that
actually apply to source or binaries Kardano SDK redistributes. It is generated
evidence for the packet described in [`docs/LEGAL_REVIEW.md`](../docs/LEGAL_REVIEW.md);
it is **not** a legal opinion and does not itself decide which license governs
which file — see [`../NOTICE`](../NOTICE) and
[`docs/THIRD_PARTY_NOTICES.md`](../docs/THIRD_PARTY_NOTICES.md) for the
per-component mapping.

Each file below was fetched from the license steward's own canonical URL on
**2026-08-24** (`curl`, no HTML/markdown conversion) and is committed with the
exact bytes received, so the SHA-256 in this table can be reproduced by
re-fetching the same URL.

| File | License | Source URL | SHA-256 of the committed file |
|---|---|---|---|
| `Apache-2.0.txt` | Apache License, Version 2.0 | https://www.apache.org/licenses/LICENSE-2.0.txt | `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` |
| `MPL-2.0.txt` | Mozilla Public License, Version 2.0 | https://www.mozilla.org/media/MPL/2.0/index.txt | `3f3d9e0024b1921b067d6f7f88deb4a60cbe7a78e76c64e3f1d7fc3b779b9d04` |
| `ISC-libsodium.txt` | ISC License (as published by the `libsodium` project) | https://raw.githubusercontent.com/jedisct1/libsodium/master/LICENSE | `508a76d186356c0dd807a670ef510964f8724557024796a2c426c6c0e19ab683` |
| `BouncyCastle.txt` | Bouncy Castle License (upstream describes it as "read in the same way as the MIT license"; it is not the generic SPDX `MIT` template) | https://www.bouncycastle.org/licence.html | `3216ec8f5e256138322eb8d7adb2c7d176af83e29193e38041a62a83ab55fd63` (SHA-256 of this repository's plain-text transcription of the licence paragraphs on that page; the upstream page is HTML, not a distributed `.txt`/`LICENSE` file, so there is no canonical upstream file digest to reproduce — re-verify by reading the page at the URL above) |

## Why these four and not others

Evaluated against the locked Gradle/Cargo dependency graph in
`docs/LEGAL_REVIEW.md` (2026-08-24):

- **Apache-2.0** — directly applies to Kotlin/Ktor/kotlinx/Compose-AndroidX/
  KotlinCrypto, `org.hyperledger.identus:bip32-ed25519`, the IonSpin libsodium
  bindings, and is the **elected** branch of every dual `Apache-2.0 OR X`
  redistributed component: JNA 5.19.1 (`Apache-2.0 OR LGPL-2.1`), the
  `ed25519-bip32` Rust crate and its `cryptoxide` dependency (`MIT OR
  Apache-2.0`, compiled into the nine committed native artifacts). Electing
  Apache-2.0 for those dual-licensed components means this SDK does not need a
  separate generic `MIT` license file — see "About MIT" below.
- **MPL-2.0** — applies to `com.goterl:lazysodium-android` (Android native
  libsodium carrier; MPL-2.0 is file-level copyleft, not chosen by election)
  and to the `uniffi` Rust crate (`=0.29.5`), which is a **single-license**
  MPL-2.0 dependency (no OR clause) whose generated/compiled code is linked
  into all nine committed `crypto-signing-backend` native artifacts.
- **ISC** — applies to `libsodium` itself (the C library), which is bundled
  as a compiled native binary inside both the IonSpin JVM artifact and the
  `lazysodium-android` artifact, per `docs/THIRD_PARTY_NOTICES.md`.
- **Bouncy Castle License** — applies to `org.bouncycastle:bcprov-jdk18on`,
  which is its own permissive license text, not the generic MIT template.

### About "MIT" (evaluated, not separately included)

The prompt's minimum evaluation list includes **MIT**. The only redistributed
or compiled-in components with an MIT option are already covered by an
Apache-2.0 election above (`ed25519-bip32`, `cryptoxide`) or have their own
distinct text (Bouncy Castle). No redistributed or compiled-in component in
the current locked graph is **MIT-only** (single-license, no OR clause) with
no other applicable text already in this directory. Components that are
genuinely MIT-only in this graph — the Gitleaks CLI, and the transitive
`actions/upload-artifact` pin used by CI — are **not distributed** (CI-only
tooling; see `docs/THIRD_PARTY_NOTICES.md`), so a generic `MIT.txt` is
intentionally not added here. If a future dependency change introduces an
MIT-only redistributed or compiled-in component, add a generic MIT license
text file to this directory (source: https://opensource.org/license/mit/) in
that same change and update this table and `docs/LEGAL_REVIEW.md`.

This evaluation is a factual dependency-graph finding, not legal advice.
