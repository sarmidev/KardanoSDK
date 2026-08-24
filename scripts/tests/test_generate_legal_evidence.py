"""Coverage tests for scripts/generate_legal_evidence.py."""

from __future__ import annotations

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


class NativeMemberDetectionTests(unittest.TestCase):
    """`_looks_like_native_member()` extension/magic-byte classification."""

    def test_extension_match_is_native_regardless_of_content(self) -> None:
        self.assertTrue(evidence._looks_like_native_member("libfoo.so", b"not really elf"))
        self.assertTrue(evidence._looks_like_native_member("jni/x86/libfoo.so", b""))
        self.assertTrue(evidence._looks_like_native_member("foo.dylib", b""))
        self.assertTrue(evidence._looks_like_native_member("foo.dll", b""))
        self.assertTrue(evidence._looks_like_native_member("foo.jnilib", b""))
        self.assertTrue(evidence._looks_like_native_member("foo.a", b""))

    def test_java_class_file_cafebabe_magic_is_not_native(self) -> None:
        # Regression test: a Java .class file's own magic number (CAFEBABE)
        # is byte-identical to a Mach-O universal/fat binary's magic number.
        # A real bug this generator was found to have: scanning
        # androidx.annotation:annotation-jvm (a pure-Kotlin/Java artifact,
        # zero native code) reported 75 ".class" members as "native".
        self.assertFalse(
            evidence._looks_like_native_member(
                "androidx/annotation/NonNull.class", b"\xca\xfe\xba\xbe\x00\x00\x00\x41"
            )
        )

    def test_extensionless_member_with_elf_magic_is_native(self) -> None:
        self.assertTrue(evidence._looks_like_native_member("payload", b"\x7fELF\x02\x01\x01\x00"))

    def test_extensionless_member_with_pe_magic_is_native(self) -> None:
        self.assertTrue(evidence._looks_like_native_member("payload", b"MZ\x90\x00"))

    def test_extensionless_member_without_native_magic_is_not_native(self) -> None:
        self.assertFalse(evidence._looks_like_native_member("README", b"just text here"))

    def test_member_with_unrelated_extension_and_native_magic_is_not_native(self) -> None:
        # An extension that IS recognized (even if not a native one) is
        # authoritative -- magic sniffing is only a backstop for members
        # with NO extension at all.
        self.assertFalse(
            evidence._looks_like_native_member("payload.txt", b"\x7fELF\x02\x01\x01\x00")
        )


class NativeCarrierDynamicDiscoveryTests(unittest.TestCase):
    """`cross_check_maven_native_carriers_against_local_cache()` -- Gap 7.

    Builds a disposable, synthetic Gradle module cache (never a real
    download) so every failure mode can be exercised deterministically:
    a brand-new native-carrying coordinate absent from the catalog, an
    unreviewed extra/missing member on an already-catalogued coordinate,
    a member hash/size drift, a duplicate member path within one archive,
    and the cold-cache (nothing found) no-op case.
    """

    def setUp(self) -> None:
        self._orig_modules2 = evidence.GRADLE_MODULES2
        self._tmp = tempfile.TemporaryDirectory()
        evidence.GRADLE_MODULES2 = Path(self._tmp.name)

    def tearDown(self) -> None:
        evidence.GRADLE_MODULES2 = self._orig_modules2
        self._tmp.cleanup()

    def _write_jar(self, group: str, artifact: str, version: str, members: dict[str, bytes]) -> Path:
        import zipfile

        base = evidence.GRADLE_MODULES2 / group / artifact / version / "deadbeef"
        base.mkdir(parents=True, exist_ok=True)
        jar_path = base / f"{artifact}-{version}.jar"
        with zipfile.ZipFile(jar_path, "w") as zf:
            for name, data in members.items():
                zf.writestr(name, data)
        return jar_path

    def _gradle_report(self, gav: str) -> dict:
        return {"modules": {"fake": {"coordinates": {"runtime": [gav]}}}}

    def test_cold_cache_is_a_no_op(self) -> None:
        gradle_report = self._gradle_report("com.example:nowhere:1.0")
        evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)  # no raise

    def test_new_native_carrying_coordinate_not_in_catalog_raises(self) -> None:
        self._write_jar("com.example", "widget", "1.0", {"libwidget.so": b"fake-elf-bytes"})
        gradle_report = self._gradle_report("com.example:widget:1.0")
        with self.assertRaises(evidence.EvidenceError) as ctx:
            evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("not present in MAVEN_NATIVE_CARRIERS", str(ctx.exception))

    def test_matching_catalog_entry_passes(self) -> None:
        data = b"fake-elf-bytes"
        digest = evidence.sha256_bytes(data)
        self._write_jar("com.example", "widget", "1.0", {"libwidget.so": data})
        carrier = {
            "maven_coordinate": "com.example:widget:1.0",
            "carrier_kind": "JVM .jar",
            "license": "MIT",
            "distribution_status": "redistributed_by_kardano",
            "distributed_by_kardano": True,
            "windows_native_available_upstream": False,
            "inspected_2026_08_24": True,
            "artifact_sha256": "0" * 64,
            "embedded_natives": [
                {
                    "path": "libwidget.so",
                    "size_bytes": len(data),
                    "sha256": digest,
                    "platform": "Linux",
                    "arch": "x86-64",
                }
            ],
            "note": None,
        }
        gradle_report = self._gradle_report("com.example:widget:1.0")
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)  # no raise

    def test_extra_undeclared_member_on_known_carrier_raises(self) -> None:
        data = b"fake-elf-bytes"
        digest = evidence.sha256_bytes(data)
        self._write_jar(
            "com.example",
            "widget",
            "1.0",
            {"libwidget.so": data, "libextra.so": b"a-second-native-blob"},
        )
        carrier = {
            "maven_coordinate": "com.example:widget:1.0",
            "carrier_kind": "JVM .jar",
            "license": "MIT",
            "distribution_status": "redistributed_by_kardano",
            "distributed_by_kardano": True,
            "windows_native_available_upstream": False,
            "inspected_2026_08_24": True,
            "artifact_sha256": "0" * 64,
            "embedded_natives": [
                {
                    "path": "libwidget.so",
                    "size_bytes": len(data),
                    "sha256": digest,
                    "platform": "Linux",
                    "arch": "x86-64",
                }
            ],
            "note": None,
        }
        gradle_report = self._gradle_report("com.example:widget:1.0")
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError) as ctx:
                evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("unreviewed native member path", str(ctx.exception))

    def test_missing_catalogued_member_raises(self) -> None:
        # Catalog declares a member the actual archive no longer contains.
        self._write_jar("com.example", "widget", "1.0", {"libwidget.so": b"fake-elf-bytes"})
        carrier = {
            "maven_coordinate": "com.example:widget:1.0",
            "carrier_kind": "JVM .jar",
            "license": "MIT",
            "distribution_status": "redistributed_by_kardano",
            "distributed_by_kardano": True,
            "windows_native_available_upstream": False,
            "inspected_2026_08_24": True,
            "artifact_sha256": "0" * 64,
            "embedded_natives": [
                {
                    "path": "libwidget.so",
                    "size_bytes": 14,
                    "sha256": evidence.sha256_bytes(b"fake-elf-bytes"),
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
            "note": None,
        }
        gradle_report = self._gradle_report("com.example:widget:1.0")
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError) as ctx:
                evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("no longer contain", str(ctx.exception))

    def test_hash_drift_on_known_member_raises(self) -> None:
        self._write_jar("com.example", "widget", "1.0", {"libwidget.so": b"fake-elf-bytes"})
        carrier = {
            "maven_coordinate": "com.example:widget:1.0",
            "carrier_kind": "JVM .jar",
            "license": "MIT",
            "distribution_status": "redistributed_by_kardano",
            "distributed_by_kardano": True,
            "windows_native_available_upstream": False,
            "inspected_2026_08_24": True,
            "artifact_sha256": "0" * 64,
            "embedded_natives": [
                {
                    "path": "libwidget.so",
                    "size_bytes": len(b"fake-elf-bytes"),
                    "sha256": "9" * 64,
                    "platform": "Linux",
                    "arch": "x86-64",
                }
            ],
            "note": None,
        }
        gradle_report = self._gradle_report("com.example:widget:1.0")
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            with self.assertRaises(evidence.EvidenceError) as ctx:
                evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("archive/hash drift", str(ctx.exception))

    def test_size_drift_on_known_member_raises(self) -> None:
        data = b"fake-elf-bytes"
        self._write_jar("com.example", "widget", "1.0", {"libwidget.so": data})
        carrier = {
            "maven_coordinate": "com.example:widget:1.0",
            "carrier_kind": "JVM .jar",
            "license": "MIT",
            "distribution_status": "redistributed_by_kardano",
            "distributed_by_kardano": True,
            "windows_native_available_upstream": False,
            "inspected_2026_08_24": True,
            "artifact_sha256": "0" * 64,
            "embedded_natives": [
                {
                    "path": "libwidget.so",
                    "size_bytes": len(data) + 1,
                    "sha256": evidence.sha256_bytes(data),
                    "platform": "Linux",
                    "arch": "x86-64",
                }
            ],
            "note": None,
        }
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
            zf.writestr("libwidget.so", b"first-copy")
            zf.writestr("libwidget.so", b"second-copy-different-bytes")
        gradle_report = self._gradle_report("com.example:widget:1.0")
        with self.assertRaises(evidence.EvidenceError) as ctx:
            evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)
        self.assertIn("duplicate native", str(ctx.exception))

    def test_false_extension_and_magic_does_not_trigger_a_false_positive(self) -> None:
        # A jar full of ordinary .class files (CAFEBABE magic, colliding
        # with Mach-O fat-binary magic) must not be reported as carrying
        # native members at all.
        self._write_jar(
            "com.example",
            "puretype",
            "1.0",
            {"com/example/Foo.class": b"\xca\xfe\xba\xbe\x00\x00\x00\x41rest-of-classfile"},
        )
        gradle_report = self._gradle_report("com.example:puretype:1.0")
        evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)  # no raise

    def test_two_artifacts_same_coordinate_merge_without_conflict(self) -> None:
        # Mirrors JNA 5.19.1's real shape: a .jar AND a separate .aar for
        # the exact same coordinate, each carrying disjoint native paths.
        jar_data = b"jar-native-bytes"
        aar_data = b"aar-native-bytes"
        base = evidence.GRADLE_MODULES2 / "com.example" / "dual" / "1.0"
        (base / "jarhash").mkdir(parents=True)
        (base / "aarhash").mkdir(parents=True)
        import zipfile

        with zipfile.ZipFile(base / "jarhash" / "dual-1.0.jar", "w") as zf:
            zf.writestr("com/example/libdual.so", jar_data)
        with zipfile.ZipFile(base / "aarhash" / "dual-1.0.aar", "w") as zf:
            zf.writestr("jni/arm64-v8a/libdual.so", aar_data)
        carrier = {
            "maven_coordinate": "com.example:dual:1.0",
            "carrier_kind": "JVM .jar + Android .aar",
            "license": "MIT",
            "distribution_status": "redistributed_by_kardano",
            "distributed_by_kardano": True,
            "windows_native_available_upstream": False,
            "inspected_2026_08_24": True,
            "artifact_sha256": "0" * 64,
            "embedded_natives": [
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
            "note": None,
        }
        gradle_report = self._gradle_report("com.example:dual:1.0")
        with mock.patch.object(evidence, "MAVEN_NATIVE_CARRIERS", (carrier,)):
            evidence.cross_check_maven_native_carriers_against_local_cache(gradle_report)  # no raise


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
