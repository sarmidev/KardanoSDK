"""Coverage tests for scripts/generate_legal_evidence.py."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import generate_legal_evidence as evidence  # noqa: E402


class ConfigurationClassificationTests(unittest.TestCase):
    def test_test_only_configuration(self) -> None:
        self.assertEqual(evidence.classify_configuration("jvmTestRuntimeClasspath"), "test")
        self.assertEqual(
            evidence.classify_configuration("androidHostTestRuntimeClasspath"), "test"
        )

    def test_runtime_configuration(self) -> None:
        self.assertEqual(evidence.classify_configuration("jvmMainRuntimeClasspath"), "runtime")
        self.assertEqual(evidence.classify_configuration("androidRuntimeClasspath"), "runtime")

    def test_framework_export_is_runtime(self) -> None:
        self.assertEqual(evidence.classify_configuration("iosArm64ReleaseFrameworkExport"), "runtime")

    def test_source_configuration(self) -> None:
        self.assertEqual(evidence.classify_configuration("jvmMainCompileClasspath"), "source")
        self.assertEqual(
            evidence.classify_configuration("commonMainImplementationDependenciesMetadata"),
            "source",
        )

    def test_build_tooling_configuration(self) -> None:
        for name in (
            "kotlinCompilerClasspath",
            "androidMainLintChecksClasspath",
            "annotationProcessor",
            "composeHotReloadRuntime",
            "composeHotReloadDevRuntimeClasspath",
            "_internal-unified-test-platform-core",
        ):
            self.assertEqual(evidence.classify_configuration(name), "build-tooling")

    def test_classify_gav_prefers_runtime_over_source(self) -> None:
        bucket = evidence.classify_gav(["jvmMainCompileClasspath", "jvmMainRuntimeClasspath"])
        self.assertEqual(bucket, "runtime")

    def test_classify_gav_all_test_is_test_only(self) -> None:
        bucket = evidence.classify_gav(["jvmTestCompileClasspath", "jvmTestRuntimeClasspath"])
        self.assertEqual(bucket, "test")

    def test_classify_gav_all_tooling_is_build_tooling(self) -> None:
        bucket = evidence.classify_gav(["kotlinCompilerClasspath", "annotationProcessor"])
        self.assertEqual(bucket, "build-tooling")


class LockfileParsingTests(unittest.TestCase):
    def test_empty_marker_line_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lockfile = Path(tmp) / "gradle.lockfile"
            lockfile.write_text(
                "# comment\n"
                "empty=androidApis,lintPublish\n"
                "com.example:foo:1.0=jvmMainRuntimeClasspath\n",
                encoding="utf-8",
            )
            entries = evidence.parse_lockfile(lockfile)
            self.assertEqual(entries, [("com.example:foo:1.0", ["jvmMainRuntimeClasspath"])])

    def test_duplicate_coordinate_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lockfile = Path(tmp) / "gradle.lockfile"
            lockfile.write_text(
                "com.example:foo:1.0=jvmMainRuntimeClasspath\n"
                "com.example:foo:1.0=jvmTestRuntimeClasspath\n",
                encoding="utf-8",
            )
            with self.assertRaises(evidence.EvidenceError):
                evidence.parse_lockfile(lockfile)

    def test_duplicate_configuration_name_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lockfile = Path(tmp) / "gradle.lockfile"
            lockfile.write_text(
                "com.example:foo:1.0=jvmMainRuntimeClasspath,jvmMainRuntimeClasspath\n",
                encoding="utf-8",
            )
            with self.assertRaises(evidence.EvidenceError):
                evidence.parse_lockfile(lockfile)

    def test_malformed_line_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lockfile = Path(tmp) / "gradle.lockfile"
            lockfile.write_text("this line has no equals sign\n", encoding="utf-8")
            with self.assertRaises(evidence.EvidenceError):
                evidence.parse_lockfile(lockfile)

    def test_crlf_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lockfile = Path(tmp) / "gradle.lockfile"
            lockfile.write_bytes(b"com.example:foo:1.0=jvmMainRuntimeClasspath\r\n")
            with self.assertRaises(evidence.EvidenceError):
                evidence.parse_lockfile(lockfile)

    def test_symlink_lockfile_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real.lockfile"
            real.write_text("com.example:foo:1.0=jvmMainRuntimeClasspath\n", encoding="utf-8")
            link = Path(tmp) / "gradle.lockfile"
            os.symlink(real, link)
            with self.assertRaises(evidence.EvidenceError):
                evidence.parse_lockfile(link)


class ChecksumsParsingTests(unittest.TestCase):
    def test_parse_checksums_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            checksums = Path(tmp) / "CHECKSUMS.sha256"
            checksums.write_text(
                ("a" * 64) + "  src/a/b.so\n" + ("b" * 64) + "  src/c/d.a\n",
                encoding="utf-8",
            )
            rows = evidence.parse_checksums(checksums)
            self.assertEqual(rows, {"src/a/b.so": "a" * 64, "src/c/d.a": "b" * 64})

    def test_malformed_line_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            checksums = Path(tmp) / "CHECKSUMS.sha256"
            checksums.write_text("not-a-valid-line\n", encoding="utf-8")
            with self.assertRaises(evidence.EvidenceError):
                evidence.parse_checksums(checksums)

    def test_uppercase_hex_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            checksums = Path(tmp) / "CHECKSUMS.sha256"
            checksums.write_text(("A" * 64) + "  src/a/b.so\n", encoding="utf-8")
            with self.assertRaises(evidence.EvidenceError):
                evidence.parse_checksums(checksums)

    def test_duplicate_path_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            checksums = Path(tmp) / "CHECKSUMS.sha256"
            checksums.write_text(
                ("a" * 64) + "  src/a/b.so\n" + ("b" * 64) + "  src/a/b.so\n",
                encoding="utf-8",
            )
            with self.assertRaises(evidence.EvidenceError):
                evidence.parse_checksums(checksums)

    def test_crlf_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            checksums = Path(tmp) / "CHECKSUMS.sha256"
            checksums.write_bytes((("a" * 64) + "  src/a/b.so\r\n").encode("utf-8"))
            with self.assertRaises(evidence.EvidenceError):
                evidence.parse_checksums(checksums)

    def test_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real.sha256"
            real.write_text(("a" * 64) + "  src/a/b.so\n", encoding="utf-8")
            link = Path(tmp) / "CHECKSUMS.sha256"
            os.symlink(real, link)
            with self.assertRaises(evidence.EvidenceError):
                evidence.parse_checksums(link)


class GradleModuleDiscoveryTests(unittest.TestCase):
    def test_discovers_modules_from_settings_gradle_kts(self) -> None:
        modules = evidence.discover_gradle_modules()
        self.assertIn("core", modules)
        self.assertIn("crypto-signing-backend", modules)
        self.assertEqual(modules, tuple(sorted(modules)))

    def test_missing_lockfile_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / "settings.gradle.kts"
            settings.write_text('include(":nonexistent-module")\n', encoding="utf-8")
            original = evidence.SETTINGS_GRADLE
            original_repo_root = evidence.REPO_ROOT
            evidence.SETTINGS_GRADLE = settings
            evidence.REPO_ROOT = Path(tmp)
            try:
                with self.assertRaises(evidence.EvidenceError):
                    evidence.discover_gradle_modules()
            finally:
                evidence.SETTINGS_GRADLE = original
                evidence.REPO_ROOT = original_repo_root


class CargoPurePackageClassificationTests(unittest.TestCase):
    """Synthetic-metadata tests for the pure classify_cargo_packages logic."""

    @staticmethod
    def _pkg(pkg_id: str, name: str, version: str, kind: str = "lib") -> dict:
        return {
            "id": pkg_id,
            "name": name,
            "version": version,
            "license": "MIT",
            "source": "registry+https://example.invalid",
            "targets": [{"kind": [kind]}],
        }

    @staticmethod
    def _node(pkg_id: str, deps: list[tuple[str, str | None]]) -> dict:
        return {
            "id": pkg_id,
            "deps": [
                {"pkg": dep_id, "dep_kinds": [{"kind": kind, "target": None}]}
                for dep_id, kind in deps
            ],
        }

    def test_conditional_target_dep_excluded_when_not_in_real_normal(self) -> None:
        # root -> normal -> windows_only (present in metadata's `deps` edge,
        # but NOT part of the real, feature/target-activation-correct set
        # for THIS target -- simulating a cfg(windows)-only dependency on a
        # non-Windows triple).
        metadata = {
            "packages": [
                self._pkg("root", "root", "0.1.0"),
                self._pkg("windows_only", "windows_only", "1.0.0"),
            ],
            "resolve": {
                "root": "root",
                "nodes": [
                    self._node("root", [("windows_only", None)]),
                    self._node("windows_only", []),
                ],
            },
        }
        real_normal = {"root"}  # windows_only excluded: not real for this target
        result = evidence.classify_cargo_packages(metadata, real_normal, real_normal)
        self.assertNotIn("windows_only", result["linked_into_compiled_artifact"])
        self.assertEqual(result["linked_into_compiled_artifact"], [])

    def test_proc_macro_and_its_support_closure_excluded(self) -> None:
        # root -> normal -> my_macro (proc-macro) -> normal -> syn_like
        metadata = {
            "packages": [
                self._pkg("root", "root", "0.1.0"),
                self._pkg("my_macro", "my_macro", "1.0.0", kind="proc-macro"),
                self._pkg("syn_like", "syn_like", "1.0.0"),
            ],
            "resolve": {
                "root": "root",
                "nodes": [
                    self._node("root", [("my_macro", None)]),
                    self._node("my_macro", [("syn_like", None)]),
                    self._node("syn_like", []),
                ],
            },
        }
        real_normal = {"root", "my_macro", "syn_like"}
        result = evidence.classify_cargo_packages(metadata, real_normal, real_normal)
        self.assertNotIn("my_macro", result["linked_into_compiled_artifact"])
        self.assertNotIn("syn_like", result["linked_into_compiled_artifact"])
        self.assertIn("my_macro", result["proc_macro_and_support_closure"])
        self.assertIn("syn_like", result["proc_macro_and_support_closure"])

    def test_dependency_linked_via_normal_and_via_proc_macro_stays_linked(self) -> None:
        # A package reachable BOTH directly (normal, non-proc-macro path) AND
        # through a proc-macro's dependency edge must remain linked -- being
        # also-reachable-via-proc-macro must not "poison" a genuinely linked
        # package (this is the exact shape of `bytes` via uniffi_core, which
        # is not itself behind any proc-macro).
        metadata = {
            "packages": [
                self._pkg("root", "root", "0.1.0"),
                self._pkg("my_macro", "my_macro", "1.0.0", kind="proc-macro"),
                self._pkg("shared_dep", "shared_dep", "1.0.0"),
            ],
            "resolve": {
                "root": "root",
                "nodes": [
                    self._node("root", [("my_macro", None), ("shared_dep", None)]),
                    self._node("my_macro", [("shared_dep", None)]),
                    self._node("shared_dep", []),
                ],
            },
        }
        real_normal = {"root", "my_macro", "shared_dep"}
        result = evidence.classify_cargo_packages(metadata, real_normal, real_normal)
        self.assertIn("shared_dep", result["linked_into_compiled_artifact"])

    def test_host_build_dependency_only(self) -> None:
        metadata = {
            "packages": [
                self._pkg("root", "root", "0.1.0"),
                self._pkg("autocfg_like", "autocfg_like", "1.0.0"),
            ],
            "resolve": {
                "root": "root",
                "nodes": [
                    self._node("root", []),
                    self._node("autocfg_like", []),
                ],
            },
        }
        real_normal = {"root"}
        real_normal_and_build = {"root", "autocfg_like"}
        result = evidence.classify_cargo_packages(metadata, real_normal, real_normal_and_build)
        self.assertEqual(result["host_build_dependency_only"], ["autocfg_like"])
        self.assertNotIn("autocfg_like", result["linked_into_compiled_artifact"])

    def test_dev_dependency_only_reported_when_supplied(self) -> None:
        metadata = {
            "packages": [
                self._pkg("root", "root", "0.1.0"),
                self._pkg("test_helper", "test_helper", "1.0.0"),
            ],
            "resolve": {
                "root": "root",
                "nodes": [self._node("root", []), self._node("test_helper", [])],
            },
        }
        result = evidence.classify_cargo_packages(
            metadata, {"root"}, {"root"}, dev_only={"test_helper"}
        )
        self.assertEqual(result["dev_dependency_only"], ["test_helper"])

    def test_duplicate_name_version_across_sources_raises(self) -> None:
        metadata = {
            "packages": [
                {
                    "id": "registry+a#foo@1.0.0",
                    "name": "foo",
                    "version": "1.0.0",
                    "license": "MIT",
                    "source": "registry+a",
                    "targets": [],
                },
                {
                    "id": "registry+b#foo@1.0.0",
                    "name": "foo",
                    "version": "1.0.0",
                    "license": "MIT",
                    "source": "registry+b",
                    "targets": [],
                },
            ],
        }
        index = evidence.name_version_index(metadata)
        with self.assertRaises(evidence.EvidenceError):
            evidence.require_unambiguous_name_versions(index, "test-triple")


class GradleLicenseCatalogTests(unittest.TestCase):
    def test_single_license_has_no_election(self) -> None:
        entry = evidence.license_catalog.lookup("org.slf4j", "slf4j-api", "2.0.18")
        self.assertIsNotNone(entry)
        self.assertIsNone(entry["election"])
        self.assertEqual(entry["licenses"], ["MIT"])

    def test_dual_license_has_election(self) -> None:
        entry = evidence.license_catalog.lookup("net.java.dev.jna", "jna", "5.19.1")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["election"], "Apache-2.0")
        self.assertEqual(len(entry["licenses"]), 2)


class RealTreeGenerationTests(unittest.TestCase):
    """Exercise the generators against the real repository tree."""

    def setUp(self) -> None:
        self.modules = evidence.discover_gradle_modules()

    def test_gradle_inventory_has_no_unclassified_coordinates(self) -> None:
        report = evidence.gradle_dependency_inventory(self.modules)
        for module, data in report["modules"].items():
            self.assertEqual(
                data["counts"].get("other", 0),
                0,
                f"module {module} has unclassified ('other') coordinates: "
                f"{data['coordinates']['other']}",
            )

    def test_native_artifact_catalog_matches_checksums_exactly(self) -> None:
        report = evidence.native_artifacts_inventory()
        self.assertEqual(report["artifact_count"], 9)

    def test_cargo_inventory_covers_all_nine_target_triples(self) -> None:
        report = evidence.cargo_dependency_inventory_per_target()
        self.assertEqual(len(report["target_triples"]), 9)
        self.assertGreater(report["package_count"], 0)
        for triple in report["target_triples"]:
            membership = report["membership_by_target"][triple]
            self.assertIn("linked_into_compiled_artifact", membership)
            self.assertIn("proc_macro_and_support_closure", membership)
            self.assertIn("host_build_dependency_only", membership)
            self.assertIn("dev_dependency_only", membership)

    def test_cargo_inventory_finds_known_mit_only_linked_packages(self) -> None:
        report = evidence.cargo_dependency_inventory_per_target()
        self.assertIn("bytes@1.12.1", report["mit_only_linked_packages"])

    def test_cargo_inventory_excludes_unicode_ident_from_linked_set(self) -> None:
        report = evidence.cargo_dependency_inventory_per_target()
        for pkg in report["packages"]:
            if pkg["name"] == "unicode-ident":
                self.assertFalse(pkg["linked_in_any_target"])
                return
        self.fail("unicode-ident not found in cargo dependency inventory")

    def test_maven_native_carriers_have_valid_distribution_status(self) -> None:
        report = evidence.maven_native_carriers_inventory()
        for carrier in report["carriers"]:
            self.assertIn(
                carrier["distribution_status"], evidence.VALID_CARRIER_DISTRIBUTION_STATUSES
            )

    def test_jna_carrier_has_34_embedded_natives_with_full_fields(self) -> None:
        # 27 in the main .jar (com/sun/jna/...) plus 7 in the separate
        # Android .aar Gradle Module Metadata variant of this same
        # coordinate (jni/<abi>/libjnidispatch.so) -- see additional_artifacts.
        report = evidence.maven_native_carriers_inventory()
        jna = next(
            c for c in report["carriers"] if c["maven_coordinate"].startswith("net.java.dev.jna")
        )
        self.assertEqual(len(jna["embedded_natives"]), 34)
        self.assertEqual(jna["embedded_native_count"], 34)
        jar_members = [m for m in jna["embedded_natives"] if m["path"].startswith("com/sun/jna/")]
        aar_members = [m for m in jna["embedded_natives"] if m["path"].startswith("jni/")]
        self.assertEqual(len(jar_members), 27)
        self.assertEqual(len(aar_members), 7)
        self.assertEqual(len(jna["additional_artifacts"]), 1)
        self.assertEqual(jna["additional_artifacts"][0]["kind"], "aar")
        for member in jna["embedded_natives"]:
            for field in ("path", "size_bytes", "sha256", "platform", "arch"):
                self.assertIn(field, member)
                self.assertTrue(member[field])

    def test_skiko_carrier_is_not_marked_redistributed(self) -> None:
        report = evidence.maven_native_carriers_inventory()
        skiko = next(c for c in report["carriers"] if "skiko" in c["maven_coordinate"])
        self.assertEqual(skiko["distribution_status"], "not_in_first_release_scope")

    def test_uniffi_bindings_inventory_lists_discovered_files(self) -> None:
        report = evidence.uniffi_bindings_inventory()
        self.assertEqual(
            report["generated_file_count"], len(evidence.discover_uniffi_generated_files())
        )
        self.assertGreater(report["generated_file_count"], 0)

    def test_gradle_license_inventory_reports_mit_only_coordinates(self) -> None:
        gradle_report = evidence.gradle_dependency_inventory(self.modules)
        report = evidence.gradle_license_inventory(gradle_report)
        self.assertTrue(
            any(gav.startswith("org.slf4j:slf4j-api:") for gav in report["mit_only_coordinates"])
        )

    def test_gradle_license_inventory_has_zero_unresolved(self) -> None:
        gradle_report = evidence.gradle_dependency_inventory(self.modules)
        report = evidence.gradle_license_inventory(gradle_report)
        self.assertEqual(report["unresolved_count"], 0)
        self.assertEqual(report["unresolved"], [])

    def test_generation_is_deterministic_across_two_runs(self) -> None:
        gradle_report = evidence.gradle_dependency_inventory(self.modules)
        first = json.dumps(gradle_report, sort_keys=True)
        second = json.dumps(evidence.gradle_dependency_inventory(self.modules), sort_keys=True)
        self.assertEqual(first, second)

        first_cargo = json.dumps(evidence.cargo_dependency_inventory_per_target(), sort_keys=True)
        second_cargo = json.dumps(
            evidence.cargo_dependency_inventory_per_target(), sort_keys=True
        )
        self.assertEqual(first_cargo, second_cargo)

    def test_no_generated_json_contains_repo_absolute_path(self) -> None:
        absolute_marker = str(REPO_ROOT)
        gradle_report = evidence.gradle_dependency_inventory(self.modules)
        for report in (
            gradle_report,
            evidence.gradle_license_inventory(gradle_report),
            evidence.cargo_dependency_inventory_per_target(),
            evidence.uniffi_bindings_inventory(),
            evidence.native_artifacts_inventory(),
            evidence.maven_native_carriers_inventory(),
            evidence.bouncycastle_license_source_inventory(),
        ):
            text = json.dumps(report)
            self.assertNotIn(absolute_marker, text)
            self.assertNotIn(str(Path.home()), text)


class SpdxExpressionParsingTests(unittest.TestCase):
    def test_single_license_is_not_an_election(self) -> None:
        self.assertTrue(evidence.is_single_license_expression("MIT"))
        self.assertTrue(evidence.is_single_license_expression("Apache-2.0"))

    def test_or_expression_needs_election(self) -> None:
        self.assertFalse(evidence.is_single_license_expression("MIT OR Apache-2.0"))
        components = evidence.parse_spdx_expression("MIT OR Apache-2.0")
        self.assertEqual(components, [{"type": "or", "options": ["MIT", "Apache-2.0"]}])

    def test_legacy_slash_syntax_is_an_or_election(self) -> None:
        self.assertFalse(evidence.is_single_license_expression("MIT/Apache-2.0"))
        components = evidence.parse_spdx_expression("MIT/Apache-2.0")
        self.assertEqual(components, [{"type": "or", "options": ["MIT", "Apache-2.0"]}])

    def test_and_component_with_or_election(self) -> None:
        components = evidence.parse_spdx_expression("(MIT OR Apache-2.0) AND Unicode-3.0")
        self.assertEqual(
            components,
            [
                {"type": "or", "options": ["MIT", "Apache-2.0"]},
                {"type": "single", "value": "Unicode-3.0"},
            ],
        )
        self.assertFalse(evidence.is_single_license_expression("(MIT OR Apache-2.0) AND Unicode-3.0"))

    def test_with_exception_stays_attached_to_its_option(self) -> None:
        components = evidence.parse_spdx_expression(
            "Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT"
        )
        self.assertEqual(len(components), 1)
        self.assertEqual(
            components[0]["options"],
            ["Apache-2.0 WITH LLVM-exception", "Apache-2.0", "MIT"],
        )

    def test_empty_expression_raises(self) -> None:
        with self.assertRaises(evidence.EvidenceError):
            evidence.parse_spdx_expression("")
        with self.assertRaises(evidence.EvidenceError):
            evidence.parse_spdx_expression(None)  # type: ignore[arg-type]

    def test_unbalanced_parens_raise(self) -> None:
        with self.assertRaises(evidence.EvidenceError):
            evidence.parse_spdx_expression("(MIT OR Apache-2.0 AND Unicode-3.0")


class CargoLicenseElectionTests(unittest.TestCase):
    def _pkg(self, name: str, version: str, license_expr: str | None, linked: bool) -> dict:
        return {
            "name": name,
            "version": version,
            "license": license_expr,
            "linked_in_any_target": linked,
            "membership": {"x86_64-unknown-linux-gnu": ["linked_into_compiled_artifact"]}
            if linked
            else {},
        }

    def test_single_license_package_produces_no_row(self) -> None:
        packages = [self._pkg("bytes", "1.12.1", "MIT", True)]
        report = evidence.cargo_license_elections(packages)
        self.assertEqual(report["rows"], [])
        self.assertEqual(report["mandatory_row_count"], 0)

    def test_known_dual_license_linked_package_uses_catalog_row(self) -> None:
        packages = [self._pkg("anyhow", "1.0.103", "MIT OR Apache-2.0", True)]
        report = evidence.cargo_license_elections(packages)
        self.assertEqual(len(report["rows"]), 1)
        row = report["rows"][0]
        self.assertEqual(row["status"], "OPEN")
        self.assertEqual(row["proposed_election"], "Apache-2.0")
        self.assertEqual(row["or_election_options"], ["MIT", "Apache-2.0"])

    def test_unknown_linked_package_with_or_expression_raises(self) -> None:
        packages = [self._pkg("brand-new-crate", "0.1.0", "MIT OR Apache-2.0", True)]
        with self.assertRaises(evidence.EvidenceError):
            evidence.cargo_license_elections(packages)

    def test_unknown_non_linked_package_gets_not_applicable_row(self) -> None:
        packages = [self._pkg("brand-new-build-tool", "0.1.0", "MIT OR Apache-2.0", False)]
        report = evidence.cargo_license_elections(packages)
        self.assertEqual(len(report["rows"]), 1)
        self.assertEqual(report["rows"][0]["status"], "NOT_APPLICABLE")
        self.assertEqual(report["mandatory_row_count"], 0)

    def test_and_component_stays_mandatory_regardless_of_or_election(self) -> None:
        packages = [
            self._pkg("unicode-ident", "1.0.24", "(MIT OR Apache-2.0) AND Unicode-3.0", False)
        ]
        report = evidence.cargo_license_elections(packages)
        row = report["rows"][0]
        self.assertEqual(row["and_required_components"], ["Unicode-3.0"])
        self.assertEqual(row["or_election_options"], ["MIT", "Apache-2.0"])

    def test_missing_license_expression_still_gets_a_row_when_linked(self) -> None:
        packages = [self._pkg("mystery-crate", "0.0.1", None, True)]
        with self.assertRaises(evidence.EvidenceError):
            evidence.cargo_license_elections(packages)

    def test_all_mandatory_elections_accepted_is_false_while_any_open(self) -> None:
        report = evidence.cargo_dependency_inventory_per_target()
        elections = report["license_elections"]
        self.assertGreater(elections["mandatory_row_count"], 0)
        self.assertFalse(elections["all_mandatory_elections_accepted"])
        for row in elections["rows"]:
            if row["linked_in_any_target"]:
                self.assertEqual(row["status"], "OPEN")

    def test_memchr_has_no_proposed_election(self) -> None:
        report = evidence.cargo_dependency_inventory_per_target()
        for row in report["license_elections"]["rows"]:
            if row["name"] == "memchr":
                self.assertIsNone(row["proposed_election"])
                return
        self.fail("memchr not found in license_elections rows")

    def test_real_tree_has_no_duplicate_election_rows(self) -> None:
        report = evidence.cargo_dependency_inventory_per_target()
        keys = [
            (r["name"], r["version"]) for r in report["license_elections"]["rows"]
        ]
        self.assertEqual(len(keys), len(set(keys)))


class NativeCarrierValidationTests(unittest.TestCase):
    def _base_carrier(self, **overrides) -> dict:
        carrier = {
            "maven_coordinate": "com.example:fake:1.0",
            "carrier_kind": "JVM .jar",
            "license": "MIT",
            "distribution_status": "redistributed_by_kardano",
            "distributed_by_kardano": True,
            "windows_native_available_upstream": False,
            "inspected_2026_08_24": True,
            "artifact_sha256": "0" * 64,
            "primary_artifact_kind": "jar",
            "embedded_natives": [
                {
                    "path": "libfake.so",
                    "size_bytes": 1,
                    "sha256": "0" * 64,
                    "platform": "Linux",
                    "arch": "x86-64",
                }
            ],
            "note": None,
        }
        carrier.update(overrides)
        return carrier

    def test_invalid_distribution_status_raises(self) -> None:
        carriers = (self._base_carrier(distribution_status="totally_shipped"),)
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", carriers):
            with self.assertRaises(evidence.EvidenceError):
                evidence.maven_native_carriers_inventory()

    def test_missing_member_field_raises(self) -> None:
        carrier = self._base_carrier()
        del carrier["embedded_natives"][0]["sha256"]
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError):
                evidence.maven_native_carriers_inventory()

    def test_embedded_native_count_mismatch_raises(self) -> None:
        carrier = self._base_carrier(embedded_native_count=99)
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError):
                evidence.maven_native_carriers_inventory()

    def test_valid_carrier_passes(self) -> None:
        carrier = self._base_carrier(embedded_native_count=1)
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            report = evidence.maven_native_carriers_inventory()
        self.assertEqual(len(report["carriers"]), 1)


import struct as _struct  # noqa: E402


def _build_fat_macho(magic: bytes, bits: int, endian: str, arches: list[dict]) -> bytes:
    """Build a structurally-valid fat/universal Mach-O fixture for one of
    the four magic variants, with real, boundedly-consistent arch entries
    (no overlap, all contained, header-adjacent-or-later offsets)."""
    entry_size = 20 if bits == 32 else 32
    header_end = 8 + len(arches) * entry_size
    fmt = (">" if endian == "big" else "<") + ("iiIII" if bits == 32 else "iiQQII")
    header = magic + len(arches).to_bytes(4, endian)
    entries = b""
    for arch in arches:
        if bits == 32:
            entries += _struct.pack(
                fmt, arch["cputype"], arch.get("cpusubtype", 0), arch["offset"], arch["size"], arch.get("align", 0)
            )
        else:
            entries += _struct.pack(
                fmt,
                arch["cputype"],
                arch.get("cpusubtype", 0),
                arch["offset"],
                arch["size"],
                arch.get("align", 0),
                0,
            )
    total_len = max(header_end, max(a["offset"] + a["size"] for a in arches))
    buf = bytearray(total_len)
    buf[: len(header) + len(entries)] = header + entries
    for i, arch in enumerate(arches):
        buf[arch["offset"] : arch["offset"] + arch["size"]] = bytes([0xAB]) * arch["size"]
    return bytes(buf)


def _one_arch_fat_macho(magic: bytes, bits: int, endian: str, cputype: int) -> bytes:
    entry_size = 20 if bits == 32 else 32
    header_end = 8 + entry_size
    return _build_fat_macho(
        magic, bits, endian, [{"cputype": cputype, "offset": header_end, "size": 16, "align": 4}]
    )


def _build_pe(
    machine: int = 0x8664,
    num_sections: int = 1,
    size_optional_header: int = 224,
    e_lfanew: int = 64,
    signature: bytes = b"PE\x00\x00",
    truncate_to: int | None = None,
) -> bytes:
    """Build a structurally-valid (unless deliberately perturbed) minimal
    PE/COFF fixture: full 64-byte DOS header, exact `e_lfanew`, `"PE\\0\\0"`,
    a 20-byte COFF header, and a section table sized from `num_sections`.
    """
    dos = b"MZ" + b"\x00" * 58 + e_lfanew.to_bytes(4, "little")
    padding = b"\x00" * max(0, e_lfanew - len(dos))
    coff = _struct.pack("<HHIIIHH", machine, num_sections, 0, 0, 0, size_optional_header, 0)
    optional = b"\x00" * size_optional_header
    sections = b"\x00" * (num_sections * 40)
    data = dos + padding + signature + coff + optional + sections
    if truncate_to is not None:
        data = data[:truncate_to]
    return data


def _build_java_class(
    major_version: int = 52,
    minor_version: int = 0,
    class_name: str = "Foo",
    with_field: bool = False,
    with_method: bool = False,
    with_attribute: bool = False,
    trailing_bytes: bytes = b"",
) -> bytes:
    """Build a minimal, structurally-valid Java `.class` file (JVMS §4):
    magic/version, a small constant pool (a Utf8 class name, a Utf8
    "V"/"()V" descriptor, a Class this_class, and -- if requested -- a
    Utf8 attribute name), `this_class` referencing the Class entry,
    `super_class=0`, zero interfaces, and an optional single trivial
    field/method/attribute (each with zero attributes/body bytes of
    their own) to exercise those code paths. `trailing_bytes` appended
    after an otherwise-complete, valid class file simulates extra data
    past the exact expected EOF.
    """
    name_bytes = class_name.encode("utf-8")

    def utf8_entry(text: bytes) -> bytes:
        return bytes([1]) + len(text).to_bytes(2, "big") + text

    cp_entries = [utf8_entry(name_bytes)]  # index 1: class name
    cp_entries.append(bytes([7]) + (1).to_bytes(2, "big"))  # index 2: Class -> name_index=1
    descriptor_index = None
    attr_name_index = None
    if with_field or with_method:
        cp_entries.append(utf8_entry(b"()V" if with_method else b"I"))  # index 3
        descriptor_index = 3
        cp_entries.append(utf8_entry(b"x"))  # index 4: member name
        member_name_index = 4
    if with_attribute:
        cp_entries.append(utf8_entry(b"Deprecated"))
        attr_name_index = len(cp_entries)

    constant_pool_count = len(cp_entries) + 1
    body = b"".join(cp_entries)
    body += (0).to_bytes(2, "big")  # access_flags
    body += (2).to_bytes(2, "big")  # this_class = 2
    body += (0).to_bytes(2, "big")  # super_class = 0
    body += (0).to_bytes(2, "big")  # interfaces_count

    def member_table(present: bool) -> bytes:
        if not present:
            return (0).to_bytes(2, "big")
        return (
            (1).to_bytes(2, "big")  # count = 1
            + (0).to_bytes(2, "big")  # access_flags
            + member_name_index.to_bytes(2, "big")  # name_index
            + descriptor_index.to_bytes(2, "big")  # descriptor_index
            + (0).to_bytes(2, "big")  # attributes_count = 0
        )

    body += member_table(with_field)
    body += member_table(with_method)
    if with_attribute:
        body += (1).to_bytes(2, "big")  # attributes_count = 1
        body += attr_name_index.to_bytes(2, "big")
        body += (0).to_bytes(4, "big")  # attribute_length = 0
    else:
        body += (0).to_bytes(2, "big")  # attributes_count = 0

    return (
        b"\xca\xfe\xba\xbe"
        + minor_version.to_bytes(2, "big")
        + major_version.to_bytes(2, "big")
        + constant_pool_count.to_bytes(2, "big")
        + body
        + trailing_bytes
    )


def _u1(n: int) -> bytes:
    return bytes([n])


def _u2(n: int) -> bytes:
    return n.to_bytes(2, "big")


def _u4(n: int) -> bytes:
    return n.to_bytes(4, "big")


def _cp_entry(tag: int, body: bytes) -> bytes:
    return _u1(tag) + body


def _utf8_entry(text: bytes) -> bytes:
    return _cp_entry(evidence.JAVA_CP_TAG_UTF8, _u2(len(text)) + text)


def _class_entry(name_index: int) -> bytes:
    return _cp_entry(evidence.JAVA_CP_TAG_CLASS, _u2(name_index))


def _string_entry(string_index: int) -> bytes:
    return _cp_entry(evidence.JAVA_CP_TAG_STRING, _u2(string_index))


def _integer_entry(value: int = 0) -> bytes:
    return _cp_entry(evidence.JAVA_CP_TAG_INTEGER, _u4(value & 0xFFFFFFFF))


def _long_entry() -> bytes:
    return _cp_entry(evidence.JAVA_CP_TAG_LONG, b"\x00" * 8)


def _double_entry() -> bytes:
    return _cp_entry(evidence.JAVA_CP_TAG_DOUBLE, b"\x00" * 8)


def _fieldref_entry(class_index: int, name_and_type_index: int) -> bytes:
    return _cp_entry(evidence.JAVA_CP_TAG_FIELDREF, _u2(class_index) + _u2(name_and_type_index))


def _methodref_entry(class_index: int, name_and_type_index: int) -> bytes:
    return _cp_entry(evidence.JAVA_CP_TAG_METHODREF, _u2(class_index) + _u2(name_and_type_index))


def _interface_methodref_entry(class_index: int, name_and_type_index: int) -> bytes:
    return _cp_entry(evidence.JAVA_CP_TAG_INTERFACE_METHODREF, _u2(class_index) + _u2(name_and_type_index))


def _name_and_type_entry(name_index: int, descriptor_index: int) -> bytes:
    return _cp_entry(evidence.JAVA_CP_TAG_NAME_AND_TYPE, _u2(name_index) + _u2(descriptor_index))


def _method_handle_entry(reference_kind: int, reference_index: int) -> bytes:
    return _cp_entry(evidence.JAVA_CP_TAG_METHOD_HANDLE, _u1(reference_kind) + _u2(reference_index))


def _method_type_entry(descriptor_index: int) -> bytes:
    return _cp_entry(evidence.JAVA_CP_TAG_METHOD_TYPE, _u2(descriptor_index))


def _dynamic_entry(bootstrap_method_attr_index: int, name_and_type_index: int) -> bytes:
    return _cp_entry(evidence.JAVA_CP_TAG_DYNAMIC, _u2(bootstrap_method_attr_index) + _u2(name_and_type_index))


def _invoke_dynamic_entry(bootstrap_method_attr_index: int, name_and_type_index: int) -> bytes:
    return _cp_entry(
        evidence.JAVA_CP_TAG_INVOKE_DYNAMIC, _u2(bootstrap_method_attr_index) + _u2(name_and_type_index)
    )


def _module_entry(name_index: int) -> bytes:
    return _cp_entry(evidence.JAVA_CP_TAG_MODULE, _u2(name_index))


def _package_entry(name_index: int) -> bytes:
    return _cp_entry(evidence.JAVA_CP_TAG_PACKAGE, _u2(name_index))


def _build_java_class_from_cp(
    cp_entries: list[bytes],
    major_version: int = 52,
    minor_version: int = 0,
    this_class: int = 1,
    super_class: int = 0,
    interfaces: tuple[int, ...] = (),
    fields: bytes | None = None,
    methods: bytes | None = None,
    attributes: bytes | None = None,
    constant_pool_count: int | None = None,
    trailing_bytes: bytes = b"",
) -> bytes:
    """Build a Java `.class` file from an explicit, caller-controlled list
    of already-encoded constant-pool entries (see the `_*_entry` helpers
    above) -- used only to exercise the constant-pool cross-reference
    validator (`_validate_java_cp_references`) directly, with full
    control over indices, tags, and `major_version`, rather than the
    fixed shape `_build_java_class` produces. `constant_pool_count` is
    computed automatically from `cp_entries` (accounting for the
    Long/Double double-slot rule) unless overridden.
    """
    if constant_pool_count is None:
        count = 1
        for entry in cp_entries:
            count += 2 if entry[0] in evidence.JAVA_CP_DOUBLE_SLOT_TAGS else 1
        constant_pool_count = count
    body = b"".join(cp_entries)
    body += _u2(0)  # access_flags
    body += _u2(this_class)
    body += _u2(super_class)
    body += _u2(len(interfaces))
    for interface_index in interfaces:
        body += _u2(interface_index)
    body += fields if fields is not None else _u2(0)
    body += methods if methods is not None else _u2(0)
    body += attributes if attributes is not None else _u2(0)
    return (
        b"\xca\xfe\xba\xbe"
        + _u2(minor_version)
        + _u2(major_version)
        + _u2(constant_pool_count)
        + body
        + trailing_bytes
    )


def _build_xcoff(bits: int, nscns: int = 1, opthdr: int = 0, truncate_to: int | None = None) -> bytes:
    """Build a structurally-valid (unless deliberately perturbed) minimal
    XCOFF32/XCOFF64 fixture."""
    if bits == 32:
        header = (
            b"\x01\xdf" + nscns.to_bytes(2, "big") + b"\x00" * 4 + b"\x00" * 4 + b"\x00" * 4
            + opthdr.to_bytes(2, "big") + b"\x00" * 2
        )
        scnhdr_size = 40
    else:
        header = (
            b"\x01\xf7" + nscns.to_bytes(2, "big") + b"\x00" * 4 + b"\x00" * 8
            + opthdr.to_bytes(2, "big") + b"\x00" * 2 + b"\x00" * 4
        )
        scnhdr_size = 72
    data = header + b"\x00" * opthdr + b"\x00" * (nscns * scnhdr_size)
    if truncate_to is not None:
        data = data[:truncate_to]
    return data


class NativeMemberDetectionTests(unittest.TestCase):
    """`classify_native_member_signal()` -- Gap 4 (original round) plus the
    2026-08-24 final round's structural-validation requirement: fat
    Mach-O/PE/XCOFF magic bytes alone are never sufficient, every one of
    those three formats gets a full bounded structural parse, and a
    magic-prefixed member that fails that parse is a hard
    `"malformed_native_magic"` failure (never silently `"not_native"`),
    except the one documented Java `.class` collision.
    """

    ELF = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8
    MACHO_THIN_64 = b"\xcf\xfa\xed\xfe\x0c\x00\x00\x01" + b"\x00" * 8
    MACHO_THIN_32 = b"\xce\xfa\xed\xfe\x07\x00\x00\x00" + b"\x00" * 8
    AR = b"!<arch>\n" + b"fake-object-bytes"

    X86_64 = 0x01000007
    ARM64 = 0x0100000C

    PE = staticmethod(_build_pe)
    XCOFF32 = _build_xcoff(32)
    XCOFF64 = _build_xcoff(64)
    # Fat/universal Mach-O with a plausible nfat_arch (2), real allowlisted
    # cputypes, and non-overlapping contained slices -- empirically matches
    # the real IonSpin libsodium universal .dylib's shape (arm64+x86-64).
    FAT_MACHO = _build_fat_macho(
        b"\xca\xfe\xba\xbe",
        32,
        "big",
        [
            {"cputype": X86_64, "offset": 48, "size": 32, "align": 4},
            {"cputype": ARM64, "offset": 80, "size": 32, "align": 4},
        ],
    )
    # Genuine, structurally-valid Java .class file: CAFEBABE + a real
    # (if minimal) constant pool/this_class/super_class/interfaces/
    # fields/methods/attributes -- not just a plausible-looking magic +
    # version prefix. A 2026-08-24 review found the prior version of
    # this fixture (bare magic + version + zero padding, no real class
    # structure at all) let ANY CAFEBABE-prefixed payload under ANY
    # filename fall back to `not_native` purely because it failed the
    # fat-Mach-O parse -- see `_validate_java_class_structure` and
    # `_classify_by_magic` for the fix: the fallback now also requires
    # this exact structural proof.
    JAVA_CLASS = _build_java_class()
    # Bare magic + version + zero padding -- LOOKS like it could be a
    # class file (major_version=0x34=52 is plausible) but has no real
    # constant pool/class structure at all. This is exactly the
    # collision-payload shape a malicious/broken renamed fat-Mach-O
    # could exploit if the fallback trusted magic+extension alone.
    MALFORMED_CAFEBABE_PADDING = b"\xca\xfe\xba\xbe\x00\x00\x00\x34" + b"\x00" * 8

    def test_known_extension_with_matching_magic_is_native(self) -> None:
        self.assertEqual(evidence.classify_native_member_signal("libfoo.so", self.ELF), "native")
        self.assertEqual(evidence.classify_native_member_signal("jni/x86/libfoo.so", self.ELF), "native")
        self.assertEqual(evidence.classify_native_member_signal("foo.dylib", self.MACHO_THIN_64), "native")
        self.assertEqual(evidence.classify_native_member_signal("foo.dll", _build_pe()), "native")
        self.assertEqual(evidence.classify_native_member_signal("foo.jnilib", self.MACHO_THIN_32), "native")
        self.assertEqual(evidence.classify_native_member_signal("foo.a", self.AR), "native")
        # AIX XCOFF object masquerading as a `.a` -- real shape of JNA's
        # com/sun/jna/aix-ppc*/libjnidispatch.a, NOT a "!<arch>\n" archive.
        self.assertEqual(evidence.classify_native_member_signal("foo.a", self.XCOFF32), "native")
        self.assertEqual(evidence.classify_native_member_signal("foo.a", self.XCOFF64), "native")
        self.assertEqual(evidence.classify_native_member_signal("foo.dylib", self.FAT_MACHO), "native")

    def test_known_extension_with_non_matching_magic_is_a_mismatch(self) -> None:
        # A .so/.dll/.dylib/.jnilib/.a whose content does not look like ANY
        # supported native format at all must fail closed -- never guess
        # either "native" or "not native" for a claimed-but-unverified
        # native extension.
        for ext in evidence.NATIVE_MEMBER_EXTENSIONS:
            with self.subTest(ext=ext):
                self.assertEqual(
                    evidence.classify_native_member_signal(
                        f"foo{ext}", b"plain text, not native at all"
                    ),
                    "extension_magic_mismatch",
                )

    def test_java_class_file_cafebabe_magic_is_not_native(self) -> None:
        # Regression test: a Java .class file's own magic number (CAFEBABE)
        # is byte-identical to a Mach-O universal/fat binary's magic number.
        # A real bug this generator was found to have: scanning
        # androidx.annotation:annotation-jvm (a pure-Kotlin/Java artifact,
        # zero native code) reported 75 ".class" members as "native".
        self.assertEqual(
            evidence.classify_native_member_signal(
                "androidx/annotation/NonNull.class", self.JAVA_CLASS
            ),
            "not_native",
        )

    def test_ordinary_resource_near_misses_are_not_native(self) -> None:
        self.assertEqual(evidence.classify_native_member_signal("README", b"just text here"), "not_native")
        self.assertEqual(
            evidence.classify_native_member_signal("icon.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 8),
            "not_native",
        )
        self.assertEqual(evidence.classify_native_member_signal("module-info.class", self.JAVA_CLASS), "not_native")

    def test_extensionless_member_with_native_magic_is_native(self) -> None:
        self.assertEqual(evidence.classify_native_member_signal("payload", self.ELF), "native")
        self.assertEqual(evidence.classify_native_member_signal("payload", _build_pe()), "native")
        self.assertEqual(evidence.classify_native_member_signal("payload", self.AR), "native")

    def test_extensionless_member_without_native_magic_is_not_native(self) -> None:
        self.assertEqual(evidence.classify_native_member_signal("README", b"just text here"), "not_native")

    def test_renamed_elf_with_misleading_extension_is_native(self) -> None:
        for name in ("payload.bin", "payload.dat", "payload.txt", "payload.class"):
            with self.subTest(name=name):
                self.assertEqual(evidence.classify_native_member_signal(name, self.ELF), "native")

    def test_renamed_pe_with_misleading_extension_is_native(self) -> None:
        self.assertEqual(evidence.classify_native_member_signal("payload.dat", _build_pe()), "native")

    def test_renamed_thin_macho_with_misleading_extension_is_native(self) -> None:
        self.assertEqual(evidence.classify_native_member_signal("payload.dat", self.MACHO_THIN_64), "native")

    def test_renamed_fat_macho_with_misleading_extension_is_native(self) -> None:
        self.assertEqual(evidence.classify_native_member_signal("payload.dat", self.FAT_MACHO), "native")

    def test_renamed_ar_with_misleading_extension_is_native(self) -> None:
        self.assertEqual(evidence.classify_native_member_signal("payload.dat", self.AR), "native")

    def test_renamed_xcoff_with_misleading_extension_is_native(self) -> None:
        self.assertEqual(evidence.classify_native_member_signal("payload.dat", self.XCOFF32), "native")
        self.assertEqual(evidence.classify_native_member_signal("payload.dat", self.XCOFF64), "native")

    def test_fat_macho_arch_count_outside_plausible_range_under_non_class_name_is_malformed(self) -> None:
        # 0x63 = 99: far above MAX_PLAUSIBLE_FAT_MACHO_ARCH_COUNT. This is
        # the exact High finding this test now guards against: a
        # non-`.class`-named member must NEVER receive the Java-class
        # collision fallback merely because it failed the fat-Mach-O
        # parse -- it must fail generation instead.
        implausible = b"\xca\xfe\xba\xbe\x00\x00\x00\x63" + b"\x00" * 8
        self.assertEqual(
            evidence.classify_native_member_signal("payload", implausible), "malformed_native_magic"
        )
        self.assertEqual(
            evidence.classify_native_member_signal("payload.bin", implausible), "malformed_native_magic"
        )

    def test_fat_macho_arch_count_outside_plausible_range_under_class_name_but_invalid_structure_is_malformed(
        self,
    ) -> None:
        # Even with the exact `.class` name, bare magic+version+padding
        # (no real constant pool/class structure) must still fail --
        # the fallback requires INDEPENDENT structural proof of a valid
        # Java class file, not just the right extension.
        self.assertEqual(
            evidence.classify_native_member_signal("Foo.class", self.MALFORMED_CAFEBABE_PADDING),
            "malformed_native_magic",
        )

    def test_truncated_magic_prefix_is_not_native(self) -> None:
        self.assertEqual(evidence.classify_native_member_signal("payload", b"\xca\xfe"), "not_native")
        self.assertEqual(evidence.classify_native_member_signal("payload.so", b"\x7f"), "extension_magic_mismatch")

    # -- Gap 1 (2026-08-24 final round): all four fat-Mach-O magic variants,
    # full structural validation, renamed-member coverage, and every
    # documented malformed shape. --------------------------------------

    FAT_MACHO_VARIANTS = (
        (b"\xca\xfe\xba\xbe", 32, "big"),  # FAT_MAGIC
        (b"\xbe\xba\xfe\xca", 32, "little"),  # FAT_CIGAM
        (b"\xca\xfe\xba\xbf", 64, "big"),  # FAT_MAGIC_64
        (b"\xbf\xba\xfe\xca", 64, "little"),  # FAT_CIGAM_64
    )

    def test_all_four_fat_macho_magic_variants_with_valid_structure_are_native(self) -> None:
        for magic, bits, endian in self.FAT_MACHO_VARIANTS:
            with self.subTest(magic=magic.hex(), bits=bits, endian=endian):
                data = _one_arch_fat_macho(magic, bits, endian, self.X86_64)
                self.assertEqual(evidence.classify_native_member_signal("libfoo.dylib", data), "native")
                # Renamed/extensionless -- must still be discovered by magic.
                self.assertEqual(evidence.classify_native_member_signal("payload.dat", data), "native")
                self.assertEqual(evidence.classify_native_member_signal("payload", data), "native")

    def test_all_four_fat_macho_variants_with_two_non_overlapping_arches_are_native(self) -> None:
        for magic, bits, endian in self.FAT_MACHO_VARIANTS:
            with self.subTest(magic=magic.hex(), bits=bits, endian=endian):
                entry_size = 20 if bits == 32 else 32
                header_end = 8 + 2 * entry_size
                data = _build_fat_macho(
                    magic,
                    bits,
                    endian,
                    [
                        {"cputype": self.X86_64, "offset": header_end, "size": 16, "align": 4},
                        {"cputype": self.ARM64, "offset": header_end + 16, "size": 16, "align": 4},
                    ],
                )
                self.assertEqual(evidence.classify_native_member_signal("payload.dylib", data), "native")

    def test_fat_macho_truncated_header_is_malformed(self) -> None:
        # Real magic, but not even the 8-byte header (magic + nfat_arch)
        # fits -- never a fallback to `not_native` except the exact
        # CAFEBABE/Java-class collision magic, which is tested separately.
        for magic, _bits, _endian in self.FAT_MACHO_VARIANTS[1:]:
            with self.subTest(magic=magic.hex()):
                self.assertEqual(
                    evidence.classify_native_member_signal("payload", magic + b"\x00\x00\x00"),
                    "malformed_native_magic",
                )

    def test_fat_macho_zero_arch_count_is_malformed(self) -> None:
        # None of these fixtures is `.class`-named or a valid Java class
        # payload, so ALL four magic variants -- including the
        # CAFEBABE/Java-class-colliding one -- must fail generation, not
        # fall back to `not_native`.
        for magic, bits, endian in self.FAT_MACHO_VARIANTS:
            with self.subTest(magic=magic.hex()):
                data = magic + (0).to_bytes(4, endian) + b"\x00" * 16
                self.assertEqual(
                    evidence.classify_native_member_signal("payload", data), "malformed_native_magic"
                )

    def test_fat_macho_excess_arch_count_is_malformed(self) -> None:
        for magic, bits, endian in self.FAT_MACHO_VARIANTS:
            with self.subTest(magic=magic.hex()):
                data = magic + (99).to_bytes(4, endian) + b"\x00" * 16
                self.assertEqual(
                    evidence.classify_native_member_signal("payload", data), "malformed_native_magic"
                )

    def test_fat_macho_arch_table_extends_past_available_data_is_malformed(self) -> None:
        # nfat_arch claims 2 entries, but only enough bytes for the header
        # itself (never for the caller to actually trust the count without
        # verifying containment).
        for magic, bits, endian in self.FAT_MACHO_VARIANTS:
            with self.subTest(magic=magic.hex()):
                data = magic + (2).to_bytes(4, endian) + b"\x00" * 4
                self.assertEqual(
                    evidence.classify_native_member_signal("payload", data), "malformed_native_magic"
                )

    def _expected_signal_for_malformed_fat_macho(self, magic: bytes) -> str:
        # No fixture in this group is `.class`-named with a genuinely
        # valid Java class payload, so every fat-Mach-O magic variant --
        # including the CAFEBABE/Java-class-colliding one -- has no
        # legitimate innocent explanation here and must fail generation
        # outright (see `JAVA_CLASS_COLLISION_FAT_MACHO_MAGIC` and
        # `_classify_by_magic` for when the narrow fallback DOES apply).
        del magic  # kept for call-site symmetry/documentation; always malformed here
        return "malformed_native_magic"

    def test_fat_macho_arch_offset_size_out_of_bounds_is_malformed(self) -> None:
        for magic, bits, endian in self.FAT_MACHO_VARIANTS:
            with self.subTest(magic=magic.hex()):
                entry_size = 20 if bits == 32 else 32
                header_end = 8 + entry_size
                # Claims a slice that extends past what is actually
                # present: build a valid-looking fixture, then truncate the
                # payload region itself out from under the claimed size.
                data = _build_fat_macho(magic, bits, endian, [{"cputype": self.X86_64, "offset": header_end, "size": 16}])
                data = data[:-1]
                self.assertEqual(
                    evidence.classify_native_member_signal("payload", data),
                    self._expected_signal_for_malformed_fat_macho(magic),
                )

    def test_fat_macho_arch_offset_overlaps_header_table_is_malformed(self) -> None:
        for magic, bits, endian in self.FAT_MACHO_VARIANTS:
            with self.subTest(magic=magic.hex()):
                # offset=0 overlaps the fat header/arch-table region itself.
                entry_size = 20 if bits == 32 else 32
                fmt = (">" if endian == "big" else "<") + ("iiIII" if bits == 32 else "iiQQII")
                header = magic + (1).to_bytes(4, endian)
                if bits == 32:
                    entry = _struct.pack(fmt, self.X86_64, 0, 0, 16, 4)
                else:
                    entry = _struct.pack(fmt, self.X86_64, 0, 0, 16, 4, 0)
                data = header + entry + b"\x00" * 32
                self.assertEqual(
                    evidence.classify_native_member_signal("payload", data),
                    self._expected_signal_for_malformed_fat_macho(magic),
                )

    def test_fat_macho_overlapping_arch_slices_is_malformed(self) -> None:
        for magic, bits, endian in self.FAT_MACHO_VARIANTS:
            with self.subTest(magic=magic.hex()):
                entry_size = 20 if bits == 32 else 32
                header_end = 8 + 2 * entry_size
                data = _build_fat_macho(
                    magic,
                    bits,
                    endian,
                    [
                        {"cputype": self.X86_64, "offset": header_end, "size": 32},
                        # Second slice starts before the first one ends.
                        {"cputype": self.ARM64, "offset": header_end + 16, "size": 16},
                    ],
                )
                self.assertEqual(
                    evidence.classify_native_member_signal("payload", data),
                    self._expected_signal_for_malformed_fat_macho(magic),
                )

    def test_fat_macho_implausible_cputype_is_malformed(self) -> None:
        data = _one_arch_fat_macho(b"\xca\xfe\xba\xbf", 64, "big", cputype=0x7FFFFFFF)
        self.assertEqual(evidence.classify_native_member_signal("payload", data), "malformed_native_magic")

    def test_fat_macho_implausible_align_is_malformed(self) -> None:
        # FAT_MAGIC_64 has no Java-class collision, so an implausible
        # `align` field must fail generation outright.
        entry_size = 32
        header_end = 8 + entry_size
        data = _build_fat_macho(
            b"\xca\xfe\xba\xbf", 64, "big", [{"cputype": self.X86_64, "offset": header_end, "size": 16, "align": 999}]
        )
        self.assertEqual(evidence.classify_native_member_signal("payload", data), "malformed_native_magic")

    def test_fat_macho_wrong_endian_field_encoding_is_malformed(self) -> None:
        # FAT_MAGIC (the exact Java-`.class`-colliding, 32-bit big-endian
        # variant) with `nfat_arch` encoded little-endian instead of the
        # big-endian its own magic implies produces an implausible count.
        # Under a non-`.class` name, this must fail generation outright --
        # never silently accepted as `"native"` OR absorbed as
        # `"not_native"`.
        colliding = b"\xca\xfe\xba\xbe" + (2).to_bytes(4, "little") + b"\x00" * 16
        self.assertEqual(
            evidence.classify_native_member_signal("payload", colliding), "malformed_native_magic"
        )
        # FAT_MAGIC_64 (no legitimate collision at all) with the same
        # mistake must fail generation outright too.
        non_colliding = b"\xca\xfe\xba\xbf" + (2).to_bytes(4, "little") + b"\x00" * 32
        self.assertEqual(
            evidence.classify_native_member_signal("payload", non_colliding), "malformed_native_magic"
        )

    # -- Gap 4 (2026-08-24 final round): structural PE validation. -------

    def test_pe_minimal_valid_fixture_is_native(self) -> None:
        self.assertEqual(evidence.classify_native_member_signal("foo.dll", _build_pe()), "native")

    def test_pe_multi_section_valid_fixture_is_native(self) -> None:
        self.assertEqual(
            evidence.classify_native_member_signal("foo.dll", _build_pe(num_sections=5)), "native"
        )

    def test_pe_ordinary_text_beginning_mz_is_malformed_not_native(self) -> None:
        # Ordinary text that happens to start with "MZ" must not be
        # silently accepted as native, and must not be silently dropped as
        # not_native either -- it is a malformed claim.
        self.assertEqual(
            evidence.classify_native_member_signal("readme.txt", b"MZ some ordinary text, not a PE file at all"),
            "malformed_native_magic",
        )

    def test_pe_truncated_dos_header_is_malformed(self) -> None:
        self.assertEqual(evidence.classify_native_member_signal("foo.dll", b"MZ\x00\x00"), "malformed_native_magic")

    def test_pe_e_lfanew_before_dos_header_end_is_malformed(self) -> None:
        data = _build_pe(e_lfanew=10)
        self.assertEqual(evidence.classify_native_member_signal("foo.dll", data), "malformed_native_magic")

    def test_pe_e_lfanew_points_outside_member_is_malformed(self) -> None:
        # A huge claimed e_lfanew with no actual data behind it (never
        # pad/allocate to match an untrusted offset -- the checked bound
        # must fail before any such read).
        e_lfanew = 10_000_000
        dos = b"MZ" + b"\x00" * 58 + e_lfanew.to_bytes(4, "little")
        self.assertEqual(evidence.classify_native_member_signal("foo.dll", dos), "malformed_native_magic")

    def test_pe_wrong_signature_is_malformed(self) -> None:
        data = _build_pe(signature=b"XX\x00\x00")
        self.assertEqual(evidence.classify_native_member_signal("foo.dll", data), "malformed_native_magic")

    def test_pe_truncated_after_signature_is_malformed(self) -> None:
        data = _build_pe(truncate_to=68)
        self.assertEqual(evidence.classify_native_member_signal("foo.dll", data), "malformed_native_magic")

    def test_pe_implausible_machine_is_malformed(self) -> None:
        data = _build_pe(machine=0xDEAD)
        self.assertEqual(evidence.classify_native_member_signal("foo.dll", data), "malformed_native_magic")

    def test_pe_zero_sections_is_malformed(self) -> None:
        data = _build_pe(num_sections=0)
        self.assertEqual(evidence.classify_native_member_signal("foo.dll", data), "malformed_native_magic")

    def test_pe_section_count_overflow_is_malformed(self) -> None:
        # Claims far more sections than MAX_PLAUSIBLE_PE_SECTION_COUNT, with
        # no matching bytes -- must not be trusted.
        dos = b"MZ" + b"\x00" * 58 + (64).to_bytes(4, "little")
        coff = _struct.pack("<HHIIIHH", 0x8664, 5000, 0, 0, 0, 224, 0)
        data = dos + b"PE\x00\x00" + coff + b"\x00" * 224
        self.assertEqual(evidence.classify_native_member_signal("foo.dll", data), "malformed_native_magic")

    def test_pe_optional_header_size_overflow_is_malformed(self) -> None:
        # 60000 exceeds MAX_PLAUSIBLE_PE_OPTIONAL_HEADER_SIZE (512) but
        # still fits the field's own 16-bit width.
        data = _build_pe(size_optional_header=60_000)
        self.assertEqual(evidence.classify_native_member_signal("foo.dll", data), "malformed_native_magic")

    def test_pe_section_table_extends_past_available_data_is_malformed(self) -> None:
        data = _build_pe(num_sections=3)
        self.assertEqual(evidence.classify_native_member_signal("foo.dll", data[:-10]), "malformed_native_magic")

    def test_pe_renamed_with_misleading_extension_is_native(self) -> None:
        self.assertEqual(evidence.classify_native_member_signal("payload.dat", _build_pe()), "native")
        self.assertEqual(evidence.classify_native_member_signal("payload", _build_pe()), "native")

    # -- Gap 4 (2026-08-24 final round): structural XCOFF validation. ----

    def test_xcoff_minimal_valid_fixtures_are_native(self) -> None:
        self.assertEqual(evidence.classify_native_member_signal("libfoo.a", _build_xcoff(32)), "native")
        self.assertEqual(evidence.classify_native_member_signal("libfoo.a", _build_xcoff(64)), "native")

    def test_xcoff_short_prefix_ordinary_data_is_malformed_not_native(self) -> None:
        # Only the 2-byte magic, no room for even the minimum file header.
        self.assertEqual(
            evidence.classify_native_member_signal("payload", b"\x01\xdf" + b"ordinary short data"[:4]),
            "malformed_native_magic",
        )
        self.assertEqual(
            evidence.classify_native_member_signal("payload", b"\x01\xf7\x00\x01"),
            "malformed_native_magic",
        )

    def test_xcoff_truncated_file_header_is_malformed(self) -> None:
        self.assertEqual(
            evidence.classify_native_member_signal("libfoo.a", _build_xcoff(32, truncate_to=10)),
            "malformed_native_magic",
        )
        self.assertEqual(
            evidence.classify_native_member_signal("libfoo.a", _build_xcoff(64, truncate_to=10)),
            "malformed_native_magic",
        )

    def test_xcoff_zero_section_count_is_malformed(self) -> None:
        self.assertEqual(
            evidence.classify_native_member_signal("libfoo.a", _build_xcoff(32, nscns=0)),
            "malformed_native_magic",
        )

    def test_xcoff_section_count_overflow_is_malformed(self) -> None:
        # Claims far more sections than MAX_PLAUSIBLE_XCOFF_SECTION_COUNT,
        # with no matching bytes -- must not be trusted.
        header = b"\x01\xdf" + (5000).to_bytes(2, "big") + b"\x00" * 14
        self.assertEqual(evidence.classify_native_member_signal("libfoo.a", header), "malformed_native_magic")

    def test_xcoff_optional_header_size_overflow_is_malformed(self) -> None:
        header = b"\x01\xdf" + (1).to_bytes(2, "big") + b"\x00" * 10 + (50_000).to_bytes(2, "big") + b"\x00" * 2
        self.assertEqual(evidence.classify_native_member_signal("libfoo.a", header), "malformed_native_magic")

    def test_xcoff_section_table_extends_past_available_data_is_malformed(self) -> None:
        data = _build_xcoff(32, nscns=2)
        self.assertEqual(evidence.classify_native_member_signal("libfoo.a", data[:-5]), "malformed_native_magic")

    def test_xcoff_renamed_with_misleading_extension_is_native(self) -> None:
        self.assertEqual(evidence.classify_native_member_signal("payload.dat", _build_xcoff(32)), "native")
        self.assertEqual(evidence.classify_native_member_signal("payload", _build_xcoff(64)), "native")

    def test_valid_fat_macho_renamed_dot_class_is_still_native(self) -> None:
        # The fat-Mach-O structural parse is always attempted FIRST,
        # before any Java-class fallback consideration -- a genuinely
        # valid fat Mach-O keeps being classified `"native"` no matter
        # what its member name is, including a `.class` name that would
        # otherwise be eligible for the Java-class fallback.
        for magic, bits, endian in self.FAT_MACHO_VARIANTS:
            with self.subTest(magic=magic.hex()):
                data = _one_arch_fat_macho(magic, bits, endian, self.X86_64)
                self.assertEqual(evidence.classify_native_member_signal("payload.class", data), "native")
        self.assertEqual(evidence.classify_native_member_signal("libfoo.class", self.FAT_MACHO), "native")

    def test_zero_byte_payload_under_dot_bin_and_dot_class_is_not_native(self) -> None:
        # An empty member has no magic at all -- correctly `not_native`
        # under any name, never confused with a malformed CAFEBABE claim.
        self.assertEqual(evidence.classify_native_member_signal("payload.bin", b""), "not_native")
        self.assertEqual(evidence.classify_native_member_signal("Foo.class", b""), "not_native")

    def test_zero_length_cafebabe_prefixed_payload_under_dot_bin_and_dot_class_is_malformed(self) -> None:
        # Exactly the 4-byte magic and nothing else -- too short for even
        # the fat-Mach-O header, and (for `.class`) also too short for
        # even the Java class file's own minor/major version fields.
        # Neither name may fall back to `not_native`.
        magic_only = evidence.JAVA_CLASS_COLLISION_FAT_MACHO_MAGIC
        self.assertEqual(evidence.classify_native_member_signal("payload.bin", magic_only), "malformed_native_magic")
        self.assertEqual(evidence.classify_native_member_signal("Foo.class", magic_only), "malformed_native_magic")

    def test_truncated_fat_macho_payload_under_dot_bin_and_dot_class_is_malformed(self) -> None:
        # A real fat-Mach-O header (plausible nfat_arch=1) truncated right
        # after the header, before the arch entry itself -- fails the fat
        # parse, and is not a valid Java class file either.
        truncated = b"\xca\xfe\xba\xbe" + (1).to_bytes(4, "big") + b"\x00" * 4
        self.assertEqual(evidence.classify_native_member_signal("payload.bin", truncated), "malformed_native_magic")
        self.assertEqual(evidence.classify_native_member_signal("Foo.class", truncated), "malformed_native_magic")


class JavaClassStructuralValidationTests(unittest.TestCase):
    """`_validate_java_class_structure()` / the CAFEBABE Java-class
    collision fallback in `_classify_by_magic()` -- final 2026-08-24 High
    finding: the fallback must require BOTH an exact-case `.class` member
    name AND independent bounded structural proof of a genuine Java class
    file, never magic+extension alone, and never magic+ANY filename.
    """

    def test_minimal_valid_class_is_structurally_valid(self) -> None:
        self.assertTrue(evidence._validate_java_class_structure(_build_java_class()))

    def test_minimal_valid_class_with_field_method_and_attribute_is_valid(self) -> None:
        self.assertTrue(evidence._validate_java_class_structure(_build_java_class(with_field=True)))
        self.assertTrue(evidence._validate_java_class_structure(_build_java_class(with_method=True)))
        self.assertTrue(evidence._validate_java_class_structure(_build_java_class(with_attribute=True)))
        self.assertTrue(
            evidence._validate_java_class_structure(
                _build_java_class(with_field=True, with_method=True, with_attribute=True)
            )
        )

    def test_wrong_magic_is_invalid(self) -> None:
        self.assertFalse(evidence._validate_java_class_structure(b"\x00\x00\x00\x00" + b"\x00" * 20))

    def test_implausible_major_version_is_invalid(self) -> None:
        for major in (0, 44, 101, 65535):
            with self.subTest(major=major):
                data = bytearray(_build_java_class())
                data[6:8] = major.to_bytes(2, "big")
                self.assertFalse(evidence._validate_java_class_structure(bytes(data)))

    def test_plausible_major_version_boundaries_are_valid(self) -> None:
        for major in (45, 52, 61, 100):
            with self.subTest(major=major):
                data = bytearray(_build_java_class())
                data[6:8] = major.to_bytes(2, "big")
                self.assertTrue(evidence._validate_java_class_structure(bytes(data)))

    def test_zero_constant_pool_count_is_invalid(self) -> None:
        data = bytearray(_build_java_class())
        data[8:10] = (0).to_bytes(2, "big")
        self.assertFalse(evidence._validate_java_class_structure(bytes(data)))

    def test_unknown_constant_pool_tag_is_invalid(self) -> None:
        data = bytearray(_build_java_class())
        # Byte 10 is the first constant pool entry's tag (a Utf8, tag=1).
        # 0xFF (255) is not a JVMS Table 4.4-A tag.
        data[10] = 0xFF
        self.assertFalse(evidence._validate_java_class_structure(bytes(data)))

    def test_utf8_length_extending_past_payload_is_invalid(self) -> None:
        data = bytearray(_build_java_class())
        # Bytes 11:13 are the first Utf8 entry's u2 length field.
        data[11:13] = (60000).to_bytes(2, "big")
        self.assertFalse(evidence._validate_java_class_structure(bytes(data)))

    def test_fixed_body_size_entry_truncated_is_invalid(self) -> None:
        # A Class entry (tag=7, 2-byte body) with only 1 body byte
        # present before the payload ends.
        data = _build_java_class()
        # Locate the Class entry's tag byte (index 2 in the constant
        # pool, right after the "Foo" Utf8 entry: 1(tag)+2(len)+3("Foo")=6
        # bytes, so the Class tag is at absolute offset 10+6=16).
        class_tag_offset = 16
        self.assertEqual(data[class_tag_offset], 7)
        truncated = data[: class_tag_offset + 2]  # tag + 1 of 2 body bytes
        self.assertFalse(evidence._validate_java_class_structure(truncated))

    def test_double_slot_long_entry_is_valid_and_advances_index_by_two(self) -> None:
        # Hand-built constant pool: index 1 = Long (tag=5, 8-byte body,
        # occupies indices 1 AND 2), index 3 = Class -> name_index=4,
        # index 4 = Utf8 "Foo". this_class=3. constant_pool_count=5
        # (highest real index 4, +1).
        cp = bytes([5]) + b"\x00" * 8  # index 1 (Long; index 2 is its phantom slot)
        cp += bytes([7]) + (4).to_bytes(2, "big")  # index 3: Class -> name_index=4
        cp += bytes([1]) + (3).to_bytes(2, "big") + b"Foo"  # index 4: Utf8 "Foo"
        data = (
            b"\xca\xfe\xba\xbe"
            + (0).to_bytes(2, "big")
            + (52).to_bytes(2, "big")
            + (5).to_bytes(2, "big")  # constant_pool_count
            + cp
            + (0).to_bytes(2, "big")  # access_flags
            + (3).to_bytes(2, "big")  # this_class = 3
            + (0).to_bytes(2, "big")  # super_class = 0
            + (0).to_bytes(2, "big")  # interfaces_count
            + (0).to_bytes(2, "big")  # fields_count
            + (0).to_bytes(2, "big")  # methods_count
            + (0).to_bytes(2, "big")  # attributes_count
        )
        self.assertTrue(evidence._validate_java_class_structure(data))

    def test_reference_to_double_slot_phantom_index_is_invalid(self) -> None:
        # Same layout as above, but this_class wrongly points at index 2
        # -- the Long entry's phantom/unusable second slot -- which must
        # never be treated as a valid Class entry.
        cp = bytes([5]) + b"\x00" * 8  # index 1 (Long); index 2 is its phantom slot
        cp += bytes([7]) + (4).to_bytes(2, "big")  # index 3: Class
        cp += bytes([1]) + (3).to_bytes(2, "big") + b"Foo"  # index 4: Utf8
        data = (
            b"\xca\xfe\xba\xbe"
            + (0).to_bytes(2, "big")
            + (52).to_bytes(2, "big")
            + (5).to_bytes(2, "big")
            + cp
            + (0).to_bytes(2, "big")  # access_flags
            + (2).to_bytes(2, "big")  # this_class = 2 (the phantom slot!)
            + (0).to_bytes(2, "big")
            + (0).to_bytes(2, "big")
            + (0).to_bytes(2, "big")
            + (0).to_bytes(2, "big")
            + (0).to_bytes(2, "big")
        )
        self.assertFalse(evidence._validate_java_class_structure(data))

    def test_invalid_this_class_index_is_invalid(self) -> None:
        data = bytearray(_build_java_class())
        # this_class is at offset 10 + len(constant pool bytes) + 2
        # (access_flags). For the default fixture: Utf8("Foo") = 6 bytes,
        # Class = 3 bytes -> cp ends at 10+9=19; access_flags at 19:21;
        # this_class at 21:23.
        self.assertEqual(int.from_bytes(data[21:23], "big"), 2)
        data[21:23] = (1).to_bytes(2, "big")  # index 1 is the Utf8, not a Class
        self.assertFalse(evidence._validate_java_class_structure(bytes(data)))

    def test_invalid_super_class_index_is_invalid(self) -> None:
        data = bytearray(_build_java_class())
        # super_class is at offset 23:25 for the default fixture.
        self.assertEqual(int.from_bytes(data[23:25], "big"), 0)
        data[23:25] = (1).to_bytes(2, "big")  # index 1 is the Utf8, not a Class
        self.assertFalse(evidence._validate_java_class_structure(bytes(data)))

    def test_invalid_interface_index_is_invalid(self) -> None:
        data = bytearray(_build_java_class())
        # interfaces_count is at offset 25:27; splice in one bogus entry.
        self.assertEqual(int.from_bytes(data[25:27], "big"), 0)
        patched = bytes(data[:25]) + (1).to_bytes(2, "big") + (99).to_bytes(2, "big") + bytes(data[27:])
        self.assertFalse(evidence._validate_java_class_structure(patched))

    def test_field_with_invalid_name_index_is_invalid(self) -> None:
        data = bytearray(_build_java_class(with_field=True))
        # Corrupt the field's name_index to reference a non-Utf8 entry
        # (index 2, the Class entry). Layout: magic(4)+minor(2)+major(2)+
        # cp_count(2) + Utf8"Foo"(6) + Class(3) + Utf8"I"(4) + Utf8"x"(4)
        # + access_flags(2) + this_class(2) + super_class(2) +
        # interfaces_count(2) + fields_count(2)=1 + field's
        # access_flags(2) + name_index(2).
        offset = 10 + 6 + 3 + 4 + 4 + 2 + 2 + 2 + 2 + 2 + 2
        original_name_index = int.from_bytes(data[offset : offset + 2], "big")
        self.assertEqual(original_name_index, 4)  # the Utf8 "x" member-name entry
        data[offset : offset + 2] = (2).to_bytes(2, "big")  # index 2 is the Class entry
        self.assertFalse(evidence._validate_java_class_structure(bytes(data)))

    def test_field_with_invalid_descriptor_index_is_invalid(self) -> None:
        data = bytearray(_build_java_class(with_field=True))
        offset = 10 + 6 + 3 + 4 + 4 + 2 + 2 + 2 + 2 + 2 + 2 + 2  # descriptor_index follows name_index
        original_descriptor_index = int.from_bytes(data[offset : offset + 2], "big")
        self.assertEqual(original_descriptor_index, 3)  # the Utf8 "I" descriptor entry
        data[offset : offset + 2] = (2).to_bytes(2, "big")  # index 2 is the Class entry
        self.assertFalse(evidence._validate_java_class_structure(bytes(data)))

    def test_truncated_in_fields_table_is_invalid(self) -> None:
        data = _build_java_class(with_field=True)
        self.assertFalse(evidence._validate_java_class_structure(data[:-1]))

    def test_truncated_in_methods_table_is_invalid(self) -> None:
        data = _build_java_class(with_method=True)
        self.assertFalse(evidence._validate_java_class_structure(data[:-1]))

    def test_attribute_with_invalid_name_index_is_invalid(self) -> None:
        data = bytearray(_build_java_class(with_attribute=True))
        # The tail of a with_attribute=True fixture is exactly
        # attributes_count(2)=1 + attribute_name_index(2) +
        # attribute_length(4)=0 -- 8 bytes total.
        self.assertEqual(int.from_bytes(data[-8:-6], "big"), 1)  # attributes_count
        original_attr_name_index = int.from_bytes(data[-6:-4], "big")
        data[-6:-4] = (2).to_bytes(2, "big")  # index 2 is the Class entry, not Utf8
        self.assertNotEqual(original_attr_name_index, 2)
        self.assertFalse(evidence._validate_java_class_structure(bytes(data)))

    def test_attribute_length_extending_past_payload_is_invalid(self) -> None:
        data = bytearray(_build_java_class(with_attribute=True))
        data[-4:] = (60000).to_bytes(4, "big")  # attribute_length, way past EOF
        self.assertFalse(evidence._validate_java_class_structure(bytes(data)))

    def test_trailing_bytes_after_valid_class_is_invalid(self) -> None:
        # Exact EOF is required -- extra bytes appended after an
        # otherwise fully well-formed, valid class file must still fail.
        data = _build_java_class(trailing_bytes=b"\x00")
        self.assertFalse(evidence._validate_java_class_structure(data))

    def test_truncated_valid_class_is_invalid(self) -> None:
        data = _build_java_class()
        self.assertFalse(evidence._validate_java_class_structure(data[:-1]))

    # -- End-to-end classify_native_member_signal() coverage. ------------

    def test_valid_class_under_dot_class_name_is_not_native(self) -> None:
        self.assertEqual(
            evidence.classify_native_member_signal("com/example/Foo.class", _build_java_class()),
            "not_native",
        )

    def test_valid_class_bytes_renamed_dot_bin_is_malformed(self) -> None:
        # Requirement: "Valid Java bytes renamed .bin/other extension ->
        # malformed_native_magic (conservative)". The payload is a
        # perfectly valid Java class file, but the fallback requires the
        # exact `.class` name too -- a non-`.class` name must never
        # receive the exemption regardless of how well-formed the
        # payload independently is.
        valid_class = _build_java_class()
        self.assertEqual(
            evidence.classify_native_member_signal("payload.bin", valid_class), "malformed_native_magic"
        )
        self.assertEqual(
            evidence.classify_native_member_signal("payload", valid_class), "malformed_native_magic"
        )
        self.assertEqual(
            evidence.classify_native_member_signal("payload.dat", valid_class), "malformed_native_magic"
        )

    def test_valid_class_under_wrong_case_class_suffix_is_malformed(self) -> None:
        # Explicit case policy (JAVA_CLASS_MEMBER_SUFFIX): only the exact
        # lowercase `.class` suffix qualifies, matching real javac/JAR
        # tooling output -- `.CLASS`/`.Class` do not.
        valid_class = _build_java_class()
        self.assertEqual(
            evidence.classify_native_member_signal("Foo.CLASS", valid_class), "malformed_native_magic"
        )
        self.assertEqual(
            evidence.classify_native_member_signal("Foo.Class", valid_class), "malformed_native_magic"
        )

    def test_malformed_class_under_dot_class_name_is_malformed(self) -> None:
        # Every malformed-structure case above, re-verified through the
        # full classify_native_member_signal() entry point under the
        # exact `.class` name it would otherwise qualify for.
        cases = {
            "unknown_tag": (lambda d: (d.__setitem__(10, 0xFF), bytes(d))[1])(bytearray(_build_java_class())),
            "truncated": _build_java_class()[:-1],
            "trailing_bytes": _build_java_class(trailing_bytes=b"\x00"),
            "truncated_fields": _build_java_class(with_field=True)[:-1],
            "truncated_methods": _build_java_class(with_method=True)[:-1],
        }
        for description, data in cases.items():
            with self.subTest(case=description):
                self.assertEqual(
                    evidence.classify_native_member_signal("Foo.class", data), "malformed_native_magic"
                )

    def test_zero_and_truncated_fat_macho_under_dot_bin_and_dot_class_are_malformed(self) -> None:
        # "zero/truncated malformed fat .bin and .class fail" -- explicit
        # coverage under both extensions, for both a zero-arch-count claim
        # and a truncated-header claim.
        zero_arch = b"\xca\xfe\xba\xbe" + (0).to_bytes(4, "big") + b"\x00" * 8
        truncated_header = b"\xca\xfe\xba\xbe" + (1).to_bytes(4, "big")
        for name in ("payload.bin", "Foo.class"):
            with self.subTest(name=name, case="zero_arch"):
                self.assertEqual(
                    evidence.classify_native_member_signal(name, zero_arch), "malformed_native_magic"
                )
            with self.subTest(name=name, case="truncated_header"):
                self.assertEqual(
                    evidence.classify_native_member_signal(name, truncated_header), "malformed_native_magic"
                )


class ModifiedUtf8ValidationTests(unittest.TestCase):
    """`_is_valid_modified_utf8()` -- JVMS §4.4.7. Modified UTF-8 is
    deliberately NOT ordinary UTF-8: raw NUL is forbidden (code point 0
    may ONLY appear as the exact overlong `C0 80` form), every OTHER
    overlong encoding is illegal, the standard 4-byte lead-byte form
    (and every byte 0xF0-0xFF) is never recognized, and supplementary
    characters (> U+FFFF) are represented as a paired 6-byte
    high+low-surrogate encoding rather than any 4-byte form.
    """

    def test_empty_is_valid(self) -> None:
        self.assertTrue(evidence._is_valid_modified_utf8(b""))

    def test_plain_ascii_is_valid(self) -> None:
        self.assertTrue(evidence._is_valid_modified_utf8(b"Hello, World! 123"))

    def test_raw_nul_byte_is_invalid(self) -> None:
        self.assertFalse(evidence._is_valid_modified_utf8(b"abc\x00def"))
        self.assertFalse(evidence._is_valid_modified_utf8(b"\x00"))

    def test_encoded_nul_c0_80_is_valid(self) -> None:
        # The documented sole exception to "no overlong encodings":
        # code point 0 is represented as the 2-byte overlong pair C0 80.
        self.assertTrue(evidence._is_valid_modified_utf8(b"\xc0\x80"))
        self.assertTrue(evidence._is_valid_modified_utf8(b"a\xc0\x80b"))

    def test_two_byte_range_boundaries_are_valid(self) -> None:
        self.assertTrue(evidence._is_valid_modified_utf8(b"\xc2\x80"))  # U+0080 (min)
        self.assertTrue(evidence._is_valid_modified_utf8(b"\xdf\xbf"))  # U+07FF (max)

    def test_three_byte_range_boundaries_are_valid(self) -> None:
        self.assertTrue(evidence._is_valid_modified_utf8(b"\xe0\xa0\x80"))  # U+0800 (min)
        self.assertTrue(evidence._is_valid_modified_utf8(b"\xef\xbf\xbd"))  # U+FFFD (non-surrogate)

    def test_overlong_two_byte_encoding_of_ascii_is_invalid(self) -> None:
        # C1 81 decodes to U+0041 ('A'), which must use the 1-byte form.
        self.assertFalse(evidence._is_valid_modified_utf8(b"\xc1\x81"))

    def test_overlong_three_byte_encoding_is_invalid(self) -> None:
        # E0 81 81 decodes to U+0041 ('A'), which must use the 1-byte form.
        self.assertFalse(evidence._is_valid_modified_utf8(b"\xe0\x81\x81"))
        # E0 80 80 decodes to U+0000, which must use the exact C0 80 form.
        self.assertFalse(evidence._is_valid_modified_utf8(b"\xe0\x80\x80"))

    def test_unsupported_standard_four_byte_lead_is_invalid(self) -> None:
        # F0 90 80 80 is the standard-UTF-8 4-byte encoding of U+10000 --
        # never recognized by modified UTF-8, which uses the 6-byte
        # surrogate-pair form instead.
        self.assertFalse(evidence._is_valid_modified_utf8(b"\xf0\x90\x80\x80"))

    def test_byte_in_reserved_high_range_is_invalid(self) -> None:
        for byte in (0xF0, 0xF7, 0xF8, 0xFF):
            with self.subTest(byte=hex(byte)):
                self.assertFalse(evidence._is_valid_modified_utf8(bytes([byte])))

    def test_malformed_continuation_after_two_byte_lead_is_invalid(self) -> None:
        self.assertFalse(evidence._is_valid_modified_utf8(b"\xc2A"))

    def test_malformed_continuation_after_three_byte_lead_is_invalid(self) -> None:
        self.assertFalse(evidence._is_valid_modified_utf8(b"\xe0\xa0A"))
        self.assertFalse(evidence._is_valid_modified_utf8(b"\xe0A\x80"))

    def test_truncated_two_byte_sequence_is_invalid(self) -> None:
        self.assertFalse(evidence._is_valid_modified_utf8(b"\xc2"))

    def test_truncated_three_byte_sequence_is_invalid(self) -> None:
        self.assertFalse(evidence._is_valid_modified_utf8(b"\xe0\xa0"))
        self.assertFalse(evidence._is_valid_modified_utf8(b"\xe0"))

    def test_stray_continuation_byte_as_lead_is_invalid(self) -> None:
        self.assertFalse(evidence._is_valid_modified_utf8(b"\x80"))
        self.assertFalse(evidence._is_valid_modified_utf8(b"a\xbfb"))

    def test_valid_supplementary_surrogate_pair_is_valid(self) -> None:
        # U+10437 (DESERET CAPITAL LETTER YEE), the standard worked
        # example for CESU-8/modified-UTF8 surrogate-pair encoding:
        # high surrogate U+D801 -> ED A0 81, low surrogate U+DC37 -> ED B0 B7.
        self.assertTrue(evidence._is_valid_modified_utf8(b"\xed\xa0\x81\xed\xb0\xb7"))
        self.assertTrue(evidence._is_valid_modified_utf8(b"a\xed\xa0\x81\xed\xb0\xb7b"))

    def test_unpaired_high_surrogate_is_invalid(self) -> None:
        self.assertFalse(evidence._is_valid_modified_utf8(b"\xed\xa0\x81"))
        self.assertFalse(evidence._is_valid_modified_utf8(b"\xed\xa0\x81abc"))

    def test_unpaired_low_surrogate_is_invalid(self) -> None:
        self.assertFalse(evidence._is_valid_modified_utf8(b"\xed\xb0\xb7"))

    def test_high_surrogate_followed_by_non_surrogate_three_byte_is_invalid(self) -> None:
        # High surrogate (ED A0 81, U+D801) followed by a structurally
        # valid but non-low-surrogate 3-byte sequence (E0 A0 80, U+0800).
        self.assertFalse(evidence._is_valid_modified_utf8(b"\xed\xa0\x81\xe0\xa0\x80"))

    def test_truncated_surrogate_pair_is_invalid(self) -> None:
        self.assertFalse(evidence._is_valid_modified_utf8(b"\xed\xa0\x81\xe0\xa0"))
        self.assertFalse(evidence._is_valid_modified_utf8(b"\xed\xa0\x81\xed"))

    def test_class_with_encoded_nul_and_supplementary_utf8_is_valid(self) -> None:
        # End-to-end: a real class file whose class-name Utf8 entry
        # contains the encoded-NUL and supplementary-character forms
        # still passes full structural validation.
        data = _build_java_class_from_cp(
            [_utf8_entry(b"a\xc0\x80\xed\xa0\x81\xed\xb0\xb7b"), _class_entry(1)],
            this_class=2,
        )
        self.assertTrue(evidence._validate_java_class_structure(data))

    def test_class_with_raw_nul_in_utf8_entry_is_invalid(self) -> None:
        data = _build_java_class_from_cp(
            [_utf8_entry(b"a\x00b"), _class_entry(1)],
            this_class=2,
        )
        self.assertFalse(evidence._validate_java_class_structure(data))


class JavaConstantPoolReferenceValidationTests(unittest.TestCase):
    """Full JVMS §4.4 constant-pool cross-reference validation: every
    entry's own internal constant-pool-index field(s) must be nonzero,
    in range, target the exact tag the spec requires, and (for the
    version-gated tags MethodHandle/MethodType/InvokeDynamic/Dynamic/
    Module/Package) only be used at or after the class-file-format
    version that introduced them.
    """

    # -- CONSTANT_Class_info.name_index -----------------------------------

    def test_class_name_index_zero_is_invalid(self) -> None:
        data = _build_java_class_from_cp([_class_entry(0)])
        self.assertFalse(evidence._validate_java_class_structure(data))

    def test_class_name_index_wrong_tag_is_invalid(self) -> None:
        data = _build_java_class_from_cp([_integer_entry(), _class_entry(1)])
        self.assertFalse(evidence._validate_java_class_structure(data))

    def test_class_name_index_out_of_range_is_invalid(self) -> None:
        data = _build_java_class_from_cp([_utf8_entry(b"Foo"), _class_entry(99)])
        self.assertFalse(evidence._validate_java_class_structure(data))

    def test_class_name_index_targeting_reserved_double_slot_is_invalid(self) -> None:
        data = _build_java_class_from_cp([_long_entry(), _class_entry(2)])
        self.assertFalse(evidence._validate_java_class_structure(data))

    def test_class_name_index_valid_utf8_target_is_valid(self) -> None:
        data = _build_java_class_from_cp([_utf8_entry(b"Foo"), _class_entry(1)], this_class=2)
        self.assertTrue(evidence._validate_java_class_structure(data))

    # -- CONSTANT_String_info.string_index --------------------------------

    def test_string_string_index_wrong_tag_is_invalid(self) -> None:
        data = _build_java_class_from_cp(
            [_utf8_entry(b"Foo"), _class_entry(1), _integer_entry(), _string_entry(3)], this_class=2
        )
        self.assertFalse(evidence._validate_java_class_structure(data))

    def test_string_string_index_valid_utf8_target_is_valid(self) -> None:
        data = _build_java_class_from_cp(
            [_utf8_entry(b"Foo"), _class_entry(1), _utf8_entry(b"hi"), _string_entry(3)], this_class=2
        )
        self.assertTrue(evidence._validate_java_class_structure(data))

    # -- CONSTANT_{Field,Method,InterfaceMethod}ref_info -------------------

    def test_ref_entry_class_index_wrong_tag_for_every_ref_kind(self) -> None:
        for ctor in (_fieldref_entry, _methodref_entry, _interface_methodref_entry):
            with self.subTest(ctor=ctor.__name__):
                # index1=Utf8 (wrong target for class_index), index2=NameAndType(1,1).
                data = _build_java_class_from_cp(
                    [_utf8_entry(b"x"), _name_and_type_entry(1, 1), ctor(1, 2)]
                )
                self.assertFalse(evidence._validate_java_class_structure(data))

    def test_ref_entry_name_and_type_index_wrong_tag_for_every_ref_kind(self) -> None:
        for ctor in (_fieldref_entry, _methodref_entry, _interface_methodref_entry):
            with self.subTest(ctor=ctor.__name__):
                # index1=Utf8, index2=Class(1) (valid class_index target),
                # name_and_type_index=1 wrongly targets the Utf8 entry.
                data = _build_java_class_from_cp([_utf8_entry(b"x"), _class_entry(1), ctor(2, 1)])
                self.assertFalse(evidence._validate_java_class_structure(data))

    def test_ref_entry_valid_targets_for_every_ref_kind_is_valid(self) -> None:
        for ctor in (_fieldref_entry, _methodref_entry, _interface_methodref_entry):
            with self.subTest(ctor=ctor.__name__):
                data = _build_java_class_from_cp(
                    [
                        _utf8_entry(b"Foo"),
                        _class_entry(1),
                        _utf8_entry(b"x"),
                        _utf8_entry(b"I"),
                        _name_and_type_entry(3, 4),
                        ctor(2, 5),
                    ],
                    this_class=2,
                )
                self.assertTrue(evidence._validate_java_class_structure(data))

    # -- CONSTANT_NameAndType_info ------------------------------------------

    def test_name_and_type_name_index_wrong_tag_is_invalid(self) -> None:
        data = _build_java_class_from_cp(
            [_utf8_entry(b"Foo"), _class_entry(1), _utf8_entry(b"I"), _name_and_type_entry(2, 3)],
            this_class=2,
        )
        self.assertFalse(evidence._validate_java_class_structure(data))

    def test_name_and_type_descriptor_index_wrong_tag_is_invalid(self) -> None:
        data = _build_java_class_from_cp(
            [_utf8_entry(b"Foo"), _class_entry(1), _utf8_entry(b"x"), _name_and_type_entry(3, 2)],
            this_class=2,
        )
        self.assertFalse(evidence._validate_java_class_structure(data))

    # -- CONSTANT_MethodHandle_info -----------------------------------------

    def test_method_handle_reference_kind_out_of_range_is_invalid(self) -> None:
        for kind in (0, 10, 255):
            with self.subTest(kind=kind):
                data = _build_java_class_from_cp(
                    [
                        _utf8_entry(b"Foo"),
                        _class_entry(1),
                        _utf8_entry(b"x"),
                        _utf8_entry(b"I"),
                        _name_and_type_entry(3, 4),
                        _fieldref_entry(2, 5),
                        _method_handle_entry(kind, 6),
                    ],
                    this_class=2,
                    major_version=55,
                )
                self.assertFalse(evidence._validate_java_class_structure(data))

    def _method_handle_class(self, kind: int, target_ctor, major_version: int = 55) -> bytes:
        cp = [
            _utf8_entry(b"Foo"),  # 1
            _class_entry(1),  # 2
            _utf8_entry(b"x"),  # 3
            _utf8_entry(b"I"),  # 4
            _name_and_type_entry(3, 4),  # 5
        ]
        cp.append(target_ctor(2, 5))  # 6: the reference target (Field/Method/InterfaceMethodref)
        cp.append(_method_handle_entry(kind, 6))  # 7
        return _build_java_class_from_cp(cp, this_class=2, major_version=major_version)

    def test_method_handle_field_kinds_require_fieldref_target(self) -> None:
        for kind in (1, 2, 3, 4):
            with self.subTest(kind=kind):
                self.assertTrue(evidence._validate_java_class_structure(self._method_handle_class(kind, _fieldref_entry)))
                self.assertFalse(
                    evidence._validate_java_class_structure(self._method_handle_class(kind, _methodref_entry))
                )

    def test_method_handle_virtual_and_new_invoke_special_require_methodref_target(self) -> None:
        for kind in (5, 8):
            with self.subTest(kind=kind):
                self.assertTrue(
                    evidence._validate_java_class_structure(self._method_handle_class(kind, _methodref_entry))
                )
                self.assertFalse(
                    evidence._validate_java_class_structure(self._method_handle_class(kind, _fieldref_entry))
                )

    def test_method_handle_invoke_interface_requires_interface_methodref_target(self) -> None:
        self.assertTrue(
            evidence._validate_java_class_structure(self._method_handle_class(9, _interface_methodref_entry))
        )
        self.assertFalse(evidence._validate_java_class_structure(self._method_handle_class(9, _methodref_entry)))

    def test_method_handle_invoke_static_or_special_under_old_version_rejects_interface_target(self) -> None:
        for kind in (6, 7):
            with self.subTest(kind=kind):
                self.assertTrue(
                    evidence._validate_java_class_structure(
                        self._method_handle_class(kind, _methodref_entry, major_version=51)
                    )
                )
                self.assertFalse(
                    evidence._validate_java_class_structure(
                        self._method_handle_class(kind, _interface_methodref_entry, major_version=51)
                    )
                )

    def test_method_handle_invoke_static_or_special_under_new_version_allows_interface_target(self) -> None:
        for kind in (6, 7):
            with self.subTest(kind=kind):
                self.assertTrue(
                    evidence._validate_java_class_structure(
                        self._method_handle_class(kind, _interface_methodref_entry, major_version=52)
                    )
                )
                self.assertTrue(
                    evidence._validate_java_class_structure(
                        self._method_handle_class(kind, _methodref_entry, major_version=52)
                    )
                )

    # -- CONSTANT_MethodType_info --------------------------------------------

    def test_method_type_descriptor_index_wrong_tag_is_invalid(self) -> None:
        data = _build_java_class_from_cp(
            [_utf8_entry(b"Foo"), _class_entry(1), _class_entry(1), _method_type_entry(3)],
            this_class=2,
            major_version=51,
        )
        self.assertFalse(evidence._validate_java_class_structure(data))

    def test_method_type_descriptor_index_valid_target_is_valid(self) -> None:
        data = _build_java_class_from_cp(
            [_utf8_entry(b"Foo"), _class_entry(1), _utf8_entry(b"()V"), _method_type_entry(3)],
            this_class=2,
            major_version=51,
        )
        self.assertTrue(evidence._validate_java_class_structure(data))

    # -- CONSTANT_Dynamic_info / CONSTANT_InvokeDynamic_info -----------------

    def test_dynamic_and_invoke_dynamic_name_and_type_index_wrong_tag_is_invalid(self) -> None:
        for ctor, version in ((_dynamic_entry, 55), (_invoke_dynamic_entry, 51)):
            with self.subTest(ctor=ctor.__name__):
                data = _build_java_class_from_cp(
                    [_utf8_entry(b"Foo"), _class_entry(1), ctor(0, 1)],
                    this_class=2,
                    major_version=version,
                )
                self.assertFalse(evidence._validate_java_class_structure(data))

    def test_dynamic_and_invoke_dynamic_valid_target_is_valid(self) -> None:
        for ctor, version in ((_dynamic_entry, 55), (_invoke_dynamic_entry, 51)):
            with self.subTest(ctor=ctor.__name__):
                data = _build_java_class_from_cp(
                    [
                        _utf8_entry(b"Foo"),
                        _class_entry(1),
                        _utf8_entry(b"x"),
                        _utf8_entry(b"I"),
                        _name_and_type_entry(3, 4),
                        ctor(0, 5),
                    ],
                    this_class=2,
                    major_version=version,
                )
                self.assertTrue(evidence._validate_java_class_structure(data))

    # -- CONSTANT_Module_info / CONSTANT_Package_info ------------------------

    def test_module_and_package_name_index_wrong_tag_is_invalid(self) -> None:
        for ctor in (_module_entry, _package_entry):
            with self.subTest(ctor=ctor.__name__):
                data = _build_java_class_from_cp(
                    [_utf8_entry(b"Foo"), _class_entry(1), _class_entry(1), ctor(3)],
                    this_class=2,
                    major_version=53,
                )
                self.assertFalse(evidence._validate_java_class_structure(data))

    def test_module_and_package_name_index_valid_target_is_valid(self) -> None:
        for ctor in (_module_entry, _package_entry):
            with self.subTest(ctor=ctor.__name__):
                data = _build_java_class_from_cp(
                    [_utf8_entry(b"Foo"), _class_entry(1), _utf8_entry(b"mymodule"), ctor(3)],
                    this_class=2,
                    major_version=53,
                )
                self.assertTrue(evidence._validate_java_class_structure(data))

    # -- Class-file-version floor for newer tags -----------------------------

    def test_newer_tags_under_too_old_a_version_are_invalid(self) -> None:
        cases = [
            (evidence.JAVA_CP_TAG_METHOD_HANDLE, _method_handle_entry(1, 2), 50),
            (evidence.JAVA_CP_TAG_METHOD_TYPE, _method_type_entry(1), 50),
            (evidence.JAVA_CP_TAG_INVOKE_DYNAMIC, _invoke_dynamic_entry(0, 1), 50),
            (evidence.JAVA_CP_TAG_DYNAMIC, _dynamic_entry(0, 1), 54),
            (evidence.JAVA_CP_TAG_MODULE, _module_entry(1), 52),
            (evidence.JAVA_CP_TAG_PACKAGE, _package_entry(1), 52),
        ]
        for tag, entry, version in cases:
            with self.subTest(tag=tag):
                data = _build_java_class_from_cp([_utf8_entry(b"x"), entry], major_version=version)
                self.assertFalse(evidence._validate_java_class_structure(data))

    def test_newer_tags_at_exact_minimum_version_pass_the_version_check(self) -> None:
        # `_parse_java_class_constant_pool` (pass 1) is exactly where the
        # version gate lives, and it does not itself validate any
        # cross-reference (that is pass 2, `_validate_java_cp_references`)
        # -- so a single bare entry with an arbitrary index-1 reference
        # is sufficient here to isolate the version check from
        # reference-target correctness, which is covered separately above.
        entry_by_tag = {
            evidence.JAVA_CP_TAG_METHOD_HANDLE: _method_handle_entry(1, 1),
            evidence.JAVA_CP_TAG_METHOD_TYPE: _method_type_entry(1),
            evidence.JAVA_CP_TAG_INVOKE_DYNAMIC: _invoke_dynamic_entry(0, 1),
            evidence.JAVA_CP_TAG_DYNAMIC: _dynamic_entry(0, 1),
            evidence.JAVA_CP_TAG_MODULE: _module_entry(1),
            evidence.JAVA_CP_TAG_PACKAGE: _package_entry(1),
        }
        for tag, min_version in evidence.JAVA_CP_TAG_MIN_MAJOR_VERSION.items():
            with self.subTest(tag=tag, version=min_version):
                reader = evidence._BoundedJavaClassReader(entry_by_tag[tag])
                evidence._parse_java_class_constant_pool(reader, 2, min_version)  # must not raise
            with self.subTest(tag=tag, version=min_version - 1):
                reader = evidence._BoundedJavaClassReader(entry_by_tag[tag])
                with self.assertRaises(evidence._JavaClassParseError):
                    evidence._parse_java_class_constant_pool(reader, 2, min_version - 1)

    # -- Long/Double terminal-entry and reserved-slot semantics --------------

    def test_long_as_terminal_constant_pool_entry_is_valid(self) -> None:
        # JVMS §4.4/§4.4.5: a constant_pool index is valid if it is
        # greater than zero and less than constant_pool_count, "with the
        # exception for constants of type long and double" -- i.e. a
        # Long/Double's reserved successor slot at index
        # constant_pool_count is EXPLICITLY sanctioned even though it
        # falls outside the general range. A Long/Double may legally be
        # the very last real entry in the pool.
        data = _build_java_class_from_cp([_utf8_entry(b"Foo"), _class_entry(1), _long_entry()], this_class=2)
        self.assertTrue(evidence._validate_java_class_structure(data))

    def test_double_as_terminal_constant_pool_entry_is_valid(self) -> None:
        data = _build_java_class_from_cp([_utf8_entry(b"Foo"), _class_entry(1), _double_entry()], this_class=2)
        self.assertTrue(evidence._validate_java_class_structure(data))

    def test_reference_to_double_slot_phantom_index_is_invalid_via_string(self) -> None:
        # Additional coverage (beyond this_class, already covered in
        # JavaClassStructuralValidationTests) of the same reserved-slot
        # rule through an ordinary CONSTANT_String_info reference: index
        # 1 is a Long (occupying slots 1 and 2), index 3 is a valid
        # Class, and the String entry's string_index=2 illegally targets
        # the Long's reserved/phantom slot 2.
        data = _build_java_class_from_cp(
            [_long_entry(), _utf8_entry(b"Foo"), _class_entry(3), _string_entry(2)], this_class=4
        )
        self.assertFalse(evidence._validate_java_class_structure(data))

    # -- Representative valid class using every newer tag together -----------

    def test_representative_valid_class_using_every_newer_cp_tag(self) -> None:
        cp = [
            _utf8_entry(b"Foo"),  # 1
            _class_entry(1),  # 2: this_class
            _utf8_entry(b"x"),  # 3
            _utf8_entry(b"I"),  # 4
            _name_and_type_entry(3, 4),  # 5
            _fieldref_entry(2, 5),  # 6
            _method_handle_entry(1, 6),  # 7: REF_getField -> Fieldref
            _utf8_entry(b"()V"),  # 8
            _method_type_entry(8),  # 9
            _invoke_dynamic_entry(0, 5),  # 10
            _dynamic_entry(0, 5),  # 11
            _utf8_entry(b"mymodule"),  # 12
            _module_entry(12),  # 13
            _utf8_entry(b"mypackage"),  # 14
            _package_entry(14),  # 15
            _long_entry(),  # 16 (terminal double-slot entry)
        ]
        data = _build_java_class_from_cp(cp, this_class=2, major_version=55)
        self.assertTrue(evidence._validate_java_class_structure(data))


class NativeCarrierDynamicDiscoveryTests(unittest.TestCase):
    """`cross_check_maven_native_carriers_against_local_cache()` -- Gap 7,
    extended for Gap 3 (whole-archive hash verification before member
    inspection) and Gap 4 (magic-based discovery regardless of extension).

    Builds a disposable, synthetic Gradle module cache (never a real
    download) so every failure mode can be exercised deterministically:
    a brand-new native-carrying coordinate absent from the catalog, an
    unreviewed extra/missing member on an already-catalogued coordinate,
    a member hash/size drift, a duplicate member path within one archive,
    a wrong/substituted whole-archive hash (even with an identical native
    member), an additional-artifact hash mismatch, an ambiguous duplicate
    resolution, a renamed native payload with a misleading extension, a
    known-extension/content mismatch, and the cold-cache no-op case.
    """

    ELF = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8

    def setUp(self) -> None:
        self._orig_modules2 = evidence.GRADLE_MODULES2
        self._tmp = tempfile.TemporaryDirectory()
        evidence.GRADLE_MODULES2 = Path(self._tmp.name)

    def tearDown(self) -> None:
        evidence.GRADLE_MODULES2 = self._orig_modules2
        self._tmp.cleanup()

    def _write_archive(
        self,
        group: str,
        artifact: str,
        version: str,
        members: dict[str, bytes],
        variant: str = "deadbeef",
        ext: str = "jar",
    ) -> tuple[Path, str]:
        import zipfile

        base = evidence.GRADLE_MODULES2 / group / artifact / version / variant
        base.mkdir(parents=True, exist_ok=True)
        archive_path = base / f"{artifact}-{version}.{ext}"
        with zipfile.ZipFile(archive_path, "w") as zf:
            for name, data in members.items():
                zf.writestr(name, data)
        return archive_path, evidence.sha256_file(archive_path)

    def _write_jar(self, group: str, artifact: str, version: str, members: dict[str, bytes]) -> tuple[Path, str]:
        return self._write_archive(group, artifact, version, members)

    def _gradle_report(self, gav: str) -> dict:
        return {"modules": {"fake": {"coordinates": {"runtime": [gav]}}}}

    def _base_carrier(self, coordinate: str, artifact_sha256: str, embedded_natives: list[dict], **overrides) -> dict:
        carrier = {
            "maven_coordinate": coordinate,
            "carrier_kind": "JVM .jar",
            "license": "MIT",
            "distribution_status": "redistributed_by_kardano",
            "distributed_by_kardano": True,
            "windows_native_available_upstream": False,
            "inspected_2026_08_24": True,
            "artifact_sha256": artifact_sha256,
            "primary_artifact_kind": "jar",
            "embedded_natives": embedded_natives,
            "note": None,
        }
        carrier.update(overrides)
        return carrier

    def test_cold_cache_is_a_no_op(self) -> None:
        gradle_report = self._gradle_report("com.example:nowhere:1.0")
        evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)  # no raise

    def test_new_native_carrying_coordinate_not_in_catalog_raises(self) -> None:
        self._write_jar("com.example", "widget", "1.0", {"libwidget.so": self.ELF + b"fake-elf-bytes"})
        gradle_report = self._gradle_report("com.example:widget:1.0")
        with self.assertRaises(evidence.EvidenceError) as ctx:
            evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("not present in MAVEN_NATIVE_CARRIERS", str(ctx.exception))

    def test_matching_catalog_entry_passes(self) -> None:
        data = self.ELF + b"fake-elf-bytes"
        digest = evidence.sha256_bytes(data)
        _, archive_digest = self._write_jar("com.example", "widget", "1.0", {"libwidget.so": data})
        carrier = self._base_carrier(
            "com.example:widget:1.0",
            archive_digest,
            [{"path": "libwidget.so", "size_bytes": len(data), "sha256": digest, "platform": "Linux", "arch": "x86-64"}],
        )
        gradle_report = self._gradle_report("com.example:widget:1.0")
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)  # no raise

    def test_extra_undeclared_member_on_known_carrier_raises(self) -> None:
        data = self.ELF + b"fake-elf-bytes"
        digest = evidence.sha256_bytes(data)
        _, archive_digest = self._write_jar(
            "com.example",
            "widget",
            "1.0",
            {"libwidget.so": data, "libextra.so": self.ELF + b"a-second-native-blob"},
        )
        carrier = self._base_carrier(
            "com.example:widget:1.0",
            archive_digest,
            [{"path": "libwidget.so", "size_bytes": len(data), "sha256": digest, "platform": "Linux", "arch": "x86-64"}],
        )
        gradle_report = self._gradle_report("com.example:widget:1.0")
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError) as ctx:
                evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("unreviewed native member path", str(ctx.exception))

    def test_missing_catalogued_member_raises(self) -> None:
        # Catalog declares a member the actual archive no longer contains.
        data = self.ELF + b"fake-elf-bytes"
        _, archive_digest = self._write_jar("com.example", "widget", "1.0", {"libwidget.so": data})
        carrier = self._base_carrier(
            "com.example:widget:1.0",
            archive_digest,
            [
                {
                    "path": "libwidget.so",
                    "size_bytes": len(data),
                    "sha256": evidence.sha256_bytes(data),
                    "platform": "Linux",
                    "arch": "x86-64",
                },
                {
                    "path": "libgone.so",
                    "size_bytes": 5,
                    "sha256": "1" * 64,
                    "platform": "Linux",
                    "arch": "x86-64",
                },
            ],
        )
        gradle_report = self._gradle_report("com.example:widget:1.0")
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError) as ctx:
                evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("no longer contain", str(ctx.exception))

    def test_hash_drift_on_known_member_raises(self) -> None:
        data = self.ELF + b"fake-elf-bytes"
        _, archive_digest = self._write_jar("com.example", "widget", "1.0", {"libwidget.so": data})
        carrier = self._base_carrier(
            "com.example:widget:1.0",
            archive_digest,
            [{"path": "libwidget.so", "size_bytes": len(data), "sha256": "9" * 64, "platform": "Linux", "arch": "x86-64"}],
        )
        gradle_report = self._gradle_report("com.example:widget:1.0")
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError) as ctx:
                evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("archive/hash drift", str(ctx.exception))

    def test_size_drift_on_known_member_raises(self) -> None:
        data = self.ELF + b"fake-elf-bytes"
        _, archive_digest = self._write_jar("com.example", "widget", "1.0", {"libwidget.so": data})
        carrier = self._base_carrier(
            "com.example:widget:1.0",
            archive_digest,
            [
                {
                    "path": "libwidget.so",
                    "size_bytes": len(data) + 1,
                    "sha256": evidence.sha256_bytes(data),
                    "platform": "Linux",
                    "arch": "x86-64",
                }
            ],
        )
        gradle_report = self._gradle_report("com.example:widget:1.0")
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError):
                evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)

    def test_duplicate_member_path_within_one_archive_raises(self) -> None:
        import zipfile

        base = evidence.GRADLE_MODULES2 / "com.example" / "widget" / "1.0" / "deadbeef"
        base.mkdir(parents=True, exist_ok=True)
        jar_path = base / "widget-1.0.jar"
        with zipfile.ZipFile(jar_path, "w") as zf:
            zf.writestr("libwidget.so", self.ELF + b"first-copy")
            zf.writestr("libwidget.so", self.ELF + b"second-copy-different-bytes")
        gradle_report = self._gradle_report("com.example:widget:1.0")
        # Caught by the earlier, more general zip-level duplicate-member
        # check in `_scan_zip_for_native_members` (before classification
        # even runs), not the cross-archive merge check further down.
        with self.assertRaises(evidence.EvidenceError) as ctx:
            evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("normalize to the same path", str(ctx.exception))

    def test_java_class_resource_near_misses_do_not_trigger_a_false_positive(self) -> None:
        # A jar full of ordinary, structurally-valid .class files (CAFEBABE
        # magic, colliding with Mach-O fat-binary magic) must not be
        # reported as carrying native members at all. Uses a genuinely
        # valid class file, not just a plausible-looking magic+version
        # prefix -- see `_validate_java_class_structure`.
        self._write_jar(
            "com.example",
            "puretype",
            "1.0",
            {"com/example/Foo.class": _build_java_class(class_name="com/example/Foo")},
        )
        gradle_report = self._gradle_report("com.example:puretype:1.0")
        evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)  # no raise

    # -- REVIEWED_NON_NATIVE_MEMBERS: narrow, hash-pinned exception -------

    def test_reviewed_non_native_member_exact_match_does_not_raise(self) -> None:
        # A member whose (coordinate, path, sha256) exactly matches a
        # human-reviewed entry is skipped entirely -- never reaches the
        # "not present in MAVEN_NATIVE_CARRIERS" catalog check either,
        # same as a genuinely `not_native` member would.
        valid_class_renamed_bin = _build_java_class(class_name="Renamed")
        digest = hashlib.sha256(valid_class_renamed_bin).hexdigest()
        reviewed = (
            {
                "maven_coordinate": "com.example:reviewedbin:1.0",
                "path": "SomeDebugProbes.bin",
                "sha256": digest,
            },
        )
        self._write_jar(
            "com.example", "reviewedbin", "1.0", {"SomeDebugProbes.bin": valid_class_renamed_bin}
        )
        gradle_report = self._gradle_report("com.example:reviewedbin:1.0")
        with mock.patch.object(evidence, "REVIEWED_NON_NATIVE_MEMBERS", reviewed):
            evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)  # no raise

    def test_reviewed_non_native_member_wrong_content_still_raises(self) -> None:
        # Same coordinate and path as the reviewed entry, but ONE byte of
        # content differs -- the sha256 pin must not match, and this must
        # still fail closed (never "close enough").
        reviewed_bytes = _build_java_class(class_name="Renamed")
        reviewed = (
            {
                "maven_coordinate": "com.example:reviewedbin:1.0",
                "path": "SomeDebugProbes.bin",
                "sha256": hashlib.sha256(reviewed_bytes).hexdigest(),
            },
        )
        tampered_bytes = _build_java_class(class_name="Tampered")
        self.assertNotEqual(reviewed_bytes, tampered_bytes)
        self._write_jar("com.example", "reviewedbin", "1.0", {"SomeDebugProbes.bin": tampered_bytes})
        gradle_report = self._gradle_report("com.example:reviewedbin:1.0")
        with mock.patch.object(evidence, "REVIEWED_NON_NATIVE_MEMBERS", reviewed):
            with self.assertRaises(evidence.EvidenceError) as ctx:
                evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("failed this generator's bounded structural validation", str(ctx.exception))

    def test_reviewed_non_native_member_wrong_coordinate_still_raises(self) -> None:
        # Identical path and content, but resolved under a DIFFERENT
        # coordinate than the one the reviewer actually pinned -- the
        # exception must not transfer across coordinates.
        valid_class_renamed_bin = _build_java_class(class_name="Renamed")
        digest = hashlib.sha256(valid_class_renamed_bin).hexdigest()
        reviewed = (
            {
                "maven_coordinate": "com.example:other-coordinate:9.9",
                "path": "SomeDebugProbes.bin",
                "sha256": digest,
            },
        )
        self._write_jar(
            "com.example", "reviewedbin", "1.0", {"SomeDebugProbes.bin": valid_class_renamed_bin}
        )
        gradle_report = self._gradle_report("com.example:reviewedbin:1.0")
        with mock.patch.object(evidence, "REVIEWED_NON_NATIVE_MEMBERS", reviewed):
            with self.assertRaises(evidence.EvidenceError):
                evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)

    # -- Zip-level duplicate-member fail-closed, BEFORE classification -----

    def _write_raw_zip(self, group: str, artifact: str, version: str, raw_names: list[str], data: bytes) -> Path:
        import zipfile

        base = evidence.GRADLE_MODULES2 / group / artifact / version / "deadbeef"
        base.mkdir(parents=True, exist_ok=True)
        archive_path = base / f"{artifact}-{version}.jar"
        with zipfile.ZipFile(archive_path, "w") as zf:
            for name in raw_names:
                zf.writestr(name, data)
        return archive_path

    def test_exact_duplicate_ordinary_member_name_raises_before_classification(self) -> None:
        archive_path = self._write_raw_zip(
            "com.example", "dupordinary", "1.0", ["NOTICE.txt", "NOTICE.txt"], b"same text twice"
        )
        gradle_report = self._gradle_report("com.example:dupordinary:1.0")
        with self.assertRaises(evidence.EvidenceError) as ctx:
            evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn(str(archive_path), str(ctx.exception))
        self.assertIn("normalize to the same path", str(ctx.exception))

    def test_exact_duplicate_native_member_name_raises_before_classification(self) -> None:
        self._write_raw_zip("com.example", "dupnative", "1.0", ["libwidget.so", "libwidget.so"], self.ELF)
        gradle_report = self._gradle_report("com.example:dupnative:1.0")
        with self.assertRaises(evidence.EvidenceError) as ctx:
            evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("normalize to the same path", str(ctx.exception))

    def test_duplicate_debug_probes_kt_bin_raises_even_though_reviewed(self) -> None:
        # A duplicate of the EXACT reviewed member (same coordinate,
        # path, and content as a real REVIEWED_NON_NATIVE_MEMBERS entry)
        # must still fail closed on the duplicate-name check itself --
        # the hash-pinned exception is consulted per-member only AFTER
        # duplicate detection, and never bypasses it.
        valid_class = _build_java_class(class_name="DebugProbesKt")
        reviewed = (
            {
                "maven_coordinate": "com.example:dupreviewed:1.0",
                "path": "DebugProbesKt.bin",
                "sha256": hashlib.sha256(valid_class).hexdigest(),
            },
        )
        self._write_raw_zip(
            "com.example", "dupreviewed", "1.0", ["DebugProbesKt.bin", "DebugProbesKt.bin"], valid_class
        )
        gradle_report = self._gradle_report("com.example:dupreviewed:1.0")
        with mock.patch.object(evidence, "REVIEWED_NON_NATIVE_MEMBERS", reviewed):
            with self.assertRaises(evidence.EvidenceError) as ctx:
                evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("normalize to the same path", str(ctx.exception))

    def test_backslash_vs_forward_slash_member_names_collide(self) -> None:
        self._write_raw_zip("com.example", "dupslash", "1.0", ["a/b.txt", "a\\b.txt"], b"payload")
        gradle_report = self._gradle_report("com.example:dupslash:1.0")
        with self.assertRaises(evidence.EvidenceError):
            evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)

    def test_directory_and_same_named_file_entry_collide(self) -> None:
        self._write_raw_zip("com.example", "dupdirfile", "1.0", ["foo/bar/", "foo/bar"], b"payload")
        gradle_report = self._gradle_report("com.example:dupdirfile:1.0")
        with self.assertRaises(evidence.EvidenceError):
            evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)

    def test_case_distinct_member_names_do_not_collide(self) -> None:
        # Deliberate, documented case policy: ZIP/JAR member-name
        # comparison is case-SENSITIVE (matching the real central
        # directory and JVM/JLS resource-name resolution semantics), so
        # two members differing only by case are NOT a collision.
        self._write_jar(
            "com.example",
            "casedistinct",
            "1.0",
            {"Foo.txt": b"one", "foo.txt": b"two"},
        )
        gradle_report = self._gradle_report("com.example:casedistinct:1.0")
        evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)  # no raise

    def test_one_exact_reviewed_member_without_any_duplicate_is_valid(self) -> None:
        # Sanity check that ordinary (non-duplicated) reviewed-member
        # handling is unaffected by the new duplicate-detection pass.
        valid_class_renamed_bin = _build_java_class(class_name="Solo")
        digest = hashlib.sha256(valid_class_renamed_bin).hexdigest()
        reviewed = (
            {
                "maven_coordinate": "com.example:soloreviewed:1.0",
                "path": "SomeDebugProbes.bin",
                "sha256": digest,
            },
        )
        self._write_jar(
            "com.example", "soloreviewed", "1.0", {"SomeDebugProbes.bin": valid_class_renamed_bin}
        )
        gradle_report = self._gradle_report("com.example:soloreviewed:1.0")
        with mock.patch.object(evidence, "REVIEWED_NON_NATIVE_MEMBERS", reviewed):
            evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)  # no raise

    def test_two_artifacts_same_coordinate_merge_without_conflict(self) -> None:
        # Mirrors JNA 5.19.1's real shape: a .jar AND a separate .aar for
        # the exact same coordinate, each carrying disjoint native paths.
        jar_data = self.ELF + b"jar-native-bytes"
        aar_data = self.ELF + b"aar-native-bytes"
        _, jar_digest = self._write_archive(
            "com.example", "dual", "1.0", {"com/example/libdual.so": jar_data}, variant="jarhash", ext="jar"
        )
        _, aar_digest = self._write_archive(
            "com.example", "dual", "1.0", {"jni/arm64-v8a/libdual.so": aar_data}, variant="aarhash", ext="aar"
        )
        carrier = self._base_carrier(
            "com.example:dual:1.0",
            jar_digest,
            [
                {
                    "path": "com/example/libdual.so",
                    "size_bytes": len(jar_data),
                    "sha256": evidence.sha256_bytes(jar_data),
                    "platform": "Linux",
                    "arch": "x86-64",
                },
                {
                    "path": "jni/arm64-v8a/libdual.so",
                    "size_bytes": len(aar_data),
                    "sha256": evidence.sha256_bytes(aar_data),
                    "platform": "Android",
                    "arch": "arm64-v8a",
                },
            ],
            carrier_kind="JVM .jar + Android .aar",
            additional_artifacts=[{"kind": "aar", "artifact_sha256": aar_digest}],
        )
        gradle_report = self._gradle_report("com.example:dual:1.0")
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)  # no raise

    # -- Gap 3: whole-archive hash verification before member inspection --

    def test_wrong_whole_archive_hash_raises_before_member_inspection(self) -> None:
        data = self.ELF + b"fake-elf-bytes"
        digest = evidence.sha256_bytes(data)
        self._write_jar("com.example", "widget", "1.0", {"libwidget.so": data})
        carrier = self._base_carrier(
            "com.example:widget:1.0",
            "f" * 64,  # deliberately wrong whole-archive hash
            [{"path": "libwidget.so", "size_bytes": len(data), "sha256": digest, "platform": "Linux", "arch": "x86-64"}],
        )
        gradle_report = self._gradle_report("com.example:widget:1.0")
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError) as ctx:
                evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("wrong/substituted artifact", str(ctx.exception))

    def test_archive_classes_changed_but_native_member_identical_still_raises(self) -> None:
        # The catalogued native member's own bytes are unchanged, but
        # something else in the archive (a class file, metadata, etc.)
        # changed -- the whole-archive hash therefore differs, and this
        # must still fail even though a member-only check would have
        # passed. Simulates a substituted archive that reuses a real
        # native library while smuggling in different application code.
        native = self.ELF + b"fake-elf-bytes"
        native_digest = evidence.sha256_bytes(native)
        _, original_archive_digest = self._write_jar(
            "com.example", "widget", "1.0", {"libwidget.so": native, "com/example/Foo.class": b"original"}
        )
        carrier = self._base_carrier(
            "com.example:widget:1.0",
            original_archive_digest,
            [{"path": "libwidget.so", "size_bytes": len(native), "sha256": native_digest, "platform": "Linux", "arch": "x86-64"}],
        )
        # Now rewrite the SAME archive path with different non-native
        # content but the IDENTICAL native member bytes.
        self._write_jar(
            "com.example", "widget", "1.0", {"libwidget.so": native, "com/example/Foo.class": b"tampered-different"}
        )
        gradle_report = self._gradle_report("com.example:widget:1.0")
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError) as ctx:
                evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("wrong/substituted artifact", str(ctx.exception))

    def test_additional_artifact_hash_mismatch_raises(self) -> None:
        jar_data = self.ELF + b"jar-native-bytes"
        aar_data = self.ELF + b"aar-native-bytes"
        _, jar_digest = self._write_archive(
            "com.example", "dual", "1.0", {"com/example/libdual.so": jar_data}, variant="jarhash", ext="jar"
        )
        self._write_archive(
            "com.example", "dual", "1.0", {"jni/arm64-v8a/libdual.so": aar_data}, variant="aarhash", ext="aar"
        )
        carrier = self._base_carrier(
            "com.example:dual:1.0",
            jar_digest,
            [
                {
                    "path": "com/example/libdual.so",
                    "size_bytes": len(jar_data),
                    "sha256": evidence.sha256_bytes(jar_data),
                    "platform": "Linux",
                    "arch": "x86-64",
                },
                {
                    "path": "jni/arm64-v8a/libdual.so",
                    "size_bytes": len(aar_data),
                    "sha256": evidence.sha256_bytes(aar_data),
                    "platform": "Android",
                    "arch": "arm64-v8a",
                },
            ],
            carrier_kind="JVM .jar + Android .aar",
            # Deliberately wrong additional_artifacts hash for the .aar.
            additional_artifacts=[{"kind": "aar", "artifact_sha256": "e" * 64}],
        )
        gradle_report = self._gradle_report("com.example:dual:1.0")
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError) as ctx:
                evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("wrong/substituted artifact", str(ctx.exception))

    def test_ambiguous_duplicate_resolution_same_extension_different_content_raises(self) -> None:
        # Two different .jar files resolved for the same coordinate+version
        # (different Gradle module-cache hash directories) with genuinely
        # different content -- this generator cannot know which one was
        # actually used to build, so it must refuse rather than guess.
        data_a = self.ELF + b"variant-a"
        data_b = self.ELF + b"variant-b-different-content"
        self._write_archive(
            "com.example", "widget", "1.0", {"libwidget.so": data_a}, variant="hasha", ext="jar"
        )
        self._write_archive(
            "com.example", "widget", "1.0", {"libwidget.so": data_b}, variant="hashb", ext="jar"
        )
        carrier = self._base_carrier(
            "com.example:widget:1.0",
            evidence.sha256_bytes(data_a),
            [{"path": "libwidget.so", "size_bytes": len(data_a), "sha256": evidence.sha256_bytes(data_a), "platform": "Linux", "arch": "x86-64"}],
        )
        gradle_report = self._gradle_report("com.example:widget:1.0")
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError) as ctx:
                evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("ambiguous", str(ctx.exception))

    def test_resolved_extension_with_no_catalog_mapping_raises(self) -> None:
        # Coordinate is catalogued (jar-only), but an .aar is resolved for
        # it with no additional_artifacts entry to verify it against.
        jar_data = self.ELF + b"jar-native-bytes"
        _, jar_digest = self._write_archive(
            "com.example", "widget", "1.0", {"libwidget.so": jar_data}, variant="jarhash", ext="jar"
        )
        self._write_archive(
            "com.example", "widget", "1.0", {"jni/arm64-v8a/libwidget.so": self.ELF + b"aar-bytes"}, variant="aarhash", ext="aar"
        )
        carrier = self._base_carrier(
            "com.example:widget:1.0",
            jar_digest,
            [{"path": "libwidget.so", "size_bytes": len(jar_data), "sha256": evidence.sha256_bytes(jar_data), "platform": "Linux", "arch": "x86-64"}],
        )
        gradle_report = self._gradle_report("com.example:widget:1.0")
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError) as ctx:
                evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("no corresponding artifact_sha256", str(ctx.exception))

    # -- Gap 4: magic-based discovery regardless of filename extension --

    def test_renamed_native_payload_with_misleading_extension_is_discovered(self) -> None:
        # A native payload packaged with a non-native, even Java-like
        # extension must still be discovered via its magic bytes and
        # treated the same as an undeclared native-carrying coordinate.
        self._write_jar(
            "com.example", "sneaky", "1.0", {"payload.class": self.ELF + b"renamed-elf-payload"}
        )
        gradle_report = self._gradle_report("com.example:sneaky:1.0")
        with self.assertRaises(evidence.EvidenceError) as ctx:
            evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("not present in MAVEN_NATIVE_CARRIERS", str(ctx.exception))
        self.assertIn("payload.class", str(ctx.exception))

    def test_known_extension_content_mismatch_fails_generation(self) -> None:
        # A member named like a native library but whose content matches
        # no supported native magic signature at all must fail closed,
        # not be silently accepted (as extension-only detection used to)
        # nor silently skipped.
        self._write_jar(
            "com.example", "mismatched", "1.0", {"libwidget.so": b"not actually native content"}
        )
        gradle_report = self._gradle_report("com.example:mismatched:1.0")
        with self.assertRaises(evidence.EvidenceError) as ctx:
            evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("extension/content mismatch", str(ctx.exception))


class ZipDuplicateMemberKeyTests(unittest.TestCase):
    """`_normalized_zip_member_key()` / `_reject_duplicate_zip_members()`
    unit-level coverage, independent of the full Maven-carrier scan.
    """

    def test_exact_duplicate_name_collides(self) -> None:
        self.assertEqual(
            evidence._normalized_zip_member_key("a/b.txt"), evidence._normalized_zip_member_key("a/b.txt")
        )

    def test_backslash_and_forward_slash_normalize_to_the_same_key(self) -> None:
        self.assertEqual(
            evidence._normalized_zip_member_key("a\\b.txt"), evidence._normalized_zip_member_key("a/b.txt")
        )

    def test_directory_trailing_slash_and_file_normalize_to_the_same_key(self) -> None:
        self.assertEqual(evidence._normalized_zip_member_key("foo/bar/"), evidence._normalized_zip_member_key("foo/bar"))

    def test_case_differs_does_not_normalize_to_the_same_key(self) -> None:
        # Deliberate case-SENSITIVE policy -- see
        # `_normalized_zip_member_key`'s docstring for the rationale.
        self.assertNotEqual(evidence._normalized_zip_member_key("Foo.txt"), evidence._normalized_zip_member_key("foo.txt"))

    def test_reject_duplicate_zip_members_passes_on_all_unique_names(self) -> None:
        import zipfile

        infos = [zipfile.ZipInfo("a.txt"), zipfile.ZipInfo("b.txt"), zipfile.ZipInfo("dir/")]
        evidence._reject_duplicate_zip_members(Path("/fake/archive.jar"), infos)  # no raise

    def test_reject_duplicate_zip_members_raises_on_exact_duplicate(self) -> None:
        import zipfile

        infos = [zipfile.ZipInfo("a.txt"), zipfile.ZipInfo("a.txt")]
        with self.assertRaises(evidence.EvidenceError):
            evidence._reject_duplicate_zip_members(Path("/fake/archive.jar"), infos)

    def test_reject_duplicate_zip_members_raises_on_backslash_variant(self) -> None:
        import zipfile

        infos = [zipfile.ZipInfo("a/b.txt"), zipfile.ZipInfo("a\\b.txt")]
        with self.assertRaises(evidence.EvidenceError):
            evidence._reject_duplicate_zip_members(Path("/fake/archive.jar"), infos)

    def test_reject_duplicate_zip_members_raises_on_directory_file_collision(self) -> None:
        import zipfile

        infos = [zipfile.ZipInfo("foo/bar/"), zipfile.ZipInfo("foo/bar")]
        with self.assertRaises(evidence.EvidenceError):
            evidence._reject_duplicate_zip_members(Path("/fake/archive.jar"), infos)


class ReviewedNonNativeMembersCatalogValidationTests(unittest.TestCase):
    """`_validate_reviewed_non_native_members_catalog()` -- the real
    `REVIEWED_NON_NATIVE_MEMBERS` catalog must pass this at module import
    ("startup"); this exercises the validator directly against
    deliberately-broken catalogs too.
    """

    def test_real_catalog_is_already_valid(self) -> None:
        evidence._validate_reviewed_non_native_members_catalog(evidence.REVIEWED_NON_NATIVE_MEMBERS)  # no raise

    def test_unique_coordinate_and_path_entries_pass(self) -> None:
        entries = (
            {"maven_coordinate": "g:a:1.0", "path": "Foo.bin", "sha256": "a" * 64},
            {"maven_coordinate": "g:a:1.0", "path": "Bar.bin", "sha256": "b" * 64},
            {"maven_coordinate": "g:b:1.0", "path": "Foo.bin", "sha256": "c" * 64},
        )
        evidence._validate_reviewed_non_native_members_catalog(entries)  # no raise

    def test_exact_duplicate_coordinate_and_path_and_hash_raises(self) -> None:
        entries = (
            {"maven_coordinate": "g:a:1.0", "path": "Foo.bin", "sha256": "a" * 64},
            {"maven_coordinate": "g:a:1.0", "path": "Foo.bin", "sha256": "a" * 64},
        )
        with self.assertRaises(evidence.EvidenceError):
            evidence._validate_reviewed_non_native_members_catalog(entries)

    def test_conflicting_hash_for_the_same_coordinate_and_path_raises(self) -> None:
        entries = (
            {"maven_coordinate": "g:a:1.0", "path": "Foo.bin", "sha256": "a" * 64},
            {"maven_coordinate": "g:a:1.0", "path": "Foo.bin", "sha256": "b" * 64},
        )
        with self.assertRaises(evidence.EvidenceError):
            evidence._validate_reviewed_non_native_members_catalog(entries)


class MavenCarrierSchemaValidationTests(unittest.TestCase):
    """Schema checks added to `maven_native_carriers_inventory()` for Gap 7:
    duplicate coordinates/member paths and malformed SHA-256 values."""

    def _base_carrier(self, **overrides) -> dict:
        carrier = {
            "maven_coordinate": "com.example:fake:1.0",
            "carrier_kind": "JVM .jar",
            "license": "MIT",
            "distribution_status": "redistributed_by_kardano",
            "distributed_by_kardano": True,
            "windows_native_available_upstream": False,
            "inspected_2026_08_24": True,
            "artifact_sha256": "0" * 64,
            "primary_artifact_kind": "jar",
            "embedded_natives": [
                {
                    "path": "libfake.so",
                    "size_bytes": 1,
                    "sha256": "0" * 64,
                    "platform": "Linux",
                    "arch": "x86-64",
                }
            ],
            "note": None,
        }
        carrier.update(overrides)
        return carrier

    def test_duplicate_maven_coordinate_raises(self) -> None:
        carriers = (self._base_carrier(), self._base_carrier())
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", carriers):
            with self.assertRaises(evidence.EvidenceError):
                evidence.maven_native_carriers_inventory()

    def test_duplicate_member_path_within_carrier_raises(self) -> None:
        carrier = self._base_carrier(
            embedded_natives=[
                {"path": "libfake.so", "size_bytes": 1, "sha256": "0" * 64, "platform": "Linux", "arch": "x86-64"},
                {"path": "libfake.so", "size_bytes": 2, "sha256": "1" * 64, "platform": "Linux", "arch": "x86-64"},
            ]
        )
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError):
                evidence.maven_native_carriers_inventory()

    def test_malformed_artifact_sha256_raises(self) -> None:
        carrier = self._base_carrier(artifact_sha256="not-a-hash")
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError):
                evidence.maven_native_carriers_inventory()

    def test_malformed_member_sha256_raises(self) -> None:
        carrier = self._base_carrier(
            embedded_natives=[
                {"path": "libfake.so", "size_bytes": 1, "sha256": "TOO-SHORT", "platform": "Linux", "arch": "x86-64"}
            ]
        )
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError):
                evidence.maven_native_carriers_inventory()

    def test_non_positive_member_size_raises(self) -> None:
        carrier = self._base_carrier(
            embedded_natives=[
                {"path": "libfake.so", "size_bytes": 0, "sha256": "0" * 64, "platform": "Linux", "arch": "x86-64"}
            ]
        )
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError):
                evidence.maven_native_carriers_inventory()

    def test_malformed_additional_artifact_sha256_raises(self) -> None:
        carrier = self._base_carrier(
            additional_artifacts=[{"kind": "aar", "artifact_sha256": "nope"}]
        )
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError):
                evidence.maven_native_carriers_inventory()

    def test_missing_primary_artifact_kind_raises(self) -> None:
        carrier = self._base_carrier()
        del carrier["primary_artifact_kind"]
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError) as ctx:
                evidence.maven_native_carriers_inventory()
        self.assertIn("primary_artifact_kind", str(ctx.exception))

    def test_unsupported_primary_artifact_kind_raises(self) -> None:
        carrier = self._base_carrier(primary_artifact_kind="zip")
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError) as ctx:
                evidence.maven_native_carriers_inventory()
        self.assertIn("primary_artifact_kind", str(ctx.exception))

    def test_additional_artifact_kind_duplicating_primary_raises(self) -> None:
        carrier = self._base_carrier(
            primary_artifact_kind="jar",
            additional_artifacts=[{"kind": "jar", "artifact_sha256": "1" * 64}],
        )
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError) as ctx:
                evidence.maven_native_carriers_inventory()
        self.assertIn("duplicates primary_artifact_kind", str(ctx.exception))

    def test_additional_artifact_duplicate_kinds_raises(self) -> None:
        carrier = self._base_carrier(
            primary_artifact_kind="jar",
            additional_artifacts=[
                {"kind": "aar", "artifact_sha256": "1" * 64},
                {"kind": "aar", "artifact_sha256": "2" * 64},
            ],
        )
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError) as ctx:
                evidence.maven_native_carriers_inventory()
        self.assertIn("more than once", str(ctx.exception))

    def test_additional_artifact_unsupported_kind_raises(self) -> None:
        carrier = self._base_carrier(
            additional_artifacts=[{"kind": "war", "artifact_sha256": "1" * 64}]
        )
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError) as ctx:
                evidence.maven_native_carriers_inventory()
        self.assertIn("not one of", str(ctx.exception))


class ColdGradleCacheTests(unittest.TestCase):
    """Prove gradle_license_inventory() needs no pre-populated Gradle cache.

    A 2026-08-24 independent review found the committed
    docs/evidence/gradle_license_inventory.json was only reproducible on a
    machine whose local Gradle module cache already had every coordinate's
    POM resolved -- a clean CI container has none of that. This class points
    GRADLE_USER_HOME at a brand-new empty temporary directory (never ran a
    single Gradle task) and requires byte-identical resolution, proving the
    curated + harvested catalogs (scripts/license_catalog.py,
    scripts/license_catalog_harvested.py) are complete for every coordinate
    in the currently tracked lockfiles, with zero live-cache fallback needed.
    """

    def setUp(self) -> None:
        self.modules = evidence.discover_gradle_modules()
        self._orig_home = evidence.GRADLE_USER_HOME
        self._orig_modules2 = evidence.GRADLE_MODULES2
        self._tmp = tempfile.TemporaryDirectory()
        evidence.GRADLE_USER_HOME = Path(self._tmp.name)
        evidence.GRADLE_MODULES2 = evidence.GRADLE_USER_HOME / "caches" / "modules-2" / "files-2.1"

    def tearDown(self) -> None:
        evidence.GRADLE_USER_HOME = self._orig_home
        evidence.GRADLE_MODULES2 = self._orig_modules2
        self._tmp.cleanup()

    def test_cold_cache_resolves_every_coordinate(self) -> None:
        self.assertFalse(evidence.GRADLE_MODULES2.exists())
        gradle_report = evidence.gradle_dependency_inventory(self.modules)
        report = evidence.gradle_license_inventory(gradle_report)
        self.assertEqual(report["unresolved_count"], 0)
        self.assertEqual(report["unresolved"], [])
        self.assertEqual(report["resolved_count"], report["runtime_coordinate_count"])
        self.assertGreater(report["resolved_count"], 250)

    def test_cold_cache_output_matches_warm_cache_output_byte_for_byte(self) -> None:
        gradle_report = evidence.gradle_dependency_inventory(self.modules)
        cold = json.dumps(evidence.gradle_license_inventory(gradle_report), sort_keys=True)

        evidence.GRADLE_USER_HOME = self._orig_home
        evidence.GRADLE_MODULES2 = self._orig_modules2
        warm = json.dumps(evidence.gradle_license_inventory(gradle_report), sort_keys=True)
        self.assertEqual(cold, warm)

    def test_cold_cache_raises_if_a_new_coordinate_is_uncataloged(self) -> None:
        gradle_report = {
            "modules": {
                "fake": {
                    "coordinates": {"runtime": ["com.example.brand-new:widget:9.9.9"]},
                }
            }
        }
        with self.assertRaises(evidence.EvidenceError):
            evidence.gradle_license_inventory(gradle_report)


class ScopeBindingSealTests(unittest.TestCase):
    """Exercise seal_scope_binding() against a disposable temp git repo.

    A real seal always runs against THIS repository's actual history; these
    tests instead build a minimal two-commit history from scratch (subject
    commit, then evidence commit) in an isolated temp git repo, so the
    various failure modes (dirty tree, already sealed, missing file, no
    parent commit) can be exercised without touching real git state.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"], cwd=self.repo, check=True
        )
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True)

        self._orig_repo_root = evidence.REPO_ROOT
        self._orig_evidence_dir = evidence.EVIDENCE_DIR
        evidence.REPO_ROOT = self.repo
        evidence.EVIDENCE_DIR = self.repo / "docs" / "evidence"
        evidence.EVIDENCE_DIR.mkdir(parents=True)

    def tearDown(self) -> None:
        evidence.REPO_ROOT = self._orig_repo_root
        evidence.EVIDENCE_DIR = self._orig_evidence_dir
        self._tmp.cleanup()

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=self.repo, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()

    def _write_outputs(self) -> None:
        for name in evidence.evidence_output_files():
            (evidence.EVIDENCE_DIR / name).write_text(
                json.dumps({"name": name}) + "\n", encoding="utf-8"
            )

    def _commit_subject(self) -> str:
        (self.repo / "SOURCE.txt").write_text("subject source\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "subject commit")
        return self._git("rev-parse", "HEAD")

    def _commit_evidence(self) -> str:
        self._write_outputs()
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "evidence commit")
        return self._git("rev-parse", "HEAD")

    def test_seal_binds_evidence_commit_to_its_immediate_parent(self) -> None:
        subject_commit = self._commit_subject()
        evidence_commit = self._commit_evidence()
        binding = evidence.seal_scope_binding()
        self.assertEqual(binding["evidence_commit"], evidence_commit)
        self.assertEqual(binding["subject_commit"], subject_commit)
        self.assertEqual(
            set(binding["sealed_evidence_digests"]), set(evidence.evidence_output_files())
        )

    def test_seal_raises_on_dirty_worktree(self) -> None:
        self._commit_subject()
        self._commit_evidence()
        any_output = next(iter(evidence.evidence_output_files()))
        (evidence.EVIDENCE_DIR / any_output).write_text("dirty\n", encoding="utf-8")
        with self.assertRaises(evidence.EvidenceError):
            evidence.seal_scope_binding()

    def test_seal_raises_if_already_sealed(self) -> None:
        self._commit_subject()
        self._commit_evidence()
        (evidence.EVIDENCE_DIR / "scope_binding.json").write_text("{}\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "already sealed")
        with self.assertRaises(evidence.EvidenceError):
            evidence.seal_scope_binding()

    def test_seal_raises_if_an_evidence_file_is_missing(self) -> None:
        self._commit_subject()
        self._write_outputs()
        first = next(iter(evidence.evidence_output_files()))
        (evidence.EVIDENCE_DIR / first).unlink()
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "evidence commit missing one file")
        with self.assertRaises(evidence.EvidenceError):
            evidence.seal_scope_binding()

    def test_seal_raises_on_repo_root_commit_with_no_parent(self) -> None:
        # The evidence commit IS the repo's first commit -- no subject commit
        # exists to bind to.
        self._write_outputs()
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "only commit")
        with self.assertRaises(evidence.EvidenceError):
            evidence.seal_scope_binding()


class OutputsIncludingExistingScopeBindingTests(unittest.TestCase):
    """A plain (non---seal) regeneration against an already-sealed worktree
    must not lose LEGAL_EVIDENCE_DIGEST.txt's scope_binding.json_sha256 line
    (see evidence_output_files()'s docstring and run_generate())."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_evidence_dir = evidence.EVIDENCE_DIR
        evidence.EVIDENCE_DIR = Path(self._tmp.name)
        self.outputs = {"gradle_dependency_inventory.json": evidence.EVIDENCE_DIR / "gdi.json"}

    def tearDown(self) -> None:
        evidence.EVIDENCE_DIR = self._orig_evidence_dir
        self._tmp.cleanup()

    def test_unsealed_worktree_returns_outputs_unchanged(self) -> None:
        merged = evidence.outputs_including_existing_scope_binding(self.outputs)
        self.assertIs(merged, self.outputs)
        self.assertNotIn("scope_binding.json", merged)

    def test_sealed_worktree_adds_scope_binding_without_mutating_input(self) -> None:
        (evidence.EVIDENCE_DIR / "scope_binding.json").write_text("{}\n", encoding="utf-8")
        merged = evidence.outputs_including_existing_scope_binding(self.outputs)
        self.assertIsNot(merged, self.outputs)
        self.assertNotIn("scope_binding.json", self.outputs)
        self.assertEqual(merged["scope_binding.json"], evidence.EVIDENCE_DIR / "scope_binding.json")
        self.assertEqual(merged["gradle_dependency_inventory.json"], self.outputs["gradle_dependency_inventory.json"])


if __name__ == "__main__":
    unittest.main()
