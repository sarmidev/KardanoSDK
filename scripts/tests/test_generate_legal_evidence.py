"""Coverage tests for scripts/generate_legal_evidence.py."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

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
            evidence.scope_binding(),
        ):
            text = json.dumps(report)
            self.assertNotIn(absolute_marker, text)
            self.assertNotIn(str(Path.home()), text)


if __name__ == "__main__":
    unittest.main()
