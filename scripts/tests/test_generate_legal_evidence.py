"""Coverage tests for scripts/generate_legal_evidence.py."""

from __future__ import annotations

import json
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


class ChecksumsParsingTests(unittest.TestCase):
    def test_parse_checksums_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            checksums = Path(tmp) / "CHECKSUMS.sha256"
            checksums.write_text(
                "deadbeef  src/a/b.so\n"
                "cafef00d  src/c/d.a\n",
                encoding="utf-8",
            )
            rows = evidence.parse_checksums(checksums)
            self.assertEqual(rows, {"src/a/b.so": "deadbeef", "src/c/d.a": "cafef00d"})

    def test_malformed_line_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            checksums = Path(tmp) / "CHECKSUMS.sha256"
            checksums.write_text("not-a-valid-line\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                evidence.parse_checksums(checksums)


class RealTreeGenerationTests(unittest.TestCase):
    """Exercise the generators against the real repository tree."""

    def test_gradle_inventory_has_no_unclassified_coordinates(self) -> None:
        report = evidence.gradle_dependency_inventory()
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

    def test_cargo_inventory_runs_locked(self) -> None:
        report = evidence.cargo_dependency_inventory()
        self.assertGreater(report["package_count"], 0)
        self.assertEqual(report["root_package"]["name"], "kardano-ed25519-bip32-signing")

    def test_uniffi_bindings_inventory_lists_committed_files(self) -> None:
        report = evidence.uniffi_bindings_inventory()
        self.assertEqual(len(report["generated_files"]), len(evidence.UNIFFI_BINDING_FILES))

    def test_generation_is_deterministic_across_two_runs(self) -> None:
        first = json.dumps(evidence.gradle_dependency_inventory(), sort_keys=True)
        second = json.dumps(evidence.gradle_dependency_inventory(), sort_keys=True)
        self.assertEqual(first, second)

        first_cargo = json.dumps(evidence.cargo_dependency_inventory(), sort_keys=True)
        second_cargo = json.dumps(evidence.cargo_dependency_inventory(), sort_keys=True)
        self.assertEqual(first_cargo, second_cargo)

    def test_no_generated_json_contains_repo_absolute_path(self) -> None:
        absolute_marker = str(REPO_ROOT)
        for report in (
            evidence.gradle_dependency_inventory(),
            evidence.cargo_dependency_inventory(),
            evidence.uniffi_bindings_inventory(),
            evidence.native_artifacts_inventory(),
            evidence.maven_native_carriers_inventory(),
        ):
            text = json.dumps(report)
            self.assertNotIn(absolute_marker, text)


if __name__ == "__main__":
    unittest.main()
