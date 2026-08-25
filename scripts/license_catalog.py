"""Curated Gradle coordinate -> license/election catalog.

This is factual metadata review, not legal advice. Every entry below was
checked against the coordinate's own published POM `<licenses>` block (Maven
Central / Google Maven, or the local Gradle module cache mirroring the same
bytes) on 2026-08-24 unless noted. `election` is filled only when the POM
itself lists more than one `<license>` (a real disjunctive choice); it is
never filled for a single-license coordinate — a single-license MIT (or
other) coordinate has no "election" to make, and code in
`scripts/generate_legal_evidence.py` must not treat it as if it did (this is
the exact mistake the 2026-08-24 independent review flagged: a prior version
of NOTICE/LICENSES claimed no MIT-only distributed component existed, which
was false for `org.slf4j:slf4j-api`, and separately failed to record that the
`bytes` Rust crate, MIT-only, is linked into every committed native
artifact).

`license` uses the exact SPDX-style name string from the POM (not
normalized), so a reviewer can trace it back to the source. Coordinates are
matched by `group:artifact` (any version), unless a specific
`group:artifact:version` key is present, which takes precedence.

Any entry with more than one `licenses` value (a real disjunctive OR choice)
MUST also carry `election_status` (one of `"OPEN"`/`"ACCEPTED"`, matching
`scripts/check_release_evidence.py`'s `VALID_ELECTION_STATUSES`),
`election_reviewer`, and `election_review_date` -- the same
"no reviewer has actually accepted this yet" schema
`scripts/cargo_election_catalog.py` uses on the Cargo side, generated
dynamically (one row per multi-license coordinate, not a hand-maintained
count) into `docs/evidence/gradle_license_inventory.json`'s
`license_elections` section by
`scripts/generate_legal_evidence.py`'s `gradle_license_elections()`.
`election_status` only ever becomes `"ACCEPTED"` by a human editing this
file to also fill in `election_reviewer`/`election_review_date` (ISO 8601)
-- this script never sets it itself, and `release` mode fails while any
such row is not `"ACCEPTED"`. `net.java.dev.jna:jna` is currently the only
Gradle coordinate in this catalog with more than one license.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import license_catalog_harvested  # noqa: E402

# group:artifact (or group:artifact:version) -> catalog entry.
GRADLE_LICENSE_CATALOG: dict[str, dict[str, Any]] = {
    "org.jetbrains.kotlin": {
        "licenses": ["Apache-2.0"],
        "election": None,
        "source": "https://github.com/JetBrains/kotlin/blob/master/license/LICENSE.txt",
    },
    "org.jetbrains.kotlinx:kotlinx-coroutines-core": {
        "licenses": ["Apache-2.0"],
        "election": None,
        "source": "https://github.com/Kotlin/kotlinx.coroutines/blob/master/LICENSE.txt",
    },
    "org.jetbrains.kotlinx:kotlinx-coroutines-slf4j": {
        "licenses": ["Apache-2.0"],
        "election": None,
        "source": "https://github.com/Kotlin/kotlinx.coroutines/blob/master/LICENSE.txt",
        "note": "Bridges kotlinx.coroutines debug info to SLF4J; pulls org.slf4j:slf4j-api as a real runtime dependency.",
    },
    "org.jetbrains.kotlinx:kotlinx-serialization-core": {
        "licenses": ["Apache-2.0"],
        "election": None,
        "source": "https://github.com/Kotlin/kotlinx.serialization/blob/master/LICENSE.txt",
    },
    "org.jetbrains.kotlinx:atomicfu": {
        "licenses": ["Apache-2.0"],
        "election": None,
        "source": "https://github.com/Kotlin/kotlinx-atomicfu/blob/master/LICENSE.txt",
    },
    "io.ktor": {
        "licenses": ["Apache-2.0"],
        "election": None,
        "source": "https://github.com/ktorio/ktor/blob/main/LICENSE",
    },
    "androidx": {
        "licenses": ["Apache-2.0"],
        "election": None,
        "source": "https://android.googlesource.com/platform/frameworks/support/+/androidx-main/LICENSE.txt",
        "note": "Prefix match for the androidx.* group; individual androidx artifacts are not separately re-verified.",
    },
    "org.jetbrains.compose": {
        "licenses": ["Apache-2.0"],
        "election": None,
        "source": "https://github.com/JetBrains/compose-multiplatform/blob/master/LICENSE.txt",
        "note": "Prefix match for org.jetbrains.compose.*; Playground/Desktop UI only.",
    },
    "org.jetbrains.compose.hot-reload": {
        "licenses": ["Apache-2.0"],
        "election": None,
        "source": "https://github.com/JetBrains/compose-hot-reload/blob/master/LICENSE.txt",
        "note": "Dev-loop tooling only; classified build-tooling by scripts/generate_legal_evidence.py, never shipped.",
    },
    "org.jetbrains.skiko:skiko": {
        "licenses": ["Apache-2.0"],
        "election": None,
        "source": "https://github.com/JetBrains/skiko/blob/master/LICENSE",
    },
    "org.jetbrains.skiko:skiko-awt": {
        "licenses": ["Apache-2.0"],
        "election": None,
        "source": "https://github.com/JetBrains/skiko/blob/master/LICENSE",
    },
    "org.jetbrains.skiko:skiko-awt-runtime-macos-arm64": {
        "licenses": ["Apache-2.0"],
        "election": None,
        "source": "https://github.com/JetBrains/skiko/blob/master/LICENSE",
        "note": (
            "Native carrier: bundles compiled libskiko-macos-arm64.dylib and "
            "libskiko-macos-x64.dylib. See docs/evidence/maven_native_carriers_inventory.json."
        ),
    },
    "org.bouncycastle:bcprov-jdk18on": {
        "licenses": ["Bouncy Castle Licence"],
        "election": None,
        "source": "https://www.bouncycastle.org/licence.html",
        "note": "See LICENSES/BouncyCastle.txt and docs/LEGAL_REVIEW.md \u00a77 for the manual-transcription method.",
    },
    "org.kotlincrypto.hash:blake2": {
        "licenses": ["Apache-2.0"],
        "election": None,
        "source": "https://github.com/KotlinCrypto/hash/blob/master/LICENSE.txt",
    },
    "org.kotlincrypto.hash:sha2": {
        "licenses": ["Apache-2.0"],
        "election": None,
        "source": "https://github.com/KotlinCrypto/hash/blob/master/LICENSE.txt",
    },
    "org.hyperledger.identus:bip32-ed25519": {
        "licenses": ["Apache-2.0"],
        "election": None,
        "source": "https://github.com/hyperledger-identus/apollo/blob/main/LICENSE",
        "note": (
            "Android artifact is org.hyperledger.identus:bip32-ed25519-android; both share this "
            "election. See docs/LEGAL_REVIEW.md \u00a76b for the embedded-native MPL/Apache uncertainty."
        ),
    },
    "org.hyperledger.identus:bip32-ed25519-android": {
        "licenses": ["Apache-2.0"],
        "election": None,
        "source": "https://github.com/hyperledger-identus/apollo/blob/main/LICENSE",
        "note": (
            "Bundles compiled libuniffi_ed25519_bip32_wrapper.so per ABI. The POM declares "
            "Apache-2.0 for the wrapper; this repository has not obtained or reviewed that native "
            "library's own build-time dependency graph (e.g. whether it links an MPL-2.0 UniFFI "
            "runtime the way this repo's own crypto-signing-backend does). Treat the embedded "
            "native library's own license/notice obligations as an OPEN counsel determination, "
            "not as \"also Apache-2.0\" by inheritance from the wrapper POM."
        ),
    },
    "com.ionspin.kotlin:multiplatform-crypto-libsodium-bindings": {
        "licenses": ["Apache-2.0"],
        "election": None,
        "source": "https://github.com/ionspin/kotlin-multiplatform-libsodium/blob/main/LICENSE",
        "note": (
            "Prefix match for all multiplatform-crypto-libsodium-bindings* variants (jvm/ios*/"
            "metadata). The jvm variant bundles compiled libsodium binaries; see "
            "docs/evidence/maven_native_carriers_inventory.json."
        ),
    },
    "com.goterl:lazysodium-android": {
        "licenses": ["MPL-2.0"],
        "election": None,
        "source": "https://github.com/terl/lazysodium-android/blob/master/LICENSE.md",
        "note": "Bundles compiled libsodium.so per ABI. MPL-2.0 file-level obligation is OPEN (docs/LEGAL_REVIEW.md \u00a76).",
    },
    "net.java.dev.jna:jna": {
        "licenses": ["LGPL-2.1-or-later", "Apache-2.0"],
        "election": "Apache-2.0",
        "election_status": "OPEN",
        "election_reviewer": None,
        "election_review_date": None,
        "source": "https://github.com/java-native-access/jna/blob/master/LICENSE",
        "note": (
            "The POM lists LGPL-2.1-or-later first, Apache-2.0 second, both under "
            "<distribution>repo</distribution> as a real disjunctive choice (confirmed from the "
            "artifact's own POM, not assumed). Kardano SDK proposes electing Apache-2.0, but "
            "election_status is OPEN -- no reviewer has actually accepted this election yet (see "
            "docs/evidence/gradle_license_inventory.json 'license_elections' and "
            "docs/LEGAL_REVIEW.md \u00a75a). Ships a jar that itself bundles 27 platform-specific "
            "libjnidispatch native binaries; see docs/evidence/maven_native_carriers_inventory.json. "
            "Do not classify JNA as source-only: it is source-plus-embedded-native-carrier."
        ),
    },
    "org.slf4j:slf4j-api": {
        "licenses": ["MIT"],
        "election": None,
        "source": "https://www.slf4j.org/license.html",
        "note": (
            "MIT-only (no OR clause in the POM). This is the component a prior version of this "
            "evidence packet incorrectly implied did not exist; see LICENSES/MIT.txt."
        ),
    },
    "junit:junit": {
        "licenses": ["Eclipse Public License 1.0"],
        "election": None,
        "source": "https://junit.org/junit4/license.html",
        "note": "Test-only; never shipped.",
    },
    "org.junit": {
        "licenses": ["Eclipse Public License 2.0"],
        "election": None,
        "source": "https://www.eclipse.org/legal/epl-2.0/",
        "note": "Test-only (JUnit 5); never shipped.",
    },
    "org.hamcrest:hamcrest-core": {
        "licenses": ["BSD-3-Clause"],
        "election": None,
        "source": "https://github.com/hamcrest/JavaHamcrest/blob/master/LICENSE",
        "note": "Test-only; never shipped.",
    },
    "androidx.test": {
        "licenses": ["Apache-2.0"],
        "election": None,
        "source": "https://android.googlesource.com/platform/frameworks/support/+/androidx-main/LICENSE.txt",
        "note": "Test-only (androidx.test.*); never shipped.",
    },
    "com.google.guava:listenablefuture:1.0": {
        "licenses": ["The Apache Software License, Version 2.0"],
        "election": None,
        "source": (
            "https://repo1.maven.org/maven2/com/google/guava/guava-parent/"
            "26.0-android/guava-parent-26.0-android.pom"
        ),
        "note": (
            "listenablefuture-1.0.pom itself carries no <licenses> block; the "
            "license is declared only on its Maven parent POM "
            "(com.google.guava:guava-parent:26.0-android), confirmed by fetching "
            "that parent POM directly on 2026-08-24. This script's own POM "
            "parser does not implement Maven parent-POM inheritance generally -- "
            "this single coordinate is hand-resolved here for exactly that "
            "reason, not mechanically harvested like the rest of "
            "scripts/license_catalog_harvested.py."
        ),
    },
}


def lookup(group: str, artifact: str, version: str) -> dict[str, Any] | None:
    """Hand-curated entries always win over harvested ones for the same key.

    Only an exact `group:artifact:version` key is checked in the harvested
    catalog (it is a mechanical, single-license-only extraction with no
    group-prefix generalization -- see `scripts/license_catalog_harvested.py`
    and the harvest script's docstring for why).
    """
    for key in (f"{group}:{artifact}:{version}", f"{group}:{artifact}", group):
        if key in GRADLE_LICENSE_CATALOG:
            entry = dict(GRADLE_LICENSE_CATALOG[key])
            entry.setdefault("resolution_method", "curated-catalog")
            return entry
    exact_key = f"{group}:{artifact}:{version}"
    if exact_key in license_catalog_harvested.HARVESTED_POM_LICENSE_CATALOG:
        entry = license_catalog_harvested.HARVESTED_POM_LICENSE_CATALOG[exact_key]
        return {
            "licenses": entry["licenses"],
            "election": None,
            "source": entry.get("source"),
            "resolution_method": "harvested-pom-catalog",
        }
    return None
