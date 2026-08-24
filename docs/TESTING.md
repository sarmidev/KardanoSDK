# Testing Guide — Kardano SDK

How tests, fixtures, and external test vectors are organized in this repository. This
guide complements the testing rules in
[docs/AI_WORKING_AGREEMENT.md](AI_WORKING_AGREEMENT.md) (the "Unit testing policy" and
"Test integrity rules" sections) and does not replace them. If anything here ever
conflicts with the working agreement, the working agreement wins.

> The Phase 1 demo is experimental and testnet/preprod-focused. It includes scoped fixture
> restoration, signing, and submission; it does not cover mainnet or user-supplied key material.

---

## Test source sets

Tests live in Kotlin Multiplatform source sets. Put each test in the narrowest source
set that can express it.

- `commonTest` — the default home for tests. Uses `kotlin.test` so the same tests run on
  every target (JVM, Android, iOS). Deterministic, UI-free SDK logic (primitives,
  encoders, parsers, validators) is tested here so coverage is shared across platforms.
- `jvmTest` — JVM-only tests, or tests that depend on JVM-only test tooling. Keep
  protocol behavior in `commonTest`; use `jvmTest` only when a test genuinely cannot be
  expressed in common code.
- Android host tests (`androidHostTest`) — JVM-hosted unit tests for the Android target.
  They run on the local JVM (no emulator/device) via the `withHostTest { }` configuration
  in the module Gradle files. Use these for Android-target-specific behavior only.
- iOS tests (`iosTest` / native targets) — Kotlin/Native tests for the iOS targets. They
  run on the iOS simulator and require macOS with Xcode. Use these for iOS-target-specific
  behavior only.

Guidance:

- Prefer `commonTest`. Only drop to a platform source set when the behavior or tooling is
  platform-specific.
- Test naming: one test class per unit under test, named `<Unit>Test`; test functions use
  descriptive lowerCamelCase names that state the expected behavior (for example,
  `rejectsInvalidChecksum`). Cover valid, invalid, and edge cases for every unit.

### Where tests live today

- `:core` — UI-free primitives, encodings, structural addresses, and CBOR.
- `:crypto` — mnemonic parsing, seed/key derivation, hashing, and scoped signing adapters.
- `:crypto-signing-backend` — generated/native signing backend seam and known-answer tests.
- `:provider` and `:provider-blockfrost` — provider-neutral models plus Blockfrost wire mapping.
- `:wallet` and `:tx` — wallet orchestration and ADA-only transaction behavior.
- `:shared` — Playground MVI, sample-flow wiring, and presentation mapping. Protocol vectors and
  SDK behavior remain owned by their corresponding SDK module rather than the Compose UI.

---

## Fixture folder layout

Fixtures (test input/expected-output data) are kept separate from implementation and from
test code. They live under the `commonTest` resources of the module that owns the logic:

```
core/src/commonTest/resources/fixtures/
  README.md         (fixture policy + index)
  bech32/README.md   (future BIP-173 / BIP-350 vectors)
  cbor/README.md     (future RFC 8949 Appendix A vectors)
  address/README.md  (future CIP-19 vectors)
```

- One subfolder per spec/area. Each subfolder has a `README.md` naming the authoritative
  source for the vectors that will go there.
- Protocol vectors may live inline in tests or in fixture files. When added, they must land
  alongside the implementation that uses them, with the authoritative source cited.
- `:shared` carries no protocol fixtures; see
  `shared/src/commonTest/resources/fixtures/README.md`.

---

## External test-vector policy

This policy is mandatory for any security-sensitive unit (checksums, CBOR, addresses).

- Vectors must be copied verbatim from cited specifications or from a trusted reference
  implementation. Do not paraphrase, reformat, or "clean up" the values.
- Generated or AI-invented vectors are not allowed. An AI agent must never produce its own
  "expected" outputs for checksum, CBOR, or address tests.
- Every fixture file (or fixture block) cites its source spec and URL in a header comment.
- Include both valid and invalid vectors where the spec provides them. Invalid vectors
  must stay invalid; do not modify them to make a parser accept them.
- Never weaken a validator to make a test pass. If a test fails, fix the implementation or
  correct the cited test data — never relax the acceptance criteria.
- Round-trip direction: `decode(encode(x)) == x` is fine to test. `encode(decode(y)) == y`
  must not be used to normalize or accept non-canonical input; if tested, also assert that
  non-canonical input is rejected before decoding.

### Required external vector sources

- Bech32 / Bech32m — BIP-173 and BIP-350 valid and invalid vectors.
- CBOR — RFC 8949 Appendix A examples for each supported type.
- Addresses — CIP-19 examples (testnet preferred) plus known-bad inputs.

---

## Verification commands

The wrapper is Gradle **9.5.0** (`distributionSha256Sum` in
`gradle/wrapper/gradle-wrapper.properties`, checksum file
`https://services.gradle.org/distributions/gradle-9.5.0-bin.zip.sha256`).
AGP is **9.1.0**, Kotlin **2.4.10**, Android compile/target API **36**.
That is the official Kotlin 2.4.10 envelope (ADR-0021). API 37 is
deferred until a Kotlin-supported AGP documents it.

Run tests per module. iOS simulator tests require macOS with Xcode.

- Core (JVM) tests: `./gradlew :core:jvmTest`
- Core Android host (JVM-hosted) tests: `./gradlew :core:testAndroidHostTest`
- Core iOS test sources compile: `./gradlew :core:compileTestKotlinIosSimulatorArm64`
- Crypto/native pin review: after a Bouncy Castle or JNA catalog change, re-run
  `:crypto:jvmTest`, `:crypto-signing-backend:jvmTest`, and `:wallet:jvmTest`.
  Remaining 0.x pins and replacement criteria are in
  `docs/DECISIONS/0020-pre-1-dependency-risk-acceptance.md`.
- Crypto, wallet, shared, and signing-backend JVM tests: run on macOS because the committed JVM
  signing artifacts target macOS hosts:
  `./gradlew :crypto:jvmTest :crypto-signing-backend:jvmTest :wallet:jvmTest :shared:jvmTest`
- Provider (JVM) tests: `./gradlew :provider:jvmTest :provider-blockfrost:jvmTest`
- `BlockfrostConfigTest` asserts that `toString`, `assertEquals` failure text, and
  `List`/`Set`/`Map` rendering never include the project id, and that two configs with
  the same fields are not equal (identity equality; the type is no longer a `data class`).
- `BlockfrostChainQueryProviderTest` covers `403`/`500` response-body detail (and
  malformed/blank bodies), cancellation rethrow, oversized-page rejection, and the UTxO
  cap: an internal `UtxoPaginationPolicy` test seam (not public) exercises an exact-cap
  empty one-item probe (`Ok`), an exact-cap probe HTTP 404 (`Ok`, same empty/end
  semantics as ordinary UTxO pagination), a non-empty probe (`ResultTruncated`), and a
  non-404 probe HTTP failure (typed `RemoteStatus`), without allocating 10_000 entries.
  `UtxoPaginationPolicyTest` asserts construction-time bounds (positive
  `pageCount`/`maxPages`, `maxPages < Int.MAX_VALUE`, checked `pageCount * maxPages`)
  using extreme `Int` values only — no large page allocations.
- `PlaygroundProviderPresenterTest` / `PlaygroundDemoFlowTest` cover every
  `ProviderError` variant, including `RemoteStatus` with and without `detail` and
  `ResultTruncated`.
- `BlockfrostHttpTimeoutTest` asserts the documented 10s/30s/30s `HttpTimeout` bounds
  through an internal policy seam (no 30s sleep), that `configureBlockfrost` installs
  the plugin, that a delayed `MockEngine` handler with a shortened request timeout maps
  to `Transport` for both read and submit, and that submit is attempted once.
- `BlockfrostErrorDetailTest` covers empty/malformed bodies, a huge raw body, a complete
  envelope with a long `message` field, and a UTF-8 4-byte code point split by the byte
  budget. Public detail stays within 500 characters; a filled byte budget is not parsed
  as JSON.
- `BlockfrostOkHttpEngineTest` (androidHostTest) asserts the effective OkHttp client
  Ktor 3.5.2 would build from the production `defaultHttpClient` engine config
  (`retryOnConnectionFailure == false` after Ktor's default `config` lambda), and that
  a preconfigured client alone is overwritten by that default. The standalone
  `blockfrostOkHttpClient()` helper is still asserted as defense in depth. That is the
  engine-level submit-replay switch, not Ktor `HttpRequestRetry`, and is not a live
  connection-failure replay.
- Wallet and transaction (JVM) tests: `./gradlew :wallet:jvmTest :tx:jvmTest`
- Desktop (JVM) tests: `./gradlew :shared:jvmTest`
- Android host (JVM-hosted) tests: `./gradlew :shared:testAndroidHostTest`
- iOS simulator tests: `./gradlew :shared:iosSimulatorArm64Test`

Playground operation-lifecycle coverage lives in `:shared`:

- `PlaygroundViewModelTest` (jvmTest) — a slow fake query discarded after ResetFlow, after a
  live-provider toggle, and after a project-id change (only the latest generation applies).
  `NonCancellable` gated fakes also complete after Job cancellation so generation / request-token
  / address-identity checks — not cooperative cancellation — discard stale UTxO and params
  results after ResetFlow, address edit/fill, repeated loads, and provider-configuration changes.
  Repeated same-generation Funds, Build, Sign, and Submit requests discard the first
  `NonCancellable` completion; Wallet restore is synchronous and has no request token.
  Upstream reruns discard in-flight and completed downstream results (Funds clears
  Build/Sign/Submit; Build clears Sign/Submit; Sign clears Submit) so Continue cannot
  advance on a stale later step.
  Toggle-off and project-id change invalidate the live factory cache before the next lookup.
- `PlaygroundReducerTest` (commonTest) — diagnostic and guided-operation request tokens
  increment on each start and on ResetFlow / provider-configuration change; starting Funds,
  Build, or Sign clears completed downstream guided results and increments those tokens;
  ResetFlow converts diagnostic Loading to Empty and keeps completed diagnostic results;
  stale token/address applies are no-ops.
- `PlaygroundProviderFactoryTest` (commonTest) — Mock vs LivePreprod mode, live-cache reuse,
  cache drop when the id changes or live mode is disabled, and explicit `invalidateLiveCache()`
  without an intervening mock lookup (dummy ids never appear in assertion messages).
- `PlaygroundTransactionDraftPresenterTest` — `InsufficientFunds` includes
  `excludedNativeAssetUtxoCount` / `excludedNativeAssetLovelace` when those fields are non-zero.
- `PlaygroundMockFlowDesktopTest` (jvmTest) — the seeded guided mock flow is unchanged
  (Funds/Build/Sign succeed; Submit still reports submission not supported).

The full Phase 1 target matrix is intentionally not equivalent across platforms:

- Android is the runtime validation surface for the Playground.
- iOS simulator/device execution requires a local macOS/Xcode environment; compile/link checks are
  run where that environment is unavailable.
- JVM signing runtime coverage uses the committed macOS natives on Darwin. Linux x86-64
  uses JNA prefix `linux-x86-64/` and is rebuilt only on native `ubuntu-22.04`
  (glibc >= 2.35, measured at runtime). The `.so` is the ninth CHECKSUMS row
  (`cb439099…4ed5`), promoted from run `32678079715`. Fresh Linux rebuilds
  must match A==B and that row. Linux ARM, musl, and older glibc are out
  of scope. Windows x86-64 JVM is candidate-only (JNA prefix
  `win32-x86-64/`, `windows-2022` / ImageOS `win22`) and is not a
  CHECKSUMS row. Rebuild jobs pin rustc 1.97.0 by placing the rustup
  toolchain `bin` first on PATH; hosted images may otherwise expose
  rustc 1.97.1.

Native rebuild comparison (does not overwrite committed binaries):

```bash
python3 -m unittest discover -s crypto-signing-backend/scripts/tests -p "test_*.py"
python3 crypto-signing-backend/scripts/rebuild_into_staging.py \
  --staging /tmp/kardano-native-rebuild \
  --groups macos-jvm,android,ios \
  --write-candidates crypto-signing-backend/rebuild-candidates \
  --mode candidate \
  --compare
```

`linux-jvm-rebuild-evidence.yml` rebuilds `x86_64-unknown-linux-gnu` twice on
pinned `ubuntu-22.04` (ImageOS `ubuntu22`, not `ubuntu-latest`), records
`/etc/os-release`, `ldd --version`, and compiler/linker versions, compares
SHA-256 + ELF reports + GNU version requirements against the documented
glibc 2.35 baseline, then runs `:crypto-signing-backend:jvmTest`
`:crypto:jvmTest` `:wallet:jvmTest` `:shared:jvmTest` against the candidate
at `linux-x86-64/`. The ELF verifier accepts only full-string
`GLIBC_<major>.<minor>` or legacy three-component labels, walks
Verneed/Vernaux inside one `SHT_GNU_verneed` section, requires canonical
section 0, one `.dynamic`/`PT_DYNAMIC` pair with exact
offset/vaddr/filesz/memsz/align, `.dynstr.sh_size == DT_STRSZ`,
`DT_VERSYM` bound to one allocated `.gnu.version`, parsed Versym
indices resolved to globally unique `vna_other`/`vd_ndx` values
(repeated `vd_ndx` is rejected even when the name matches),
canonical dynsym entry 0, Versym 0 only for the null entry / local /
undefined weak import, fail-closed `readelf --version-info` and
`--dyn-syms --wide` corroboration coupled to the parsed sign Versym,
`UINT64_MAX` checked add/mul, and a two-pass path scan. Permissions
stay `contents: read`. Uploads use `if-no-files-found: error`. The
job does not write CHECKSUMS or committed `src/`. After Phase C it
requires A==B **and** identity with the committed Linux `.so` /
CHECKSUMS row. Promoted from run `32678079715` (artifacts
`9503309381` / `9503308946` / `9503350346`, expire 2026-09-07).

`windows-jvm-rebuild-evidence.yml` rebuilds `x86_64-pc-windows-msvc`
twice on pinned `windows-2022` (ImageOS `win22`, not `windows-latest`;
`ImageVersion` is recorded and is not an immutable-image claim).
Jobs select MSVC toolset `14.44.35207` `Hostx64/x64` `link.exe` via
`vswhere`, prepend that directory, require `where.exe link` to match,
and pass `-Clinker=` so cargo `--verbose` names that `link.exe`.
Toolset drift fails until reviewed. Compares SHA-256 + PE32+ reports
(AMD64, PE32+, `IMAGE_FILE_DLL`, canonical `SizeOfImage`, exact sign
export in a `CNT_CODE`+`MEM_EXECUTE` non-writable section, no
forwarder RVA, every nonempty data directory parsed, allowlisted
imports, empty delay-load/Authenticode/CLR/bound-import, no
CODEVIEW/PDB, `IMAGE_DEBUG_TYPE_REPRO` only, recorded `/Brepro`
`TimeDateStamp`, `DYNAMIC_BASE`+`NX_COMPAT`, no overlay). Path scan
rejects ASCII and UTF-16LE drive-root and UNC candidates from any
byte offset. Then runs `:crypto-signing-backend:jvmTest` via
`gradlew.bat`. `:crypto`/`:wallet` JVM tests are not run here
(`bip32-ed25519` 1.8.8 has no `win32-x86-64` wrapper). The DLL is
placed only on the runner JNA path for that test. Permissions stay
`contents: read`. Uploads use `if-no-files-found: error`. CHECKSUMS
and committed `src/` are unchanged. Promotion waits for independent
review.

`native-rebuild-evidence.yml` runs the harness tests and `cargo metadata --locked` on
Ubuntu, and the macOS staged rebuild on pinned `macos-26` + Xcode 26.6. Compare
mode is chosen before NDK install so a diagnostic failure cannot skip the
manifest. The job installs NDK `27.2.12479018` into a dest it owns and ignores
the image `ANDROID_NDK*` value (`27.3.13750724`). It compares
hashes/arch/symbols/install names against CHECKSUMS (or a candidate
manifest if one is present during an iteration). Uploads use
`if-no-files-found: error`. It never writes staged copies over `src/`.
CARGO_TARGET_DIR is staging-owned and must be empty; the module `target/` is
refused.

Documentation and claim-language checks:

```bash
rg -n "TESTING|fixtures|test vector|commonTest|jvmTest|iosSimulatorArm64Test|testAndroidHostTest" README.md docs/ core/README.md shared/README.md
python3 -m unittest scripts.tests.test_check_restricted_claims scripts.tests.test_check_handoff_archive scripts.tests.test_check_action_pins
python3 -m unittest discover -s crypto-signing-backend/scripts/tests -p "test_*.py"
python3 scripts/check_handoff_archive.py
python3 scripts/check_restricted_claims.py
python3 scripts/check_action_pins.py
```

`scripts/check_restricted_claims.py` classifies each restricted-claim phrase
match on its own (never a whole-line exclusion), reports `path:line:column`,
and prefers the longest phrase. It enumerates tracked files with
`git ls-files -z` and compares suffixes case-insensitively (`.md`, `.mdc`,
`.html`, `.kt`, `.kts`, `.swift`, `.xml`, `.properties`, `.toml`, `.yaml`,
`.yml`, `.json`) while reporting the original path. Whole-file exclusions are
limited to immutable archived snapshots and circular policy/test data.
Historical wording in evolving ADRs and append-only logs is allowlisted per
occurrence (path + 1-based physical line number + SHA-256 of the exact line +
phrase + 1-based occurrence on that line). Duplicating an allowlisted line
elsewhere, or inserting a line before it, is a finding until the allowlist is
re-reviewed (fail-closed). Hyphen compounds are not exempt. CI runs the unit
tests and the archive byte check before the scan. It does not scan credentials.

`scripts/check_action_pins.py` requires every external `uses:` in
`.github/workflows/*` and local `.github/actions/**/action.yml` to contain
exactly a 40-character lowercase SHA that matches
`scripts/action_pin_inventory.py`. Composite Action metadata recorded in
that inventory (and copied in `docs/DEPENDENCY_REVIEW.md`) must itself be
SHA-pinned; a floating transitive `uses:` is a finding. CI runs
`scripts.tests.test_check_action_pins` before the check. The inventory was
resolved live on 2026-08-23; do not reuse SHAs from older audit notes.
The previous pins were exact patch releases (`checkout` `v4.3.1`, not the
moving `v4` tag).

Dependency lock and verification (regenerate only when coordinates
change; do not hand-edit generated checksums):

```bash
./gradlew --no-daemon --no-configuration-cache resolveAndLockAll --write-locks
# re-run the same command; `git diff` on `*/gradle.lockfile` and
# `settings-gradle.lockfile` must be empty
cargo metadata --locked --manifest-path crypto-signing-backend/Cargo.toml --format-version 1 >/dev/null
```

`gradle/verification-metadata.xml` is SHA-256 verification metadata
generated by Gradle. A changed artifact checksum fails the build (proven
locally by flipping the `junit-4.13.2.jar` SHA-256, then restoring it).
See `docs/DEPENDENCY_REVIEW.md`.

Android lint (warnings fail the build; freshness detectors are off
because versions are locked and SHA-256 verified) and packaging:

```bash
./gradlew --no-daemon :androidApp:lintDebug :androidApp:lintRelease
./gradlew --no-daemon :androidApp:assembleDebug :androidApp:assembleRelease
```

`verify.yml` job `android-lint` (Ubuntu) runs lint Debug/Release, then
assemble Debug/Release. Reports should read `No issues found.`
Unsuppressed findings fail CI. Assemble is packaging only, not
`connectedAndroidDeviceTest`. Owner should still glance at pre-API-26
launcher tiles after regenerating the rounded-rect legacy silhouette
(`scripts/generate_legacy_launcher_icons.py`).

iOS compile and simulator link (macOS Verify job
`macos-signing-and-ios`):

```bash
./gradlew --no-daemon \
  :core:compileKotlinIosArm64 \
  :crypto:compileKotlinIosArm64 \
  :crypto-signing-backend:compileKotlinIosArm64 \
  :provider:compileKotlinIosArm64 \
  :provider-blockfrost:compileKotlinIosArm64 \
  :wallet:compileKotlinIosArm64 \
  :tx:compileKotlinIosArm64 \
  :shared:compileKotlinIosArm64 \
  :crypto-signing-backend:linkDebugTestIosSimulatorArm64
```

That job also runs the macOS signing-path JVM tests. iOS on-simulator
assertion execution remains future work (compile+link only).

`scripts/check_handoff_archive.py` restores the six documented archive link
rewrites at the byte level (no newline normalization) and hashes the result
with SHA-256. The archived snapshot keeps its original trailing blank line;
`.gitattributes` scopes `whitespace=-blank-at-eof` to that file only so
`git diff --check` stays clean without a global whitespace suppress.

Full-history credential scan (Gitleaks CLI, not a third-party Action wrapper):

```bash
python3 -m unittest scripts.tests.test_gitleaks_allowlist
python3 scripts/install_gitleaks.py
python3 scripts/check_gitleaks.py
```

The installer verifies the official `gitleaks_*_checksums.txt` digest and the
selected archive digest, reads the expected member into memory, and writes the
binary through an exclusive temporary sibling. It loops `os.write` until every
byte is written, sets mode `0755` with `fchmod` on the open temp descriptor,
then atomically replaces a validated non-symlink destination. It refuses a
destination symlink and a world-writable archive member.
The binary is written to `.gitleaks-bin/` (gitignored) and is never committed.
CI runs the helper/installer/allowlist tests before install and scan. Output
is redacted. Allowlists are match-level only (cited CIP-19 payment-credential
hex **and** an exact repo-root path, including the helper). See
`.gitleaks.toml` and `docs/RELEASING.md`.

Reachable commits after a complete fetch are `git rev-list --all`. The
scan is not that list: Gitleaks v8.30.1 is invoked with
`--log-opts=--full-history --all -m`, which is `git log` over every ref,
without history simplification, with one diff per merge parent. A
credential that exists only in a merge resolution (absent from both
parents) is therefore in the scanned diffs. An integration test builds
that merge and requires the check command to find it while still
redacting the value.
