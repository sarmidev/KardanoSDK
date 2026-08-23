"""Adversarial tests for fail-closed native rebuild inspection and staging rules."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import native_artifacts as natives  # noqa: E402
import native_toolchain as toolchain  # noqa: E402
import rebuild_into_staging as rebuild  # noqa: E402


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class _Proc:
    def __init__(self, rc: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = rc
        self.stdout = stdout
        self.stderr = stderr


class ScriptedHooks(natives.InspectHooks):
    def __init__(
        self,
        which_map: dict[str, str | None],
        results: dict[str, _Proc],
    ) -> None:
        self.which_map = which_map
        self.results = results
        self.which = self._which
        self.run = self._run
        self.llvm_nm = which_map.get("llvm-nm")

    def _which(self, name: str) -> str | None:
        if name in self.which_map:
            return self.which_map[name]
        return None

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        tool = Path(command[0]).name
        result = self.results.get(tool)
        if result is None:
            result = _Proc(1, "", f"no scripted result for {tool}")
        return subprocess.CompletedProcess(command, result.returncode, result.stdout, result.stderr)


def _dylib_hooks(*, nm_rc: int = 0, nm_out: str | None = None, arch: str = "arm64", install: str | None = None) -> ScriptedHooks:
    symbol = natives.SIGN_SYMBOL if nm_out is None else nm_out
    install = install or toolchain.STABLE_INSTALL_NAME
    return ScriptedHooks(
        {
            "file": "/usr/bin/file",
            "lipo": "/usr/bin/lipo",
            "otool": "/usr/bin/otool",
            "nm": "/usr/bin/nm",
            "llvm-nm": None,
        },
        {
            "file": _Proc(0, f"Mach-O 64-bit dynamically linked shared library {arch}\n"),
            "lipo": _Proc(0, f"Non-fat file: lib.dylib is architecture: {arch}\n"),
            "otool": _Proc(
                0,
                "cmd LC_ID_DYLIB\n"
                f"  name {install} (offset 24)\n"
                "cmd LC_UUID\n"
                "  uuid DEAD-BEEF\n"
                "cmd LC_BUILD_VERSION\n"
                "  sdk 26.5\n"
                "  minos 26.0\n",
            ),
            "nm": _Proc(nm_rc, f"00000000 T _{symbol}\n" if nm_rc == 0 else "", "nm failed\n"),
        },
    )


class StagingRulesTests(unittest.TestCase):
    def test_dirty_cargo_target_is_rejected(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        staging = root / "staging"
        staging.mkdir()
        dirty = staging / "cargo-target"
        dirty.mkdir()
        (dirty / "leftover").write_text("nope\n", encoding="utf-8")
        with self.assertRaises(rebuild.RebuildError) as raised:
            rebuild.resolve_cargo_target_dir(staging, root / "module", dirty)
        self.assertIn("not empty", str(raised.exception))

    def test_module_target_is_rejected(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        staging = root / "staging"
        staging.mkdir()
        module = root / "module"
        (module / "target").mkdir(parents=True)
        with self.assertRaises(rebuild.RebuildError) as raised:
            rebuild.resolve_cargo_target_dir(staging, module, module / "target")
        self.assertIn("module target", str(raised.exception))

    def test_cargo_target_outside_staging_is_rejected(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        staging = root / "staging"
        staging.mkdir()
        outside = root / "elsewhere"
        with self.assertRaises(rebuild.RebuildError) as raised:
            rebuild.resolve_cargo_target_dir(staging, root / "module", outside)
        self.assertIn("inside staging", str(raised.exception))

    def test_stale_output_is_rejected(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        src = root / "lib.dylib"
        src.write_bytes(b"old-bytes")
        past = time.time() - 3600
        __import__("os").utime(src, (past, past))
        with self.assertRaises(rebuild.RebuildError) as raised:
            rebuild.copy_fresh_output(
                src,
                root / "staging",
                "src/jvmMain/resources/darwin-aarch64/libkardano_ed25519_bip32_signing.dylib",
                started_monotonic=time.monotonic(),
            )
        self.assertIn("stale cargo output", str(raised.exception))

    def test_missing_output_is_rejected(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        with self.assertRaises(rebuild.RebuildError) as raised:
            rebuild.copy_fresh_output(
                root / "missing.dylib",
                root / "staging",
                "src/a.dylib",
                started_monotonic=time.monotonic(),
            )
        self.assertIn("missing", str(raised.exception))


class FailClosedInspectionTests(unittest.TestCase):
    def test_missing_nm_is_a_finding(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        path = root / "lib.dylib"
        path.write_bytes(b"not-a-real-dylib")
        hooks = ScriptedHooks({"file": "/usr/bin/file", "lipo": "/usr/bin/lipo", "otool": "/usr/bin/otool"}, {
            "file": _Proc(0, "Mach-O 64-bit dynamically linked shared library arm64\n"),
            "lipo": _Proc(0, "Non-fat file: lib.dylib is architecture: arm64\n"),
            "otool": _Proc(0, "cmd LC_ID_DYLIB\n  name @rpath/libkardano_ed25519_bip32_signing.dylib (offset 24)\n"),
        })
        spec = natives.ARTIFACT_BY_ID["macos-jvm-arm64"]
        record = natives.inspect_artifact(spec, path, hooks=hooks)
        self.assertTrue(any("nm/llvm-nm is required" in item for item in record.inspection_errors))

    def test_nonzero_nm_is_a_finding(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        path = root / "lib.dylib"
        path.write_bytes(b"dylib")
        spec = natives.ARTIFACT_BY_ID["macos-jvm-arm64"]
        record = natives.inspect_artifact(spec, path, hooks=_dylib_hooks(nm_rc=1))
        self.assertTrue(any("nm exited 1" in item for item in record.inspection_errors))

    def test_wrong_arch_is_a_finding(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        path = root / "lib.dylib"
        path.write_bytes(b"dylib")
        spec = natives.ARTIFACT_BY_ID["macos-jvm-arm64"]
        record = natives.inspect_artifact(spec, path, hooks=_dylib_hooks(arch="x86_64"))
        self.assertFalse(record.arch_ok)
        self.assertTrue(any("architecture" in item for item in record.inspection_errors))

    def test_wrong_symbol_is_a_finding(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        path = root / "lib.dylib"
        path.write_bytes(b"dylib")
        spec = natives.ARTIFACT_BY_ID["macos-jvm-arm64"]
        record = natives.inspect_artifact(spec, path, hooks=_dylib_hooks(nm_out="something_else"))
        self.assertFalse(record.symbol_ok)

    def test_wrong_install_name_is_a_finding(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        path = root / "lib.dylib"
        path.write_bytes(b"dylib")
        spec = natives.ARTIFACT_BY_ID["macos-jvm-arm64"]
        record = natives.inspect_artifact(
            spec,
            path,
            hooks=_dylib_hooks(install="/Users/host/target/release/libkardano_ed25519_bip32_signing.dylib"),
        )
        self.assertFalse(record.install_name_ok)

    def test_compare_reports_install_name_and_symbol(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        committed = root / "committed"
        staged = root / "staged"
        payloads = {
            spec.relative_path: f"{spec.artifact_id}\n".encode("ascii")
            for spec in natives.EXISTING_ARTIFACTS
        }
        checksum_lines = []
        for relative, data in payloads.items():
            _write(committed / relative, data)
            _write(staged / relative, data)
            checksum_lines.append(f"{natives.sha256_file(committed / relative)}  {relative}")
        (committed / natives.CHECKSUMS_NAME).write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
        hooks = _dylib_hooks(install="/tmp/wrong.dylib", nm_out="nope")
        findings, _, _ = natives.compare_trees(
            committed,
            staged,
            require_inspection=True,
            hooks=hooks,
            groups=("macos-jvm",),
        )
        kinds = {item.kind for item in findings}
        self.assertIn("install-name-mismatch", kinds)
        self.assertIn("missing-symbol", kinds)


class EvidenceAndManifestTests(unittest.TestCase):
    def test_missing_evidence_and_logs_are_findings(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        findings = natives.check_evidence_dir(
            root / "missing-evidence",
            groups=("macos-jvm",),
            logs_dir=root / "missing-logs",
        )
        kinds = {item.kind for item in findings}
        self.assertIn("missing-evidence", kinds)

    def test_empty_logs_directory_is_a_finding(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        evidence = root / "evidence"
        evidence.mkdir()
        spec = natives.ARTIFACT_BY_ID["macos-jvm-arm64"]
        for name in natives.required_evidence_names(spec):
            payload = "" if name.endswith(".path-scan.txt") else "x\n"
            (evidence / name).write_text(payload, encoding="utf-8")
        logs = root / "logs"
        logs.mkdir()
        findings = natives.check_evidence_dir(evidence, groups=("macos-jvm",), logs_dir=logs)
        self.assertTrue(any(item.kind == "missing-log" for item in findings))

    def test_candidate_manifest_mismatch_and_extra_file(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        committed = root / "committed"
        staged = root / "staged"
        spec = natives.ARTIFACT_BY_ID["android-x86"]
        _write(staged / spec.relative_path, b"candidate-a\n")
        extra = staged / "src/jvmMain/resources/linux-x86-64/libkardano_ed25519_bip32_signing.so"
        _write(extra, b"extra\n")
        checksums = {item.relative_path: "ab" * 32 for item in natives.EXISTING_ARTIFACTS}
        checksums[spec.relative_path] = "cd" * 32
        findings, _, _ = natives.compare_trees(
            committed,
            staged,
            checksums=checksums,
            groups=("android",),
            compare_committed=False,
            require_inspection=False,
        )
        kinds = {item.kind for item in findings}
        self.assertIn("candidate-mismatch", kinds)
        self.assertIn("extra-staged", kinds)
        self.assertIn("missing-staged", kinds)


class PinnedNdkTests(unittest.TestCase):
    def test_require_dest_ignores_image_ndk_env(self) -> None:
        import install_ndk as ndk_install

        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        image = root / "ndk-27.3"
        image.mkdir()
        (image / "source.properties").write_text(
            "Pkg.Revision = 27.3.13750724\n",
            encoding="utf-8",
        )
        dest = root / "kardano-ndk"
        pinned = dest / "android-ndk-r27c"
        pinned.mkdir(parents=True)
        (pinned / "source.properties").write_text(
            "Pkg.Revision = 27.2.12479018\n",
            encoding="utf-8",
        )
        previous = os.environ.get("ANDROID_NDK_HOME")
        os.environ["ANDROID_NDK_HOME"] = str(image)
        self.addCleanup(
            lambda: (
                os.environ.__setitem__("ANDROID_NDK_HOME", previous)
                if previous is not None
                else os.environ.pop("ANDROID_NDK_HOME", None)
            )
        )
        from io import StringIO
        from unittest.mock import patch

        with patch("sys.stdout", new=StringIO()) as out:
            rc = ndk_install.main(
                ["--dest", str(dest), "--require-dest", "--print-home"]
            )
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue().strip(), str(pinned))
        self.assertEqual(ndk_install.dest_ndk(dest), pinned)

    def test_missing_source_properties_is_rejected(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        with self.assertRaises(rebuild.RebuildError):
            rebuild.require_pinned_ndk(root / "missing-ndk")

    def test_wrong_ndk_revision_is_rejected(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        ndk = root / "ndk-27.3"
        ndk.mkdir()
        (ndk / "source.properties").write_text(
            "Pkg.Revision = 27.3.13750724\n",
            encoding="utf-8",
        )
        with self.assertRaises(rebuild.RebuildError):
            rebuild.require_pinned_ndk(ndk)

    def test_pin_ndk_env_overrides_all_names(self) -> None:
        env = {
            "ANDROID_NDK": "/image/ndk/27.3.13750724",
            "ANDROID_NDK_HOME": "/image/ndk/27.3.13750724",
            "ANDROID_NDK_ROOT": "/image/ndk/27.3.13750724",
        }
        rebuild.pin_ndk_env(env, Path("/tmp/android-ndk-r27c"))
        self.assertEqual(env["ANDROID_NDK"], "/tmp/android-ndk-r27c")
        self.assertEqual(env["ANDROID_NDK_HOME"], "/tmp/android-ndk-r27c")
        self.assertEqual(env["ANDROID_NDK_ROOT"], "/tmp/android-ndk-r27c")


class ToolchainFlagTests(unittest.TestCase):
    def test_darwin_flags_include_stable_install_name(self) -> None:
        pairs = [("/workspace", "/kardano")]
        flags = toolchain.rustflags_darwin_jvm(pairs)
        self.assertTrue(any(toolchain.STABLE_INSTALL_NAME in item for item in flags))
        self.assertTrue(any(item.startswith("--remap-path-prefix=") for item in flags))

    def test_darwin_wrapper_appends_install_name(self) -> None:
        script = toolchain.darwin_cc_wrapper_script()
        self.assertIn(f"-Wl,-install_name,{toolchain.STABLE_INSTALL_NAME}", script)
        self.assertIn('exec cc "$@"', script)

    def test_xcode_pin_parser(self) -> None:
        version, build = toolchain.parse_xcodebuild("Xcode 26.6\nBuild version 17F113\n")
        self.assertEqual(version, "26.6")
        self.assertEqual(build, "17F113")


class CommandRecorderTests(unittest.TestCase):
    def test_retains_stdout_stderr_and_meta(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        recorder = rebuild.CommandRecorder(root / "logs")
        recorder.run(
            [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr)"],
            cwd=root,
            env=__import__("os").environ.copy(),
            name="echo-test",
            outputs=[],
        )
        metas = list((root / "logs").glob("*.meta.json"))
        self.assertEqual(len(metas), 1)
        meta = json.loads(metas[0].read_text(encoding="utf-8"))
        self.assertEqual(meta["returncode"], 0)
        self.assertTrue(Path(meta["stdout_path"]).read_text(encoding="utf-8").startswith("out"))
        self.assertTrue(Path(meta["stderr_path"]).read_text(encoding="utf-8").startswith("err"))


if __name__ == "__main__":
    unittest.main()
