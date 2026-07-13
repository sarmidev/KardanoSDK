# ADR-0014: Minimal ADA Transaction Builder

| Field   | Value                                                                 |
|---------|------------------------------------------------------------------------|
| Status  | **Accepted**                                                          |
| Scope   | Block 1.9a — `:tx` module boundary, unsigned-transaction-body scope, Cardano CBOR map ordering, input-set ordering, output encoding form, fee/size and min-ADA/change policy, error model, sub-block split |
| Phase   | Phase 1 (Block 1.9a)                                                  |
| Updated | 2026-07-13                                                            |

---

## Context

By the end of Block 1.8, the read-only path is complete: `:wallet` can restore the cited
test-only wallet, generate a testnet base address, query UTxOs through a caller-supplied
`ChainQueryProvider`, and sum an ADA-only balance; `:provider` exposes provider-neutral
`Utxo`, `Value` (ADA-only, `coin: Lovelace`), `ProtocolParameters`
(`minFeeCoefficient`, `minFeeConstant`, `keyDeposit`, `poolDeposit`, `maxTxSize`,
`coinsPerUtxoByte`) and the read-only `ChainQueryProvider`; and `:core` holds `Address`
(parse + `baseAddress` + `toBech32()` + `toByteArray()`), `Lovelace`, `UtxoRef`, `TxHash`,
and the bounded definite-length CBOR subset (`Cbor` / `CborValue` / `CborError`).

Block 1.9 (Transaction Builder Minimal) is the first block that constructs transaction
structure. ADR-0005 §6 defined "minimal ADA transaction" (one or more inputs, one payment
output, one change output, a computed fee, a validity interval only if required) and
**explicitly deferred one serialization prerequisite to this block**: whether Cardano
transaction serialization requires RFC 7049 length-first map ordering instead of the RFC 8949
§4.2.1 bytewise ordering that Phase 0 (ADR-0001) uses for the general-purpose `:core` CBOR
subset. That prerequisite, plus the module/ownership decision, the exact unsigned-artifact
scope, input-set ordering, the transaction-output encoding form, the fee/size and
min-ADA/change policy, and the error model, must be resolved before any 1.9 code is written.

This ADR follows the pre-implementation pattern of ADR-0012 (Block 1.7a) and ADR-0013
(Block 1.8a): record the decision, then split the implementation into `b`/`c` sub-blocks. It
authorizes no code; Block 1.9a is docs-only.

The hard rules stand: no transaction signing before Block 1.10's own scoped decision, no
witness/signature construction here, no submit, no mainnet, no real mnemonics/keys/funds, no
handwritten cryptography, and no weakening of any validator or parser policy.

---

## Decision

### 1. Create a new Gradle module `:tx` in Block 1.9b, depending on `:core` and `:provider` only

Transaction building is introduced as a new Gradle module, not a package inside an existing
module.

- Targets mirror `:provider`/`:wallet`: `iosArm64`, `iosSimulatorArm64`, `jvm`,
  `androidLibrary { withHostTest }`, `explicitApi()`.
- Android namespace and package: `org.sarmidev.kardano.tx`.
- Registered in `settings.gradle.kts` as `:tx`; referenced elsewhere via the typed project
  accessor `projects.tx`.
- `commonMain` depends on **`:core`** (for `Address`, `Lovelace`, `UtxoRef`, `TxHash`,
  `Network`, `KardanoResult`, and the `encoding.cbor` subset) and **`:provider`** (for the
  provider-neutral models `Utxo`, `Value`, `ProtocolParameters`).
- `commonTest` adds `libs.kotlin.test` (and `libs.kotlinx.coroutinesTest` only if any test
  turns out to need it; the builder itself is not `suspend`). No new external `commonMain`
  dependency is introduced.

`:tx` does **not** depend on:

- **`:wallet`** — the builder is a pure function over `List<Utxo>` + `ProtocolParameters` +
  addresses supplied by the caller; it holds no wallet state and performs no restore.
- **`:shared`** — `:shared` is the sample/UI host (ADR-0011 §3) and may only call `:tx` for
  display, never the reverse.
- **`:provider-blockfrost`** — `:tx` never performs I/O; it queries no provider (see §2), so
  it needs neither the provider interface's transport nor any HTTP client.
- **`:crypto`** — the builder emits transaction-body bytes only and does not hash or sign; the
  transaction id (a Blake2b-256 hash of the body) is produced by the caller (see §2).

Why transaction-building logic cannot live in an existing module:

- **`:core`** is dependency-free by design (ADR-0002/0003) and must stay so; the builder must
  consume `:provider`'s `Utxo`/`Value`/`ProtocolParameters`, so it cannot live in a module
  that is forbidden to depend on `:provider`.
- **`:provider`** is the read-only chain-query boundary (ADR-0006). Constructing and
  serializing a transaction from already-fetched inputs is a different concern from querying
  the chain; placing it in `:provider` would overload that boundary and pull serialization
  into the query layer.
- **`:wallet`** is the read-only wallet-state module (ADR-0013) and itself depends on
  `:crypto`; hosting the builder there would give a signing-free, crypto-free builder a
  transitive `:crypto` dependency it does not need and would conflate "wallet state" with
  "transaction construction."
- **`:shared`** is explicitly barred from owning SDK protocol logic (ADR-0011 §3); a
  transaction serializer is exactly the protocol logic that rule excludes.

This is the ADR-0002/ADR-0005 module-extraction trigger firing: real dependency-direction
pressure (`:core` + `:provider` models, but not `:crypto`/`:wallet`) that no existing module
can host without inverting a boundary another ADR already fixed. `:tx` was pre-named as a
candidate module in ADR-0002/ADR-0005 and `docs/ROADMAP.md`.

### 2. Block 1.9 builds an unsigned transaction **body** only; 1.9b emits its canonical CBOR bytes; the caller (not `:tx`) produces the transaction id

The artifact of Block 1.9 is the Conway `transaction_body` map with the three mandatory
fields and an optional validity field:

- `0` — inputs (a `set<transaction_input>`; see §4 for encoding and ordering)
- `1` — outputs (the payment output, followed by the change output when change is non-zero;
  see §5)
- `2` — fee (`coin`; see §6)
- `3` — time to live (`invalid_hereafter`, a `uint` slot) — **included only when the caller
  supplies a ttl**, omitted otherwise

**Block 1.9b emits the canonical CBOR bytes of this `transaction_body`.** Emitting the body
bytes is the point of the block ("generate the transaction body / CBOR needed for future
signing", `docs/PHASE_1_PLAN.md` §1.9); the bytes are what Block 1.10 will hash and sign.

The block does **not** build a full `transaction`
(`[ transaction_body, transaction_witness_set, bool, auxiliary_data / null ]`). The witness
set requires signatures, which requires signing — out of scope until Block 1.10. `:tx`
therefore returns the body bytes and a structured summary (selected inputs, outputs, fee,
ttl), not a signed or submittable transaction.

**The transaction id / body hash is not computed by `:tx`, and Block 1.9 does not compute or
display it anywhere.** The transaction id is `Blake2b-256(transaction_body_bytes)`; hashing
lives in `:crypto` (`Hashing.blake2b256`, Block 1.5b). To keep `:tx` crypto-free and
signing-free (§1), `:tx` exposes only the body bytes, never a hash of them. **Block 1.9c's
`:shared` Playground checkpoint also does not compute or display a transaction id or body
hash** — it displays only the unsigned draft's structural summary (selected input/output
counts, fee, change, encoded body size, and a truncated body-CBOR hex preview; see §10). A
transaction id is only meaningful once the body is finalized (its fee correct against a real
witness set), which does not happen until signing exists, so computing and showing one before
then would either hash a still-provisional body or require `:shared` to anticipate
signing-era logic ahead of its own block. **Displaying the transaction id / body hash is
therefore deferred to Block 1.10 (Transaction Signing) or whichever block introduces
signing/finalization first** — not to Block 1.9c. A future revision may reconsider exposing
the id from `:tx` itself if a non-display consumer needs it; Block 1.9 has no such consumer,
so the crypto dependency is not added now.

Out of scope for Block 1.9 (each deferred to its own later block or phase): native assets /
multi-asset values, metadata / auxiliary data, certificates, withdrawals, native or Plutus
scripts, collateral, datums (hash or inline), reference inputs, minting, required signers,
network-id body field, treasury/donation fields, witness-set construction, signing, and
submit.

### 3. Cardano transaction CBOR uses RFC 7049 §3.9 canonical map ordering (length-first, then bytewise); `:core`'s CBOR subset is reused unchanged for the 1.9 MVP

**Resolution of the ADR-0005 §6 deferred item:** Cardano transaction serialization follows the
canonical CBOR ordering defined in **RFC 7049 §3.9** — map keys are sorted **shorter encoding
first, then bytewise (lexicographic) among equal-length encodings** — not the RFC 8949 §4.2.1
purely-bytewise rule. Authoritative sources:

- **CIP-21, "Canonical CBOR serialization format"**
  (`cardano-foundation/CIPs`, `CIP-0021`): transactions "must be serialized in line with
  suggestions from Section 3.9 of CBOR specification RFC" — integers as small as possible,
  lengths as short as possible, "the keys in every map must be sorted from lowest value to
  highest", definite-length only.
- **RFC 7049 §3.9** (Canonicalization): the length-first-then-bytewise key ordering rule.
- **Cardano ledger CDDL** (`IntersectMBO/cardano-ledger`, Alonzo/Conway `cddl-files`): the
  script-data comment states the RFC 7049 §3.9 rule verbatim — "If two keys have different
  lengths, the shorter one sorts earlier. If two keys have the same length, the one with the
  lower value in (byte-wise) lexical order sorts earlier."
- **`cardano-api`** (`Cardano.Api.Serialise.Cbor.Canonical`, `IntersectMBO/cardano-api`):
  implements the same rule as supporting evidence —
  `compare (length b1) (length b2) <> compare b1 b2` over each key's encoded bytes.

RFC 8949 (the successor to RFC 7049) keeps length-first ordering available as an explicit
option precisely for protocols, like Cardano, that require the legacy RFC 7049 canonical form.

**`:core`'s CBOR subset is reused unchanged for the Block 1.9 MVP.** The MVP
`transaction_body` map keys are the integers `0`, `1`, `2`, and optionally `3`. Every one of
these encodes to a **single byte** (`0x00`, `0x01`, `0x02`, `0x03`). For single-byte keys the
two rules are byte-identical: they all have equal length (1 byte), so RFC 7049's length-first
tie-breaker reduces to the same bytewise comparison RFC 8949 uses, and both agree with the
strict ascending order `:core`'s encoder already validates (ADR-0001, RFC 8949 §4.2.1). The
canonical body bytes `:core` produces for the MVP are therefore exactly the bytes the Cardano
canonical rule requires — no new deterministic mode, flag, or fork of `:core` is added, and
Phase 0 parser policy is not weakened.

**Explicit limitation (must be revisited before implementation of any feature that adds a map
with heterogeneous or multi-byte keys):** the reuse above holds *only* because every MVP map
key is a single-byte integer. Future Cardano structures with map keys of differing encoded
length — for example multiasset maps (`policy_id` → `asset_name` → amount), withdrawals
(reward-account keys), or body fields with keys ≥ 24 — need RFC 7049 length-first ordering,
which **diverges** from `:core`'s current bytewise rule and which `:core`'s encoder would
actively **reject** (`NonCanonicalMapKeyOrder`) if handed length-first-but-not-bytewise order.
Before any such feature is implemented, this must be resolved by either (a) extending `:core`
with an explicit Cardano/length-first deterministic mode selected by the caller, or (b) a
`:tx`-owned canonical emitter for those specific structures — in both cases **without**
relaxing `:core`'s existing strict "reject, never normalize" Phase 0 policy. Block 1.9b must
document this constraint in `:tx` and its tests, and must not silently emit a map that only
happens to be valid because its keys are single-byte.

### 4. Transaction inputs (field 0) are sorted by the ledger `(transaction_id, index)` order and encoded as a plain untagged definite-length array

`transaction_input = [ transaction_id : $hash32, index : uint ]`. Field 0 is a **set**, and
the Cardano ledger does not honor the serialized element order: it treats the field as a set
ordered by the `(transaction_id, index)` pair. The Cardano Developer Portal's Conway CBOR
reference states this directly — "the specifications assume that the inputs are ordered
lexicographically in the pair `(transaction_id, index)`" — and it matters because redeemer
indexing (out of scope here, but a forward constraint) refers to positions in that ordered
list. This corresponds to the ledger's `Ord TxIn` (compare `TxId` bytes, then the numeric
index) and to CIP-21's requirement that set/map elements be canonically ordered and
duplicate-free.

**Block 1.9b sorts inputs ascending by `transaction_id` bytes first (unsigned bytewise over
the 32-byte hash), then by `index` (numeric, ascending)**, and rejects duplicate
`(transaction_id, index)` pairs. This is the authoritative ledger `(transaction_id, index)`
tuple order, not an arbitrary convention. Because every `transaction_input` shares the same
outer shape (a 2-element array whose first element is a fixed 32-byte bytestring), this tuple
order coincides with ordering by each element's canonical encoded bytes in the common case;
the tuple order is specified as the authoritative rule so that the numeric `index` comparison
(rather than its variable-width CBOR encoding) is unambiguous.

Field 0 is encoded as a **plain, untagged, definite-length CBOR array** (major type 4), not a
tagged set. Conway optionally allows a `#6.258` tag on set-typed fields, but CIP-21 permits
the untagged form as long as it is used consistently ("either there are no tags 258 in sets,
or there are such tags everywhere"); the MVP uses none. The untagged array also stays within
`:core`'s CBOR subset, which rejects all tags (`TagsNotSupported`). This choice is recorded so
a later block that introduces tagged sets does so deliberately and consistently.

### 5. Transaction outputs (field 1) use the legacy/Alonzo array form `[address, coin]` for ADA-only outputs

The Conway CDDL defines
`transaction_output = legacy_transaction_output / post_alonzo_transaction_output`, with:

- `legacy_transaction_output = [ address, amount : value, ? datum_hash : $hash32 ]`
- `post_alonzo_transaction_output = { 0 : address, 1 : value, ? 2 : datum_option, ? 3 : script_ref }`

The ledger CDDL states the two forms are interchangeable ("Both of the Alonzo and Babbage
style TxOut formats are equally valid and can be used interchangeably",
`IntersectMBO/cardano-ledger` Conway `cddl/data/conway.cddl`). For an ADA-only output,
`value = coin / [coin, multiasset<positive_coin>]` collapses to `value = coin` and `coin = uint`.

**Block 1.9b encodes each output in the legacy array form as a two-element definite-length
array `[ address_bytes, coin ]`**, where:

- `address_bytes` is `CborByteString(address.toByteArray())` — the raw Shelley address bytes
  (8-bit header + payload) that `:core`'s `Address` already exposes;
- `coin` is `CborUnsigned(lovelace.value)`;
- the optional `datum_hash` element is omitted (no datums in the MVP).

This form is valid for a minimal ADA-only payment or change output in the Alonzo-through-Conway
eras because it is one of the two ledger-accepted output encodings, it carries exactly the two
mandatory components (address and an ADA-only value), and it needs no inner map — so it raises
no map-key-ordering question (§3) and stays entirely within `:core`'s CBOR subset. The legacy
array is preferred over the post-Alonzo map form for the MVP precisely because the map form
would introduce an inner integer-keyed map whose ordering, while also single-byte-keyed today,
adds surface with no MVP benefit.

The output-encoding question is resolved with confidence from the cited CDDL, so it does
**not** block Block 1.9b.

### 6. Fee is `minFeeCoefficient * txSize + minFeeConstant`, where `txSize` is the estimated size of the whole signed transaction, not the body alone; the fee is an estimate until Block 1.10

Cardano's linear fee is `fee = minFeeA * txSize + minFeeB`, mapped to this SDK's
`ProtocolParameters` as `fee = minFeeCoefficient * txSize + minFeeConstant`. The ledger applies
`txsize tx ≤ maxTxSize` and computes the fee over the **entire serialized transaction**
(`IntersectMBO/cardano-ledger` Babbage/Conway UTxO rules), i.e. the
`[ body, witness_set, bool, auxiliary_data / null ]` wrapper — **not** the body in isolation.
Estimating from `bodyCbor` plus "raw witness bytes" alone would undercount the array wrapper
and the witness-set map structure and would produce a fee below the ledger minimum.

**Block 1.9b estimates `txSize` as the sum of all four wrapper components**, computed
arithmetically from known CBOR byte counts (only the body is actually encoded through `:core`;
the wrapper, the validity flag, the auxiliary-data placeholder, and the witness set are
size-accounted, not emitted — which also avoids needing `:core` to encode the `bool`/`null`
simple values its subset does not support):

- **Wrapper array header** `[ _, _, _, _ ]`: 1 byte.
- **Transaction body**: `|bodyCbor|` (the bytes actually produced by `:core`).
- **Witness set** `{ 0 : [* vkeywitness] }` with `N` vkey witnesses, where
  `vkeywitness = [ $vkey /* 32-byte bytestring */, $signature /* 64-byte bytestring */ ]`:
  - map header (1 entry): 1 byte; key `0`: 1 byte; inner-array header for `N` elements:
    `headSize(N)` bytes, where `headSize` is the **same canonical CBOR shortest-form
    head-size rule `:core`'s own encoder already implements** (`Cbor`'s internal
    `encodeHead`, ADR-0001) rather than a new, invented rule: 1 byte for `N < 24`, 2 bytes
    for `24 ≤ N ≤ 255`, 3 bytes for `256 ≤ N ≤ 65_535`, 5 bytes for `65_536 ≤ N ≤
    4_294_967_295` (unreachable here — see below), 9 bytes beyond that;
  - per witness: array(2) header (1) + 32-byte bytestring (2 header + 32) + 64-byte
    bytestring (2 header + 64) = 101 bytes;
  - witness-set total = `2 + headSize(N) + 101 * N` bytes, valid for **any** `N`, not only
    `N < 24`.
- **Validity flag** (`bool`): 1 byte.
- **Auxiliary data** (`null`): 1 byte.

**Block 1.9b must not impose an arbitrary `N < 24` cap on the number of selected inputs to
keep this formula simple.** The witness-set estimator computes `headSize(N)` generically (as
above) so the fee stays correctly estimated regardless of how many inputs coin selection
picks. In practice `N` cannot exceed `CBOR_MAX_COLLECTION_ELEMENTS` (65,536): the body's own
input array (field `0`) is encoded through `:core`, which enforces that same named limit on
every array/map it produces, and `N` (one witness per selected input, §6 below) is bounded by
the number of body inputs. So `headSize(N)` only ever needs the `1`/`2`/`3`-byte bands above
for a body `:core` will actually accept; the 5-/9-byte bands are listed only to state the
general rule completely, not because 1.9b expects to reach them.

**Witness-count assumption for the MVP:** `N` = the number of selected inputs (one vkey
witness per input). This is a documented, conservative upper bound: the real transaction needs
one witness per distinct payment key, which is ≤ the number of inputs, so estimating one per
input never underestimates the fee for the single-key test wallet. Block 1.9b records this
assumption in KDoc and tests.

**The fee is an estimate, not the final fee, because no witnesses exist yet.** The exact
witness set — and therefore the exact `txSize` and fee — is only known once Block 1.10 signs
the body. **Impact on Block 1.10:** signing must recompute (or validate) the fee against the
real witness set and, if the real size differs from this estimate, rebuild the body with the
corrected fee/change before signing the final bytes. Block 1.9b's KDoc and the 1.9c checkpoint
copy label the fee as an estimate for an unsigned draft.

**Fee/change fixed-point loop (the size components above are fully specified, so the loop is
defined):**

1. Select inputs largest-first from the caller-supplied `List<Utxo>` until they cover
   `payment + fee_seed` (`fee_seed = minFeeConstant`).
2. Set `fee = minFeeConstant`.
3. Loop (bounded, e.g. ≤ 8 iterations): compute `change = Σ selectedInputs − payment − fee`;
   assemble the body (omitting the change output when `change == 0`, per §7); estimate
   `txSize` from the components above; compute `feeNext = minFeeCoefficient * txSize +
   minFeeConstant`. If `feeNext == fee`, stop; otherwise set `fee = feeNext` and repeat. If
   `change` would go negative, add the next input largest-first and continue; if none remain,
   fail with `InsufficientFunds`.
4. If the loop does not converge within the cap, take `conservativeFee = maxOf(lastFee,
   lastFeeNext)` (the larger, and therefore conservative, of the last two estimates) and
   rebuild the body **exactly once more** with it, rather than looping unbounded.
5. **That final rebuild must itself be checked, not trusted blindly.** Rebuilding at
   `conservativeFee` can require selecting additional inputs to cover the larger trial fee,
   and each additional input adds another witness to the size estimate — which can push the
   *next* fee estimate past `conservativeFee` again. If the rebuilt body's re-estimated fee is
   still greater than `conservativeFee` (the fee actually encoded into that rebuilt body), the
   builder fails with `TxBuildError.FeeEstimateDidNotConverge(encodedFee, recomputedFee)` (§8)
   rather than returning a `TransactionDraft` whose encoded fee is a known under-estimate.

All arithmetic is on `Long` lovelace with overflow checks before each operation (never
truncate); overflow fails with `FeeCalculationOverflow` (§8).

### 7. Minimum-ADA and change policy: enforce the Babbage/Conway min-UTxO rule, omit zero change, reject dust change

**Min-UTxO rule (sourced).** The Babbage/Conway minimum ADA for an output is
`minADA = (160 + serializedOutputSizeInBytes) * coinsPerUtxoByte`, where the constant overhead
`160 = 20 words * 8 bytes` approximates the in-memory cost of the `TxIn` and the UTxO-map
entry. Sources: the ledger `babbageMinUTxOValue` implementation
(`IntersectMBO/cardano-ledger`, `eras/babbage/impl/.../TxOut.hs`:
`Coin $ fromIntegral (constantOverhead + sizedSize sizedTxOut) * fromIntegral cpb`,
`constantOverhead = 160`) and the Cardano glossary "UTxO Cost per Byte"
(`(160 + serialized size of the output) × utxoCostPerByte`). The serialized output size is the
CBOR byte length of that output as encoded per §5, using the module's own
`ProtocolParameters.coinsPerUtxoByte`.

Block 1.9b applies this rule to both outputs:

- **Payment output.** If the requested payment amount is below its own computed min-UTxO, fail
  with `InvalidOutputAmount` (§8). The builder does not silently raise the payment.
- **Change output.**
  - **Zero change** (`change == 0`): the change output is **omitted** entirely, producing a
    valid single-output transaction.
  - **Change ≥ its min-UTxO**: emit the change output back to the caller-supplied change
    address.
  - **Dust change** (`0 < change < min-UTxO` for the change output): **reject** with
    `ChangeBelowMinimum` (§8). The builder does **not** fold dust into the fee: doing so would
    change fee semantics and must be an explicit, separately justified and tested future
    decision, not an implicit behavior in the minimal MVP.

Because the min-UTxO formula is established with confidence here, Block 1.9b enforces it (no
fallback/deferral is needed). The draft remains an unsigned, unsubmitted structural artifact:
enforcing min-UTxO improves fidelity but the draft is still not a full ledger validation and
is never presented as submittable.

### 8. Error model: a `:tx`-owned sealed `TxBuildError`; provider errors are not part of it

Block 1.9b exposes a sealed error type, returned via `KardanoResult` (no throwing, per the KMP
error policy):

```kotlin
public sealed interface TxBuildError {
    public data object NoInputs : TxBuildError
    public data object NoOutputs : TxBuildError
    public data class InvalidProtocolParameters(
        public val field: String,
        public val value: Long,
    ) : TxBuildError
    public data class FeeEstimateDidNotConverge(
        public val encodedFee: Long,
        public val recomputedFee: Long,
    ) : TxBuildError
    public data class InsufficientFunds(
        public val required: Long,
        public val available: Long,
    ) : TxBuildError
    public data class InvalidOutputAmount(
        public val amount: Long,
        public val minRequired: Long,
    ) : TxBuildError
    public data class ChangeBelowMinimum(
        public val change: Long,
        public val minRequired: Long,
    ) : TxBuildError
    public data class ExceedsMaxTxSize(
        public val size: Long,
        public val max: Long,
    ) : TxBuildError
    public data object FeeCalculationOverflow : TxBuildError
    public data class Serialization(public val error: CborError) : TxBuildError
    public data class NetworkMismatch(
        public val expected: Network,
        public val actual: Network,
    ) : TxBuildError
    public data class UnsupportedFeature(public val detail: String) : TxBuildError
    public data class DuplicateInput(public val ref: UtxoRef) : TxBuildError
}
```

- `NoInputs` — the candidate input list is empty.
- `NoOutputs` — the outputs list is empty; a minimal transaction body (§2) must have at least
  one output. Implementation-discovered addition (Block 1.9b-1): the sketch above did not
  originally name this case, but the same "at least one input/output" MVP requirement that
  motivates `NoInputs` applies to outputs too, and `NoInputs` itself turned out to be reachable
  directly from the 1.9b-1 serializer as well, not only from the coin-selection builder.
- `InvalidProtocolParameters` — a `ProtocolParameters` field the builder depends on
  (`minFeeCoefficient`, `minFeeConstant`, `maxTxSize`, or `coinsPerUtxoByte`) is negative.
  Implementation-discovered addition (Block 1.9b-2 review): `ProtocolParameters` is a plain
  data class of `Long` fields with no non-negativity invariant of its own, so `:tx` validates
  these fields are all `>= 0` before any min-ADA or fee arithmetic runs — a negative
  `coinsPerUtxoByte` in particular would otherwise silently defeat the min-UTxO check (§7)
  rather than fail loudly.
- `FeeEstimateDidNotConverge` — the fee/change fixed-point loop's final conservative rebuild
  (step 5 of §6's loop) itself required a higher fee than the one it encoded. Implementation-
  discovered addition (Block 1.9b-2 review): the conservative rebuild can need to select
  additional inputs to cover its larger trial fee, and each additional input's witness can
  push the re-estimated fee past what that same rebuild just encoded; this variant reports
  that case instead of returning an under-estimated `TransactionDraft`.
- `InsufficientFunds` — selected inputs cannot cover `payment + fee` with no candidates left.
- `InvalidOutputAmount` — the payment output is below its computed min-UTxO (§7).
- `ChangeBelowMinimum` — non-zero change below the change output's min-UTxO (§7).
- `ExceedsMaxTxSize` — the estimated `txSize` exceeds `ProtocolParameters.maxTxSize`.
- `FeeCalculationOverflow` — `Long` overflow anywhere in the fee/change arithmetic (§6).
- `Serialization` — wraps a `:core` `CborError` if body encoding fails.
- `NetworkMismatch` — the payment address, change address, or request `network` disagree.
- `UnsupportedFeature` — a forward guard, e.g. a supplied `Utxo` whose `Value` carries native
  assets once `Value` gains a multi-asset field; the ADA-only MVP declines rather than
  silently dropping assets.
- `DuplicateInput` — two supplied inputs share the same `(transaction_id, index)` pair.
  Implementation-discovered addition (Block 1.9b-1): §4 requires duplicate-input rejection, but
  this sketch originally named no dedicated variant for it.

**Provider errors are not in `TxBuildError`.** `:tx` performs no I/O and queries no provider:
the caller passes `List<Utxo>` and `ProtocolParameters` in, so `ProviderError` never arises
inside `:tx`. The `:shared` presenter (Block 1.9c) fetches those inputs beforehand and maps
`ProviderError` with the existing `presentProviderError`, exactly as the Provider and Wallet
Balance checkpoints already do.

### 9. Test and vector policy: structural and CDDL-derived tests; no invented goldens

No self-contained, citable **minimal ADA-only** unsigned `transaction_body` known-answer
vector was located that could serve as a golden without reconstruction (the transaction id is
itself a hash of the body, and the readily available worked examples — e.g. the Cardano
Developer Portal Conway walkthrough — are full transactions with native assets, scripts,
datums, and collateral, not a minimal ADA-only body). Per the project's test-integrity rule,
Block 1.9b therefore uses **structural, CDDL-derived, and decode/inspect tests rather than
invented golden bytes**:

- Encode the body, then decode it back through `:core` `Cbor.decode` and assert the field set,
  field values, and structure match the CDDL (`transaction_body` keys `0/1/2` plus optional
  `3`; inputs as arrays of `[hash32, index]`; outputs as `[address, coin]`).
- **CBOR body map keys/order**: assert keys are exactly the present subset of `{0,1,2,3}` in
  ascending order, and that for these single-byte keys the RFC 7049 length-first and RFC 8949
  bytewise orders coincide (documenting the §3 reuse and its limitation).
- **Input set ordering**: assert inputs are emitted in `(transaction_id, index)` ascending
  order regardless of input order supplied, and that duplicates are rejected.
- **Output encoding form**: assert the legacy `[address, coin]` array shape (address as raw
  bytes, coin as unsigned) with no datum-hash element.
- **Fee/change edge cases**: exact-zero change (output omitted), change just below min-UTxO
  (`ChangeBelowMinimum`), change at/above min-UTxO (emitted), payment below min-UTxO
  (`InvalidOutputAmount`), single vs multiple inputs, largest-first selection, and fee
  fixed-point convergence.
- **Insufficient funds**: `NoInputs` and `InsufficientFunds`.
- **Overflow**: `Long` overflow near `Long.MAX_VALUE` → `FeeCalculationOverflow`.
- **Max tx size**: estimated size over `maxTxSize` → `ExceedsMaxTxSize`.

If a citable minimal ADA-only body vector is later found (for example from `cardano-cli` or a
cited ledger test fixture with a fixed, published hex), it is added verbatim with its source in
the fixture header; until then, no golden bytes are fabricated. **No signing tests are added in
Block 1.9** (there is no signing). Split per the existing convention: native-free logic in
`commonTest`; any end-to-end path in `jvmTest`.

### 10. Sub-block split: 1.9a (this ADR) / 1.9b (`:tx` + builder + tests) / 1.9c (Playground)

- **1.9a** — this ADR (docs only). Resolves the module boundary, the unsigned-body scope, the
  CBOR map-ordering prerequisite, input-set ordering, the output encoding form, the fee/size
  and min-ADA/change policy, and the error model.
- **1.9b** — create the `:tx` module and implement the builder: the transaction model, the
  canonical `transaction_body` serialization via `:core` (§3–§5), largest-first selection with
  the bounded fee/change fixed-point loop (§6–§7), `TxBuildError` (§8), tests (§9), and a
  `:tx/README.md`.
- **1.9c** — the `:shared` Android Playground "Transaction Draft (unsigned)" checkpoint:
  reuse the restored test wallet plus the active provider to obtain candidate inputs and
  protocol parameters, call `:tx`'s `TransactionBuilder.build`, and display the selected
  input/output counts, the estimated fee and any change (in lovelace), the encoded body size
  (in bytes), and a truncated body-CBOR hex preview — clearly labeled as an unsigned,
  not-submitted, testnet-only draft with no real funds. **No transaction id or body hash is
  computed or displayed by this checkpoint**; that is deferred to Block 1.10 (Transaction
  Signing) or whichever block introduces signing/finalization first, per §2.

**All blocking decisions are resolved in this ADR, so Block 1.9b is authorized to proceed
after this ADR is accepted; no item remains that blocks implementation.** If, during 1.9b, the
serialization or fee/min-ADA work reveals an unforeseen ambiguity, that sub-block must stop and
record it here (or in a follow-up ADR) rather than guess. Block 1.9b may itself be split
(for example serialization first, fee/change second) if its diff would exceed the
~300–400-line review target, but no such split is mandated up front.

---

## Rationale

- Creating `:tx` now matches the ADR-0002/ADR-0005 extraction trigger exactly: the builder
  needs `:core` and `:provider` models but not `:crypto`/`:wallet`, a dependency direction no
  existing module can host without inverting a fixed boundary. Keeping it out of
  `:core`/`:provider`/`:wallet`/`:shared` preserves each module's single responsibility and
  keeps `:core` dependency-free.
- Restricting Block 1.9 to the unsigned body — and leaving the id to the caller — keeps `:tx`
  free of `:crypto` and signing while still producing the exact bytes Block 1.10 will hash and
  sign, so the block delivers real, testable output without crossing the signing line the
  guardrails draw at Block 1.10.
- Reusing `:core` unchanged is possible only because the MVP body has single-byte integer keys,
  where RFC 7049 length-first and RFC 8949 bytewise orderings are byte-identical; documenting
  this as a bounded, feature-gated reuse (rather than a general claim) prevents a future
  multiasset/withdrawals map from silently relying on an ordering `:core` does not implement.
- Sorting inputs by the ledger `(transaction_id, index)` order (not an arbitrary
  txHash-then-index convention chosen for convenience) ties the rule to the ledger's own set
  semantics and to redeemer indexing, so a later scripts block inherits a correct ordering.
- Choosing the legacy `[address, coin]` output form keeps the MVP within `:core`'s CBOR subset
  and avoids an inner map entirely, while remaining a ledger-accepted encoding interchangeable
  with the post-Alonzo map form.
- Estimating the fee over the whole `[body, witness_set, bool, aux]` transaction — with a
  documented one-witness-per-input assumption — avoids the classic undercount of fee-from-body,
  and labeling it an estimate makes Block 1.10's responsibility to finalize the fee explicit.
- Enforcing the sourced Babbage/Conway min-UTxO rule and rejecting dust (rather than folding it
  into the fee) keeps change behavior explicit and testable; omitting exactly-zero change
  yields a valid single-output transaction without special-casing.
- A `:tx`-owned `TxBuildError` that excludes provider errors matches the pure-function boundary
  (no I/O in `:tx`) and mirrors how `WalletError` wraps only what its own module can produce.

## Rejected alternatives

- **Build the transaction inside `:wallet` or `:shared`.** Rejected: `:wallet` would gain an
  unneeded transitive `:crypto` dependency and conflate wallet state with construction;
  `:shared` is barred from SDK protocol logic (ADR-0011 §3).
- **Emit a full signed `transaction` (with a witness set) in Block 1.9.** Rejected: that
  requires signing, which is out of scope until Block 1.10's own scoped decision (guardrails).
- **Compute the transaction id inside `:tx`.** Rejected for the MVP: it would add a `:crypto`
  dependency to an otherwise crypto-free module for a value only the display layer needs; the
  caller (which already has `:crypto`) computes it. Left open for reconsideration if a
  non-display consumer appears.
- **Add a Cardano length-first deterministic mode to `:core` now.** Rejected as premature: the
  MVP body's single-byte keys make it byte-identical to `:core`'s existing output, so the
  extra `:core` surface would be unused in Block 1.9. It is deferred to the first feature that
  actually needs heterogeneous-length keys, with the constraint recorded in §3.
- **Encode inputs as a Conway tagged set (`#6.258`).** Rejected for the MVP: the untagged array
  is CIP-21-permitted (used consistently), stays within `:core`'s tag-rejecting subset, and
  needs no new CBOR support. A later block may adopt tagged sets deliberately.
- **Use the post-Alonzo map output form `{0: address, 1: value, ...}`.** Rejected for the MVP:
  it introduces an inner integer-keyed map (more surface, another ordering site) with no
  ADA-only benefit; the interchangeable legacy array form is simpler.
- **Estimate the fee from `bodyCbor` plus raw witness bytes only.** Rejected: it undercounts
  the wrapper array and witness-set map structure and would produce a sub-minimum fee; the
  whole-transaction estimate is used instead.
- **Fold dust change into the fee.** Rejected for the MVP: it silently changes fee semantics;
  dust is rejected with a typed error, and any fold-into-fee behavior must be a separately
  justified and tested future decision.
- **Defer min-UTxO enforcement (build structurally without it).** Rejected: the Babbage/Conway
  formula is established with confidence from the cited ledger source, so enforcing it now adds
  fidelity at no correctness risk; the draft is still labeled unsigned and unsubmitted.

## Consequences

- A new Gradle module `:tx` will exist after Block 1.9b, depending only on `:core` and
  `:provider`; no other module's dependency graph changes, and `:core` stays dependency-free.
- The ADR-0005 §6 CBOR map-ordering prerequisite is resolved: Cardano uses RFC 7049 §3.9
  length-first ordering, and `:core` is reused unchanged for the single-byte-keyed MVP body,
  with a recorded constraint that heterogeneous/multi-byte-keyed maps must revisit this before
  implementation and must not weaken `:core`.
- Block 1.9b will emit unsigned `transaction_body` CBOR bytes plus a structured summary; it
  will not produce a signed or submittable transaction, and no transaction id is computed —
  neither by `:tx` nor by the Block 1.9c Playground checkpoint (see §2/§10); that is deferred
  to Block 1.10 or the block that introduces signing/finalization first.
- The fee produced in Block 1.9 is an estimate; Block 1.10 (signing) inherits the
  responsibility to finalize the fee against the real witness set and rebuild the body if the
  size differs.
- No signing, witness construction, submit, native assets, metadata, certificates, scripts,
  collateral, datums, reference inputs, or minting are introduced by this decision; each
  remains scoped to its own later block or phase.

## Non-goals

- No transaction signing, witness/signature construction, or witness set (beyond a size
  estimate for the fee).
- No full `transaction` array, no submit, no chain interaction from `:tx`.
- No native assets / multi-asset values, metadata, certificates, withdrawals, native or Plutus
  scripts, collateral, datums, reference inputs, minting, required signers, or network-id body
  field.
- No CBOR tag `258` set encoding; no post-Alonzo map output form; no advanced coin selection;
  no folding of dust change into the fee.
- No change to `:core`'s CBOR ordering rule or Phase 0 parser policy; no new deterministic mode
  added to `:core` in this block.
- No mainnet; no real mnemonics, private keys, or funds; no persistence.
- No claim of readiness, external review, or audit status.

## Follow-up work

- **Block 1.9b** implements this ADR: the `:tx` module, the transaction model, canonical
  `transaction_body` serialization, largest-first selection with the bounded fee/change
  fixed-point loop, `TxBuildError`, the structural/CDDL tests, and `:tx/README.md`.
- **Block 1.9c** wires `:tx` into the `:shared` Android Playground "Transaction Draft
  (unsigned)" checkpoint, displaying only the unsigned draft's structural summary
  (input/output counts, fee, change, body size, a truncated body-CBOR preview) with no
  transaction id or body hash — that display is deferred to Block 1.10 (or the block that
  introduces signing/finalization) per §2 — and the draft clearly labeled unsigned, not
  submitted, testnet-only.
- **Block 1.10** (Transaction Signing) introduces its own scoped signing decision, builds the
  witness set, and finalizes the fee against the real witnesses — updating the guardrail that
  currently disallows signing.
- **Before any block that adds a map with heterogeneous or multi-byte keys** (multiasset,
  withdrawals, or body fields with keys ≥ 24): resolve the RFC 7049 length-first ordering for
  those structures (extend `:core` with a length-first mode, or add a `:tx`-owned emitter),
  without weakening `:core`'s Phase 0 parser policy (§3).
- ADR-0001 (CBOR/parser policy), ADR-0002/0003 (module/package structure), ADR-0005 (Phase 1
  scope), ADR-0006 (provider boundary), and ADR-0013 (`:wallet`) remain the governing decisions
  this ADR aligns with; this ADR does not supersede them.
