# Third-Party Components And Notices

Kardano SDK source files are licensed under Apache-2.0. Dependencies, generated bindings, and
prebuilt native artifacts remain subject to their own licences. This page is an initial inventory,
not a replacement for a release-time dependency and notice review.

## Directly documented components

| Component | Use in Kardano SDK | Documented licence |
|---|---|---|
| Kotlin and Kotlin Multiplatform | Language, build plugins, standard libraries | Apache-2.0 |
| Ktor | Blockfrost HTTP client | Apache-2.0 |
| kotlinx.serialization / coroutines / atomicfu | Serialization, concurrency, generated binding support | Apache-2.0 |
| Compose Multiplatform and AndroidX | Sample Playground UI | Apache-2.0 |
| Bouncy Castle | JVM/Android PBKDF2 platform seam | MIT-style Bouncy Castle licence |
| `bip32-ed25519` | Android key derivation backend | Verify release artefact notice before distribution |
| IonSpin libsodium bindings | JVM/iOS public-key projection | Verify release artefact notice before distribution |
| LazySodium Android | Android public-key projection | Verify release artefact notice before distribution |
| JNA | JVM/native signing backend loading | Apache-2.0 OR LGPL-2.1 |
| `ed25519-bip32` Rust crate | Project-owned signing wrapper | MIT OR Apache-2.0 |
| UniFFI Rust crate | Generated signing backend bindings | MPL-2.0 |
| Gobley UniFFI bindgen | Offline generation tool only | Apache-2.0 OR MIT |

The signing-backend module records its pinned versions and a more detailed inventory in
[crypto-signing-backend/README.md](../crypto-signing-backend/README.md).

## Release-time checklist

Before publishing a binary, Maven artifact, app bundle, or other distribution:

1. Generate or obtain a dependency licence report for all Gradle runtime artifacts.
2. Review the `Cargo.lock` dependency graph for the Rust signing backend.
3. Preserve notices required by redistributed native artifacts and generated bindings.
4. Verify that every copied test vector, code fragment, image, or documentation extract has an
   attribution and licence compatible with its use.
5. Add required attribution text to the release package or a `NOTICE` file.
6. Record the review date, release tag, and reviewer in the release notes.

Do not treat this initial inventory as legal advice. Consult qualified counsel when distributing a
commercial product or when licence obligations are unclear.
