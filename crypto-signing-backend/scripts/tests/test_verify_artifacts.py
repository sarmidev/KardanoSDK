"""Unit tests for staged-vs-committed native artifact comparison."""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import native_artifacts as natives  # noqa: E402
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "verify_artifacts_cli",
    SCRIPT_DIR / "verify-artifacts.py",
)
assert _spec is not None and _spec.loader is not None
verify_cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify_cli)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _checksums(rows: dict[str, bytes]) -> str:
    lines = [f"{_sha(payload)}  {relative}" for relative, payload in rows.items()]
    return "\n".join(lines) + "\n"


class ParseChecksumsTests(unittest.TestCase):
    def test_parses_two_rows(self) -> None:
        rows = natives.parse_checksums(
            "aa" * 32 + "  src/a.so\n" + "bb" * 32 + "  src/b.so\n"
        )
        self.assertEqual(rows["src/a.so"], "aa" * 32)
        self.assertEqual(rows["src/b.so"], "bb" * 32)

    def test_rejects_malformed_line(self) -> None:
        with self.assertRaises(ValueError):
            natives.parse_checksums("not-a-digest  src/a.so\n")


class LinuxCatalogTests(unittest.TestCase):
    def test_linux_is_in_the_promoted_catalog(self) -> None:
        linux = natives.LINUX_JVM_ARTIFACTS[0]
        self.assertEqual(linux.group, "linux-jvm")
        self.assertEqual(
            linux.relative_path,
            "src/jvmMain/resources/linux-x86-64/libkardano_ed25519_bip32_signing.so",
        )
        self.assertIn(linux, natives.EXISTING_ARTIFACTS)
        self.assertEqual(
            [spec.artifact_id for spec in natives.artifacts_for_groups(("linux-jvm",))],
            ["linux-jvm-x86_64"],
        )
        self.assertEqual(len(natives.EXISTING_ARTIFACTS), 9)


class ManifestCoverageTests(unittest.TestCase):
    def test_missing_catalog_row_is_a_finding(self) -> None:
        checksums = {
            spec.relative_path: "ab" * 32
            for spec in natives.EXISTING_ARTIFACTS
            if spec.artifact_id != "ios-arm64"
        }
        findings = natives.check_manifest_coverage(checksums)
        kinds = {item.kind for item in findings}
        self.assertIn("missing-manifest", kinds)
        self.assertTrue(any(item.artifact_id == "ios-arm64" for item in findings))

    def test_extra_checksums_row_is_a_finding(self) -> None:
        checksums = {
            spec.relative_path: "ab" * 32 for spec in natives.EXISTING_ARTIFACTS
        }
        checksums["src/unexpected-extra.so"] = "cd" * 32
        findings = natives.check_manifest_coverage(checksums)
        self.assertTrue(any(item.kind == "extra-manifest" for item in findings))

    def test_complete_manifest_has_no_coverage_findings(self) -> None:
        checksums = {
            spec.relative_path: "ab" * 32 for spec in natives.EXISTING_ARTIFACTS
        }
        self.assertEqual(natives.check_manifest_coverage(checksums), [])


class CompareTreeTests(unittest.TestCase):
    def _tree(self, payloads: dict[str, bytes]) -> tuple[Path, Path]:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        committed = root / "committed"
        staged = root / "staged"
        for relative, data in payloads.items():
            _write(committed / relative, data)
            _write(staged / relative, data)
        (committed / natives.CHECKSUMS_NAME).write_text(_checksums(payloads), encoding="utf-8")
        return committed, staged

    def _payloads(self) -> dict[str, bytes]:
        return {
            spec.relative_path: f"{spec.artifact_id}\n".encode("ascii")
            for spec in natives.EXISTING_ARTIFACTS
        }

    def test_identical_trees_pass(self) -> None:
        payloads = self._payloads()
        committed, staged = self._tree(payloads)
        findings, _, _ = natives.compare_trees(
            committed, staged, require_inspection=False
        )
        leftover = [item for item in findings if item.kind not in {"missing-symbol", "arch-mismatch"}]
        self.assertEqual(leftover, [], "\n".join(item.format() for item in leftover))

    def test_missing_staged_binary_is_a_finding(self) -> None:
        payloads = self._payloads()
        committed, staged = self._tree(payloads)
        missing = natives.ARTIFACT_BY_ID["macos-jvm-arm64"].relative_path
        (staged / missing).unlink()
        findings, _, _ = natives.compare_trees(
            committed, staged, require_inspection=False
        )
        self.assertTrue(
            any(
                item.kind == "missing-staged" and item.artifact_id == "macos-jvm-arm64"
                for item in findings
            ),
            "\n".join(item.format() for item in findings),
        )

    def test_extra_staged_binary_is_a_finding(self) -> None:
        payloads = self._payloads()
        committed, staged = self._tree(payloads)
        extra = staged / "src/jvmMain/resources/unexpected/libkardano_ed25519_bip32_signing.so"
        _write(extra, b"extra\n")
        findings, _, _ = natives.compare_trees(
            committed, staged, require_inspection=False
        )
        self.assertTrue(
            any(item.kind == "extra-staged" for item in findings),
            "\n".join(item.format() for item in findings),
        )

    def test_mismatched_bytes_are_a_finding(self) -> None:
        payloads = self._payloads()
        committed, staged = self._tree(payloads)
        relative = natives.ARTIFACT_BY_ID["android-x86"].relative_path
        (staged / relative).write_bytes(b"different-bytes\n")
        findings, _, _ = natives.compare_trees(
            committed, staged, require_inspection=False
        )
        self.assertTrue(
            any(
                item.kind == "byte-mismatch" and item.artifact_id == "android-x86"
                for item in findings
            ),
            "\n".join(item.format() for item in findings),
        )

    def test_first_differing_byte_reports_offset(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        left = root / "left.bin"
        right = root / "right.bin"
        left.write_bytes(b"AAAABBBB")
        right.write_bytes(b"AAAACBBB")
        diff = natives.first_differing_byte(left, right)
        assert diff is not None
        self.assertEqual(diff["offset"], 4)
        self.assertEqual(diff["committed"], "42")
        self.assertEqual(diff["staged"], "43")

    def test_difference_clusters_report_every_range(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        left = root / "left.bin"
        right = root / "right.bin"
        left.write_bytes(b"AAAABBBBCCCC")
        right.write_bytes(b"AAAAxBBByCCC")
        clusters = natives.difference_clusters(left, right)
        self.assertEqual(
            [(item["offset"], item["length"]) for item in clusters],
            [(4, 1), (8, 1)],
        )

    def test_cli_exits_nonzero_on_mismatch(self) -> None:
        payloads = self._payloads()
        committed, staged = self._tree(payloads)
        relative = natives.ARTIFACT_BY_ID["ios-arm64"].relative_path
        (staged / relative).write_bytes(b"nope\n")
        rc = verify_cli.main(
            [
                "--module-root",
                str(committed),
                "--staging",
                str(staged),
                "--skip-inspection",
            ]
        )
        self.assertEqual(rc, 1)


class CurrentCommittedManifestTests(unittest.TestCase):
    def test_module_checksums_cover_the_catalog(self) -> None:
        checksums = natives.load_checksums(natives.MODULE_ROOT)
        self.assertEqual(natives.check_manifest_coverage(checksums), [])
        for spec in natives.EXISTING_ARTIFACTS:
            path = natives.MODULE_ROOT / spec.relative_path
            self.assertTrue(path.is_file(), spec.relative_path)
            self.assertEqual(natives.sha256_file(path), checksums[spec.relative_path])


if __name__ == "__main__":
    unittest.main()
