# ADR-0018: Signing API Scope Signal and Publication Readiness (W7-1)

| Field   | Value                                                                 |
|---------|------------------------------------------------------------------------|
| Status  | **Accepted (decision only) — implementation not authorized by this ADR.** This ADR resolves *which direction* to build in; the chosen option is its own separate, future implementation task, mirroring how ADR-0015 §1 recorded the signing decision ahead of Block 1.10b's implementation. |
| Scope   | Reassessing W7-1 from the 2026-08-22 pre-release audit (`docs/AUDIT/2026-08-22-pre-release-audit.md` §4.6): whether `ReadOnlyWallet.signTransaction`'s unenforced scope is a defect, an API-contract problem, a publication-policy problem, or a combination; comparing focused remediation options; recommending one. |
| Phase   | Pre-release hardening (post-Phase 1, pre-first-public-release)         |
| Updated | 2026-08-23                                                            |

---

## Context

[`ReadOnlyWallet.signTransaction`](../../wallet/src/commonMain/kotlin/org/sarmidev/kardano/wallet/ReadOnlyWallet.kt)
is public, takes a `network: Network` parameter annotated `@Suppress("UNUSED_PARAMETER")` and
never reads it, and validates only that the supplied `words` are structurally valid BIP-39 — not
that they are the Phase 1 fixture. `Network.MAINNET`
([`core/.../primitives/Network.kt`](../../core/src/commonMain/kotlin/org/sarmidev/kardano/primitives/Network.kt))
and `BlockfrostNetwork.MAINNET` are both public, unguarded enum constants resolving to a real
`cardano-mainnet.blockfrost.io` base URL. `TransactionBuilder.build`
([`tx/.../TransactionBuilder.kt:94-101`](../../tx/src/commonMain/kotlin/org/sarmidev/kardano/tx/TransactionBuilder.kt))
checks only that the payment/change address network matches the caller's declared
`TransactionBuildRequest.network` — self-consistency, never an allow-list of which network may be
declared. Confirmed during this ADR's preparation:
[`TransactionDraft`](../../tx/src/commonMain/kotlin/org/sarmidev/kardano/tx/TransactionDraft.kt)
**carries no `network` field at all** — it stores `selectedInputs`, `outputs`, `fee`, `ttl`, and
the raw body CBOR, nothing else.

This means a caller can today, entirely through public API:

1. Build a full mainnet draft: `TransactionBuilder.build(TransactionBuildRequest(network =
   Network.MAINNET, payment = <a mainnet address>, ...))`.
2. Sign it with an arbitrary, real mnemonic:
   `ReadOnlyWallet.signTransaction(realMnemonic, Network.TESTNET, thatDraft)` — passing
   `Network.TESTNET` here does not lie about anything `signTransaction` checks, because
   `signTransaction` reads neither its own `network` argument nor anything on `draft` that would
   reveal it was built for mainnet.

**This is the precise reason the audit's suggested minimal fix — reject
`network != Network.TESTNET` inside `signTransaction` — is insufficient by itself.** Adding that
check would only validate the caller's own `network` *argument*; it would not, and structurally
cannot, validate what `draft` was actually built for, because nothing connects the two. A caller
that (accidentally or not) passes `Network.TESTNET` alongside a mainnet-built `draft` would sail
straight through such a check. Real enforcement requires the network (or, more precisely, the
full ADR-0015 §2a scope) to be **bound to the `TransactionDraft` itself**, not asserted
separately by a second, disconnected parameter.

ADR-0015 §2a already reasoned through why this exists: `:wallet` cannot depend on `:shared`
(the sample/UI host), so it cannot import `:shared`'s `TestWalletFixture` to recognize "this is
the fixture" — the fixture-only/testnet-only guarantee was therefore made a **Phase 1 call-site
and test-suite discipline**, not a `:wallet`-internal runtime check, and every actual Playground
call site is confirmed hardcoded to `Network.TESTNET` and the fixture
(`PlaygroundPresenter.kt:440,608,738,751,893,976`). Reading ADR-0015 in full confirms this was a
deliberate, considered choice for an internal, single-consumer repository — not an oversight. The
audit's own dual rating (§4.6) agrees: by-design and acceptable for the project's current internal
development scope, High once the SDK is a public, source-reachable artifact.

---

## Decision

### 1. What kind of problem this actually is

W7-1 is a **combination**, not a single category, and the combination is the point:

- **Not, by itself, a runtime-enforcement defect** under ADR-0015's own internal-development-scope
  frame — the ADR explicitly authorized exactly this design, for exactly the dependency-direction
  reason above, and every in-repo caller respects the intended scope.
- **It is an API-contract/visibility problem.** Nothing in the *type system* distinguishes "the
  Phase 1 fixture-only testnet entry point" from "a general-purpose signing API" — the KDoc says
  the former, the compiler allows the latter. A good-faith integrator reading only the function
  signature (not the KDoc, not this repository's guardrail file) has no compiler- or IDE-level
  signal that anything is restricted.
- **It is also an artifact-publication-policy problem**, but not purely so: `docs/RELEASING.md`
  states plainly that "Kardano SDK does not publish Maven artifacts yet" and that Maven
  publication "requires a separate decision" — so the narrowest reading of the audit's own
  language ("the moment this becomes a public, installable artifact") has not technically
  happened yet. This ADR's assessment is that this narrow reading understates the real exposure:
  a Kotlin Multiplatform module is trivially usable straight from a tagged source clone (a git
  submodule, a Gradle composite build, or a `mavenLocal()` publish anyone can run themselves,
  costing an integrator a few minutes, not a Maven Central listing). The friction difference
  between "git-tag source release" and "installable Maven artifact" is small enough that this ADR
  treats W7-1 as materially relevant **to the first source release itself**, not deferrable to
  "whenever Maven publication happens."

### 2. What has to be accounted for

- **Arbitrary caller-supplied mnemonics.** `signTransaction` validates only BIP-39 structural
  validity (`Mnemonic.parse`); it cannot and does not distinguish the cited Phase 1 fixture from
  any other valid mnemonic, including a real one.
- **Mainnet drafts.** Buildable today via the same public `TransactionBuilder` any Playground call
  uses; nothing rejects `Network.MAINNET` as a build target.
- **Public `Network.MAINNET` / `BlockfrostNetwork.MAINNET`.** Both are ordinary, unguarded enum
  constants — removing or hiding them is not a real option, since `Network` and
  `BlockfrostNetwork` are legitimate general-purpose SDK types used correctly elsewhere (address
  parsing, provider configuration) that must be able to represent mainnet structurally even where
  Phase 1's own signing path must not act on it.
- **Public crypto primitives.** `:crypto`'s `Signing`, `KeyDerivation`, and `Mnemonic` are already
  public, backend-delegated, general-purpose primitives (ADR-0009/ADR-0010) — restricting *those*
  would break their own, already-correct, general-purpose contract. The scope problem is specific
  to `:wallet`'s orchestration entry point, not to the primitives it composes.
- **Open-source consumers can modify source.** Any runtime guard this ADR could add is trivially
  removable by a consumer building from a forked or patched copy of the source. This reframes the
  actual goal: **not** "prevent a determined bad actor from misusing the code" (impossible for an
  open-source library by construction) but **"give a good-faith integrator an honest,
  hard-to-miss signal about what this entry point is actually authorized/verified for"** — the
  same "tell the user exactly what happened" principle the Playground redesign (W9-1 remediation)
  already applies to end users, extended here to SDK-consuming developers.

### 3. Options compared

| # | Option | Effort / diff size | Solves the binding problem (§1's exploit)? | Blocks first source release if adopted as-is? |
|---|---|---|---|---|
| 1 | Do not publish installable SDK artifacts yet | None (already true per `docs/RELEASING.md`) | No — irrelevant to source-clone reachability (see §1) | N/A — but doesn't address the actual risk this ADR is about |
| 2 | Opt-in experimental annotation (`@RequiresOptIn`) + explicit scope naming | Small (~30-60 lines: one annotation type + apply-sites + KDoc) | No — it is a *visibility/intent* signal, not a binding check | No |
| 3 | Redesign `TransactionDraft`/signing so network + supported scope are represented and validated in the type | Large (spans `:tx` body/serializer, `:wallet` orchestration, breaking API change) | Yes — this is the only option that actually closes §1's exploit | Not required to block it, but is the real fix and should be scheduled deliberately |
| 4 | Expose only a deliberately bounded demo-signing façade instead of the general entry point | Medium (visibility narrowing + a renamed, narrower public entry point) | Partially — makes the *intended* narrow entry point unambiguous by name, but `:wallet` still cannot verify "this is the fixture" (ADR-0015 §2a's constraint is unchanged) | No |
| 5 | Defer general signing to a later ADR | None (this is a "do nothing new" option) | No | No — but leaves the honesty gap open indefinitely without even a KDoc-level compiler signal |

**Option 1** is rejected as a primary response: it doesn't address the source-clone exposure this
ADR itself identifies (§1), and blocking all artifact publication indefinitely conflicts with the
stated business objective of reaching a first public *source* release — `docs/RELEASING.md`
already correctly treats Maven publication as a separate, later decision; this ADR doesn't need to
re-decide that.

**Option 3** is the only option that actually fixes the binding problem in §1 (a `network`
argument that isn't connected to the thing being signed). It is also the largest and riskiest:
`TransactionDraft` is constructed by `TransactionBodySerializer`/`TransactionBuilder`, consumed by
`:wallet` and `:shared`, and asserted on by existing tests (`TransactionBuilderTest`,
`PlaygroundTransactionDraftPresenterTest`) — adding a `network` property (and deciding what
"supported scope" means as a type, e.g. an ADA-only/single-payment marker) is a genuine, reviewable
redesign, not a small patch. It should happen, but not as a rushed precondition for the first
source tag.

**Option 5** (pure deferral) is rejected as insufficient on its own: it leaves the *current* state
— no compiler/IDE signal whatsoever — unchanged indefinitely, with no forcing function to revisit
it. A "defer" decision is only responsible when paired with *something* cheap in the meantime.

**Options 2 and 4 are complementary, not competing**, and this ADR recommends adopting both
together now, with Option 3 explicitly scheduled as a separate future ADR/block (§4).

### 4. Recommendation: Options 2 + 4 now; Option 3 as a separately-scheduled future ADR

Adopt, as a **future implementation task** (not authorized by this ADR itself):

1. **Rename the entry point to name its exact scope**, e.g.
   `ReadOnlyWallet.signTestnetFixtureTransaction` (exact name to be finalized in the
   implementation task) rather than the generic `signTransaction` — so the *name itself*, not
   only the KDoc, tells an integrator this is not a general-purpose signer. This is Option 4's
   realistic form: ADR-0015 §2a's dependency-direction constraint (`:wallet` cannot depend on
   `:shared`) is unchanged, so `:wallet` still cannot verify "this is actually the fixture" — the
   rename narrows *intent signaling*, not enforcement.
2. **Add a dedicated opt-in annotation** (Option 2), e.g. `@ExperimentalKardanoSigningScope`
   annotated `@RequiresOptIn(level = RequiresOptIn.Level.ERROR)`, applied to the renamed entry
   point (and, for symmetry, to `Network.MAINNET`/`BlockfrostNetwork.MAINNET` themselves, so
   selecting mainnet anywhere in the SDK requires the same explicit opt-in). A caller must write
   `@OptIn(ExperimentalKardanoSigningScope::class)` to compile against it, which is a genuine
   compiler-level speed bump a KDoc comment is not.
3. **State plainly, in the annotation's own KDoc and in this ADR, what this does and does not
   achieve**: it is a **signal**, not a **binding check** — it does not close the §1 exploit (an
   integrator can still opt in and then sign a mainnet draft with a real mnemonic; nothing stops
   that). This must not be described in release notes or KDoc as "safe" or "restricted" in any
   sense beyond "requires an explicit, documented, IDE-visible opt-in."

**KMP/Swift implication (must be documented in the implementation task):** Kotlin's
`@RequiresOptIn` enforcement is a **Kotlin-compiler-only** mechanism. When `:wallet` is consumed
through the compiled `:shared`/framework boundary from Swift, the opt-in requirement does **not**
carry over as a Swift-visible compile-time gate — a Swift caller sees an ordinary function with no
enforced opt-in. For iOS consumers, the annotation's rename (item 1) and its KDoc are therefore the
*only* effective signal; the compiler gate in item 2 benefits Kotlin/JVM/Android consumers only.
This asymmetry must be stated explicitly wherever the annotation is documented, not left implicit.

**Module dependency direction:** neither item 1 nor item 2 changes any module's dependency graph —
both are internal to `:wallet`'s own public surface. This ADR does not reopen or reverse
ADR-0015 §2a's "no `:wallet` → `:shared`" rule.

**Option 3 (the real fix) is formally scheduled, not abandoned**, as its own future ADR once one
of two triggers occurs: (a) Maven/binary publication is seriously proposed (per
`docs/RELEASING.md`'s own "requires a separate decision" framing), or (b) any future block
proposes mainnet or general-purpose wallet support (which ADR-0015 §2a already said requires its
own explicit ADR). That future ADR should design `TransactionDraft`'s network/scope binding
end-to-end — this ADR intentionally does not pre-design it, to keep this decision focused and
reviewable.

### 5. Is this a precondition for the first source tag?

**No, with a condition.** This ADR's *decision* (this document) should land before the tag, so the
release notes can accurately state the chosen scope and cite it — that is a documentation
precondition, satisfied by this ADR's existence. The *implementation* of items 1-2 above (rename +
opt-in annotation) is **recommended but not required** before the first source tag; if not
implemented before that tag, the release notes must carry it forward explicitly as an accepted,
named residual scope (see the final re-audit gate's "unresolved risks carried into release notes"
requirement), not silently omitted. Option 3 (the real fix) is explicitly **not** a precondition
for the first source tag under any circumstance contemplated by this ADR — it is future work,
scheduled per §4.

---

## Consequences

- W7-1 remains an accurately-documented, dual-rated finding (by-design for internal development,
  a real gap for public reachability) — this ADR does not reclassify it, it decides what to do
  about the public-reachability half.
- No code changes are authorized by this ADR. A future, separately-reviewed implementation PR
  covers items 1-2 of §4; a further future ADR covers Option 3.
- `docs/RELEASING.md`'s existing framing (no Maven publication yet; a tag is the current release
  vehicle) is unchanged and is not re-litigated by this ADR.
- This ADR does not authorize widening `:wallet`'s dependency graph, does not add a `:wallet →
  :shared` edge, and does not weaken any existing guardrail.
