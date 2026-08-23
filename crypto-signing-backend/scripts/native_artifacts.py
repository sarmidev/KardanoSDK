"""Catalog and comparison helpers for committed signing-backend natives.

This module does not rebuild binaries. It names the eight committed artifacts
that exist today, parses CHECKSUMS.sha256, and compares a staging tree against
those committed bytes. Rebuilds must write only into a staging directory.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent.parent
CHECKSUMS_NAME = "CHECKSUMS.sha256"
LIB_STEM = "libkardano_ed25519_bip32_signing"
SIGN_SYMBOL = "uniffi_kardano_ed25519_bip32_signing_fn_func_sign"

SHA256_LINE_RE = re.compile(r"^([0-9a-f]{64})  (.+)$")


@dataclass(frozen=True)
class ArtifactSpec:
    artifact_id: str
    relative_path: str
    group: str
    filename: str
    kind: str
    expected_arch: str
    expected_file_tokens: tuple[str, ...]
    rust_target: str | None
    host_only: bool = False


# The eight committed natives. Linux/Windows JVM hosts are not in this catalog.
EXISTING_ARTIFACTS: tuple[ArtifactSpec, ...] = (
    ArtifactSpec(
        artifact_id="macos-jvm-arm64",
        relative_path=f"src/jvmMain/resources/darwin-aarch64/{LIB_STEM}.dylib",
        group="macos-jvm",
        filename=f"{LIB_STEM}.dylib",
        kind="dylib",
        expected_arch="arm64",
        expected_file_tokens=("Mach-O", "arm64"),
        rust_target=None,
        host_only=True,
    ),
    ArtifactSpec(
        artifact_id="macos-jvm-x86_64",
        relative_path=f"src/jvmMain/resources/darwin-x86-64/{LIB_STEM}.dylib",
        group="macos-jvm",
        filename=f"{LIB_STEM}.dylib",
        kind="dylib",
        expected_arch="x86_64",
        expected_file_tokens=("Mach-O", "x86_64"),
        rust_target="x86_64-apple-darwin",
    ),
    ArtifactSpec(
        artifact_id="android-arm64-v8a",
        relative_path=f"src/androidMain/jniLibs/arm64-v8a/{LIB_STEM}.so",
        group="android",
        filename=f"{LIB_STEM}.so",
        kind="so",
        expected_arch="aarch64",
        expected_file_tokens=("ELF", "ARM aarch64"),
        rust_target="aarch64-linux-android",
    ),
    ArtifactSpec(
        artifact_id="android-armeabi-v7a",
        relative_path=f"src/androidMain/jniLibs/armeabi-v7a/{LIB_STEM}.so",
        group="android",
        filename=f"{LIB_STEM}.so",
        kind="so",
        expected_arch="arm",
        expected_file_tokens=("ELF", "ARM"),
        rust_target="armv7-linux-androideabi",
    ),
    ArtifactSpec(
        artifact_id="android-x86",
        relative_path=f"src/androidMain/jniLibs/x86/{LIB_STEM}.so",
        group="android",
        filename=f"{LIB_STEM}.so",
        kind="so",
        expected_arch="i386",
        expected_file_tokens=("ELF", "Intel 80386"),
        rust_target="i686-linux-android",
    ),
    ArtifactSpec(
        artifact_id="android-x86_64",
        relative_path=f"src/androidMain/jniLibs/x86_64/{LIB_STEM}.so",
        group="android",
        filename=f"{LIB_STEM}.so",
        kind="so",
        expected_arch="x86-64",
        expected_file_tokens=("ELF", "x86-64"),
        rust_target="x86_64-linux-android",
    ),
    ArtifactSpec(
        artifact_id="ios-arm64",
        relative_path=f"src/nativeInterop/libs/iosArm64/{LIB_STEM}.a",
        group="ios",
        filename=f"{LIB_STEM}.a",
        kind="archive",
        expected_arch="arm64",
        expected_file_tokens=("ar archive",),
        rust_target="aarch64-apple-ios",
    ),
    ArtifactSpec(
        artifact_id="ios-simulator-arm64",
        relative_path=f"src/nativeInterop/libs/iosSimulatorArm64/{LIB_STEM}.a",
        group="ios",
        filename=f"{LIB_STEM}.a",
        kind="archive",
        expected_arch="arm64",
        expected_file_tokens=("ar archive",),
        rust_target="aarch64-apple-ios-sim",
    ),
)

ARTIFACT_BY_ID: dict[str, ArtifactSpec] = {
    spec.artifact_id: spec for spec in EXISTING_ARTIFACTS
}
ARTIFACT_BY_RELATIVE: dict[str, ArtifactSpec] = {
    spec.relative_path: spec for spec in EXISTING_ARTIFACTS
}
GROUPS: tuple[str, ...] = ("macos-jvm", "android", "ios")


@dataclass
class Finding:
    kind: str
    artifact_id: str | None
    path: str
    message: str

    def format(self) -> str:
        prefix = self.kind
        if self.artifact_id:
            return f"{prefix}: {self.artifact_id} ({self.path}): {self.message}"
        return f"{prefix}: {self.path}: {self.message}"


@dataclass
class ArtifactRecord:
    spec: ArtifactSpec
    path: str
    exists: bool
    size: int | None = None
    sha256: str | None = None
    file_output: str | None = None
    lipo_output: str | None = None
    symbols: list[str] = field(default_factory=list)
    symbol_ok: bool | None = None
    arch_ok: bool | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_checksums(text: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = SHA256_LINE_RE.match(line)
        if match is None:
            raise ValueError(f"CHECKSUMS.sha256 line {line_no} is not 'hash  path'")
        digest, relative = match.group(1), match.group(2)
        if relative in rows:
            raise ValueError(f"duplicate CHECKSUMS path {relative}")
        rows[relative] = digest
    return rows


def load_checksums(module_root: Path) -> dict[str, str]:
    path = module_root / CHECKSUMS_NAME
    if not path.is_file():
        raise FileNotFoundError(f"missing {CHECKSUMS_NAME}")
    return parse_checksums(path.read_text(encoding="utf-8"))


def _run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _file_output(path: Path) -> str:
    file_bin = shutil.which("file")
    if file_bin is None:
        return ""
    completed = _run([file_bin, str(path)])
    return (completed.stdout or "").strip()


def _lipo_output(path: Path) -> str:
    lipo = shutil.which("lipo")
    if lipo is None:
        return ""
    completed = _run([lipo, "-info", str(path)])
    return ((completed.stdout or "") + (completed.stderr or "")).strip()


def _ndk_llvm_nm(ndk_home: Path | None) -> str | None:
    if ndk_home is None:
        env = os.environ.get("ANDROID_NDK_HOME") or os.environ.get("ANDROID_NDK_ROOT")
        ndk_home = Path(env) if env else None
    if ndk_home is None or not ndk_home.is_dir():
        return None
    prebuilt = ndk_home / "toolchains" / "llvm" / "prebuilt"
    if not prebuilt.is_dir():
        return None
    for child in sorted(prebuilt.iterdir()):
        candidate = child / "bin" / "llvm-nm"
        if candidate.is_file():
            return str(candidate)
    return None


def _rustc_llvm_nm() -> str | None:
    rustc = shutil.which("rustc")
    if rustc is None:
        return None
    completed = _run([rustc, "--print", "sysroot"])
    sysroot = (completed.stdout or "").strip()
    if not sysroot:
        return None
    rustlib = Path(sysroot) / "lib" / "rustlib"
    if not rustlib.is_dir():
        return None
    for candidate in rustlib.glob("*/bin/llvm-nm"):
        return str(candidate)
    return None


def _nm_command(spec: ArtifactSpec, path: Path, ndk_home: Path | None) -> list[str] | None:
    if spec.kind == "so":
        llvm_nm = _ndk_llvm_nm(ndk_home) or shutil.which("llvm-nm")
        if llvm_nm:
            return [llvm_nm, "-D", str(path)]
    rust_nm = _rustc_llvm_nm()
    if spec.kind == "archive" and rust_nm:
        return [rust_nm, "-g", str(path)]
    nm = shutil.which("nm")
    if nm is None:
        return None
    if spec.kind == "so":
        return [nm, "-D", str(path)]
    return [nm, "-gU", str(path)]


def exported_sign_symbols(output: str) -> list[str]:
    hits: list[str] = []
    for raw in output.splitlines():
        if SIGN_SYMBOL in raw:
            hits.append(raw.strip())
    return hits


def inspect_artifact(
    spec: ArtifactSpec,
    path: Path,
    *,
    ndk_home: Path | None = None,
) -> ArtifactRecord:
    record = ArtifactRecord(spec=spec, path=str(path), exists=path.is_file())
    if not record.exists:
        return record
    record.size = path.stat().st_size
    record.sha256 = sha256_file(path)
    record.file_output = _file_output(path)
    if spec.kind in {"dylib", "archive"}:
        record.lipo_output = _lipo_output(path)
    command = _nm_command(spec, path, ndk_home)
    if command is not None:
        completed = _run(command)
        record.symbols = exported_sign_symbols(
            (completed.stdout or "") + "\n" + (completed.stderr or "")
        )
        record.symbol_ok = any(SIGN_SYMBOL in line for line in record.symbols)
    file_text = record.file_output or ""
    record.arch_ok = all(token in file_text for token in spec.expected_file_tokens)
    if spec.kind == "dylib" and record.lipo_output:
        record.arch_ok = record.arch_ok and spec.expected_arch in record.lipo_output
    return record


def check_manifest_coverage(checksums: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    expected = {spec.relative_path for spec in EXISTING_ARTIFACTS}
    listed = set(checksums)
    for relative in sorted(expected - listed):
        spec = ARTIFACT_BY_RELATIVE[relative]
        findings.append(
            Finding(
                "missing-manifest",
                spec.artifact_id,
                relative,
                "committed artifact is absent from CHECKSUMS.sha256",
            )
        )
    for relative in sorted(listed - expected):
        findings.append(
            Finding(
                "extra-manifest",
                None,
                relative,
                "CHECKSUMS.sha256 lists a path that is not in the existing-artifact catalog",
            )
        )
    return findings


def compare_trees(
    committed_root: Path,
    staged_root: Path,
    *,
    checksums: dict[str, str] | None = None,
    groups: tuple[str, ...] | None = None,
    ndk_home: Path | None = None,
) -> tuple[list[Finding], list[ArtifactRecord], list[ArtifactRecord]]:
    wanted = [
        spec
        for spec in EXISTING_ARTIFACTS
        if groups is None or spec.group in groups
    ]
    if checksums is None:
        checksums = load_checksums(committed_root)
    findings = check_manifest_coverage(checksums)
    committed_records: list[ArtifactRecord] = []
    staged_records: list[ArtifactRecord] = []
    staged_seen: set[str] = set()
    if staged_root.is_dir():
        for path in staged_root.rglob("*"):
            if path.is_file() and path.name.startswith(LIB_STEM):
                relative = path.relative_to(staged_root).as_posix()
                staged_seen.add(relative)
    for spec in wanted:
        committed_path = committed_root / spec.relative_path
        staged_path = staged_root / spec.relative_path
        committed = inspect_artifact(spec, committed_path, ndk_home=ndk_home)
        staged = inspect_artifact(spec, staged_path, ndk_home=ndk_home)
        committed_records.append(committed)
        staged_records.append(staged)
        expected_digest = checksums.get(spec.relative_path)
        if not committed.exists:
            findings.append(
                Finding(
                    "missing-committed",
                    spec.artifact_id,
                    spec.relative_path,
                    "committed binary is missing",
                )
            )
        elif expected_digest and committed.sha256 != expected_digest:
            findings.append(
                Finding(
                    "checksum-mismatch",
                    spec.artifact_id,
                    spec.relative_path,
                    f"committed SHA-256 {committed.sha256} != CHECKSUMS {expected_digest}",
                )
            )
        if not staged.exists:
            findings.append(
                Finding(
                    "missing-staged",
                    spec.artifact_id,
                    spec.relative_path,
                    "staged rebuild is missing",
                )
            )
            continue
        if committed.exists and committed.sha256 != staged.sha256:
            findings.append(
                Finding(
                    "byte-mismatch",
                    spec.artifact_id,
                    spec.relative_path,
                    f"staged {staged.sha256} != committed {committed.sha256} "
                    f"(sizes {staged.size} vs {committed.size})",
                )
            )
        if staged.symbol_ok is False:
            findings.append(
                Finding(
                    "missing-symbol",
                    spec.artifact_id,
                    spec.relative_path,
                    f"{SIGN_SYMBOL} is not exported",
                )
            )
        if staged.arch_ok is False:
            findings.append(
                Finding(
                    "arch-mismatch",
                    spec.artifact_id,
                    spec.relative_path,
                    f"file(1)/lipo did not confirm {spec.expected_arch}: {staged.file_output}",
                )
            )
    extra = sorted(
        relative
        for relative in staged_seen
        if relative not in ARTIFACT_BY_RELATIVE
        or (
            groups is not None
            and ARTIFACT_BY_RELATIVE[relative].group not in groups
        )
    )
    for relative in extra:
        findings.append(
            Finding(
                "extra-staged",
                ARTIFACT_BY_RELATIVE[relative].artifact_id
                if relative in ARTIFACT_BY_RELATIVE
                else None,
                relative,
                "staged tree contains a binary outside the requested catalog",
            )
        )
    return findings, committed_records, staged_records


def first_differing_byte(left: Path, right: Path) -> dict[str, int | str] | None:
    if not left.is_file() or not right.is_file():
        return None
    left_size = left.stat().st_size
    right_size = right.stat().st_size
    offset = 0
    with left.open("rb") as left_handle, right.open("rb") as right_handle:
        while True:
            left_chunk = left_handle.read(1024 * 1024)
            right_chunk = right_handle.read(1024 * 1024)
            if not left_chunk and not right_chunk:
                return None
            if left_chunk != right_chunk:
                for index, (a, b) in enumerate(zip(left_chunk, right_chunk)):
                    if a != b:
                        return {
                            "offset": offset + index,
                            "committed": f"{a:02x}",
                            "staged": f"{b:02x}",
                            "committed_size": left_size,
                            "staged_size": right_size,
                        }
                return {
                    "offset": offset + min(len(left_chunk), len(right_chunk)),
                    "committed": "eof" if len(left_chunk) < len(right_chunk) else "pad",
                    "staged": "eof" if len(right_chunk) < len(left_chunk) else "pad",
                    "committed_size": left_size,
                    "staged_size": right_size,
                }
            offset += len(left_chunk)
    return None
