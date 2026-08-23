"""Catalog and fail-closed comparison helpers for signing-backend natives.

This module does not rebuild binaries. It names the eight committed artifacts
that exist today, parses SHA-256 manifests, inspects staged copies, and
compares them against a manifest. Rebuilds must write only into staging.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from native_toolchain import STABLE_INSTALL_NAME

MODULE_ROOT = Path(__file__).resolve().parent.parent
CHECKSUMS_NAME = "CHECKSUMS.sha256"
CANDIDATE_MANIFEST_NAME = "CANDIDATE_MANIFEST.sha256"
LIB_STEM = "libkardano_ed25519_bip32_signing"
SIGN_SYMBOL = "uniffi_kardano_ed25519_bip32_signing_fn_func_sign"

SHA256_LINE_RE = re.compile(r"^([0-9a-f]{64})  (.+)$")
HOST_PATH_MARKERS = (
    b"/Users/",
    b"/var/folders/",
    b"/private/var/folders/",
    b"/opt/homebrew/",
    b"/Applications/",
    b"/Volumes/",
    b"C:\\",
    b"/Users\\",
)
HOST_PATH_HOME_RE = re.compile(rb"/home/(?!rebuild(?:/|\x00|$))")

REQUIRED_EVIDENCE_SUFFIXES = {
    "dylib": (".inspect.json", ".file.txt", ".nm.txt", ".lipo.txt", ".otool-l.txt", ".path-scan.txt"),
    "so": (".inspect.json", ".file.txt", ".nm.txt", ".path-scan.txt"),
    "archive": (
        ".inspect.json",
        ".file.txt",
        ".nm.txt",
        ".lipo.txt",
        ".ar-tv.txt",
        ".members.json",
        ".path-scan.txt",
    ),
}


@dataclass(frozen=True)
class ArtifactSpec:
    artifact_id: str
    relative_path: str
    group: str
    filename: str
    kind: str
    expected_arch: str
    expected_file_tokens: tuple[str, ...]
    rust_target: str
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
        rust_target="aarch64-apple-darwin",
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
    file_returncode: int | None = None
    lipo_output: str | None = None
    lipo_returncode: int | None = None
    otool_output: str | None = None
    otool_returncode: int | None = None
    install_name: str | None = None
    uuid: str | None = None
    linker_version: str | None = None
    sdk_version: str | None = None
    nm_command: list[str] = field(default_factory=list)
    nm_output: str | None = None
    nm_returncode: int | None = None
    symbols: list[str] = field(default_factory=list)
    symbol_ok: bool | None = None
    arch_ok: bool | None = None
    install_name_ok: bool | None = None
    ar_tv: str | None = None
    ar_tv_returncode: int | None = None
    member_hashes: list[dict[str, str]] = field(default_factory=list)
    embedded_paths: list[str] = field(default_factory=list)
    inspection_errors: list[str] = field(default_factory=list)


_UNSET = object()


@dataclass
class InspectHooks:
    """Injectable process/path helpers so tests can fail closed without host tools."""

    which: Callable[[str], str | None] = shutil.which
    run: Callable[..., subprocess.CompletedProcess[str]] | None = None
    ndk_home: Path | None = None
    llvm_nm: str | None | object = _UNSET

    def run_command(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        if self.run is not None:
            return self.run(command)
        return _run(command)

    def llvm_nm_path(self) -> str | None:
        if self.llvm_nm is not _UNSET:
            return self.llvm_nm  # type: ignore[return-value]
        return _rustc_llvm_nm() or self.which("llvm-nm")


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
            raise ValueError(f"checksum manifest line {line_no} is not 'hash  path'")
        digest, relative = match.group(1), match.group(2)
        if relative in rows:
            raise ValueError(f"duplicate checksum path {relative}")
        rows[relative] = digest
    return rows


def format_checksums(rows: dict[str, str]) -> str:
    lines = []
    for spec in EXISTING_ARTIFACTS:
        if spec.relative_path in rows:
            lines.append(f"{rows[spec.relative_path]}  {spec.relative_path}")
    extras = sorted(path for path in rows if path not in ARTIFACT_BY_RELATIVE)
    for path in extras:
        lines.append(f"{rows[path]}  {path}")
    return "\n".join(lines) + ("\n" if lines else "")


def load_checksums(module_root: Path, name: str = CHECKSUMS_NAME) -> dict[str, str]:
    path = module_root / name
    if not path.is_file():
        raise FileNotFoundError(f"missing {name}")
    return parse_checksums(path.read_text(encoding="utf-8"))


def load_manifest(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f"missing manifest {path}")
    return parse_checksums(path.read_text(encoding="utf-8"))


def _run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


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
    rustup = shutil.which("rustup")
    if rustup:
        completed = _run([rustup, "which", "llvm-nm"], cwd=MODULE_ROOT)
        path = (completed.stdout or "").strip()
        if completed.returncode == 0 and path and Path(path).is_file():
            return path
    rustc = shutil.which("rustc")
    if rustc is None:
        return None
    completed = _run([rustc, "--print", "sysroot"], cwd=MODULE_ROOT)
    sysroot = (completed.stdout or "").strip()
    if not sysroot:
        return None
    rustlib = Path(sysroot) / "lib" / "rustlib"
    if not rustlib.is_dir():
        return None
    for candidate in rustlib.glob("*/bin/llvm-nm"):
        return str(candidate)
    return None


def _nm_command(
    spec: ArtifactSpec,
    path: Path,
    hooks: InspectHooks,
) -> list[str] | None:
    if spec.kind == "so":
        llvm_nm = _ndk_llvm_nm(hooks.ndk_home) or hooks.which("llvm-nm")
        if llvm_nm:
            return [llvm_nm, "-D", str(path)]
    rust_nm = hooks.llvm_nm_path()
    if spec.kind == "archive":
        if rust_nm:
            return [rust_nm, "-g", str(path)]
        return None
    if spec.kind == "so":
        llvm_nm = _ndk_llvm_nm(hooks.ndk_home) or rust_nm
        if llvm_nm:
            return [llvm_nm, "-D", str(path)]
        return None
    nm = rust_nm or hooks.which("nm")
    if nm is None:
        return None
    return [nm, "-gU", str(path)]


def exported_sign_symbols(output: str) -> list[str]:
    hits: list[str] = []
    for raw in output.splitlines():
        if SIGN_SYMBOL in raw:
            hits.append(raw.strip())
    return hits


def parse_lipo_archs(lipo_output: str) -> list[str]:
    text = lipo_output.strip()
    if "is architecture:" in text:
        return [text.rsplit("is architecture:", 1)[1].strip()]
    if "are:" in text:
        return [item for item in text.rsplit("are:", 1)[1].split() if item]
    return []


def parse_macho_identity(otool_output: str) -> tuple[str | None, str | None, str | None, str | None]:
    install_name = None
    uuid = None
    linker_version = None
    sdk_version = None
    in_id = False
    in_build = False
    for line in otool_output.splitlines():
        stripped = line.strip()
        if stripped == "cmd LC_ID_DYLIB":
            in_id = True
            in_build = False
        elif stripped == "cmd LC_BUILD_VERSION":
            in_build = True
            in_id = False
        elif stripped.startswith("cmd "):
            in_id = False
            in_build = False
        elif in_id and stripped.startswith("name "):
            install_name = stripped[5:].split(" (offset", 1)[0].strip()
        elif stripped.startswith("uuid "):
            uuid = stripped.split(None, 1)[1].strip()
        elif in_build and stripped.startswith("sdk "):
            sdk_version = stripped.split(None, 1)[1].strip()
        elif in_build and stripped.startswith("minos "):
            linker_version = stripped
    return install_name, uuid, linker_version, sdk_version


def scan_embedded_absolute_paths(path: Path) -> list[str]:
    data = path.read_bytes()
    hits: list[str] = []
    for marker in HOST_PATH_MARKERS:
        start = 0
        while True:
            index = data.find(marker, start)
            if index < 0:
                break
            end = index
            while end < len(data) and 32 <= data[end] < 127:
                end += 1
            fragment = data[index:end].decode("ascii", errors="ignore")
            if fragment and fragment not in hits:
                hits.append(fragment)
            start = index + 1
    for match in HOST_PATH_HOME_RE.finditer(data):
        end = match.start()
        while end < len(data) and 32 <= data[end] < 127:
            end += 1
        fragment = data[match.start() : end].decode("ascii", errors="ignore")
        if fragment and fragment not in hits:
            hits.append(fragment)
    return hits


def archive_members(path: Path, hooks: InspectHooks) -> tuple[int | None, str, list[dict[str, str]]]:
    ar = hooks.which("ar")
    if ar is None:
        return None, "", []
    listing = hooks.run_command([ar, "-tv", str(path)])
    text = ((listing.stdout or "") + (listing.stderr or "")).strip()
    if listing.returncode != 0:
        return listing.returncode, text, []
    names = hooks.run_command([ar, "-t", str(path)])
    member_names = [line.strip() for line in (names.stdout or "").splitlines() if line.strip()]
    hashed: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory() as tmp:
        extract = subprocess.run(
            [ar, "-x", str(path.resolve())],
            cwd=tmp,
            capture_output=True,
            text=True,
            check=False,
        )
        if extract.returncode != 0:
            return extract.returncode, text, []
        for name in member_names:
            if name.startswith("__.SYMDEF"):
                hashed.append({"name": name, "sha256": "symdef"})
                continue
            member = Path(tmp) / name
            try:
                if member.is_file():
                    hashed.append({"name": name, "sha256": sha256_file(member)})
                else:
                    hashed.append({"name": name, "sha256": ""})
            except OSError as error:
                hashed.append({"name": name, "sha256": f"unreadable:{error}"})
    return listing.returncode, text, hashed


def inspect_artifact(
    spec: ArtifactSpec,
    path: Path,
    *,
    hooks: InspectHooks | None = None,
    require_inspection: bool = True,
    expected_install_name: str = STABLE_INSTALL_NAME,
) -> ArtifactRecord:
    hooks = hooks or InspectHooks()
    record = ArtifactRecord(spec=spec, path=str(path), exists=path.is_file())
    if not record.exists:
        if require_inspection:
            record.inspection_errors.append("artifact file is missing")
        return record
    record.size = path.stat().st_size
    record.sha256 = sha256_file(path)

    file_bin = hooks.which("file")
    if file_bin is None:
        record.inspection_errors.append("file(1) is required")
    else:
        completed = hooks.run_command([file_bin, str(path)])
        record.file_returncode = completed.returncode
        record.file_output = ((completed.stdout or "") + (completed.stderr or "")).strip()
        if completed.returncode != 0:
            record.inspection_errors.append(f"file(1) exited {completed.returncode}")

    file_text = record.file_output or ""
    token_ok = bool(file_text) and all(token in file_text for token in spec.expected_file_tokens)

    if spec.kind in {"dylib", "archive"}:
        lipo = hooks.which("lipo")
        if lipo is None:
            record.inspection_errors.append("lipo is required")
        else:
            completed = hooks.run_command([lipo, "-info", str(path)])
            record.lipo_returncode = completed.returncode
            record.lipo_output = ((completed.stdout or "") + (completed.stderr or "")).strip()
            if completed.returncode != 0:
                record.inspection_errors.append(f"lipo exited {completed.returncode}")
            archs = parse_lipo_archs(record.lipo_output)
            if spec.kind == "dylib":
                record.arch_ok = token_ok and archs == [spec.expected_arch]
            else:
                record.arch_ok = token_ok and spec.expected_arch in archs
            if not record.arch_ok:
                record.inspection_errors.append(
                    f"architecture {spec.expected_arch} not confirmed "
                    f"(file={record.file_output!r} lipo={record.lipo_output!r} archs={archs})"
                )
        if spec.kind == "dylib":
            otool = hooks.which("otool")
            if otool is None:
                record.inspection_errors.append("otool is required for Darwin dylibs")
            else:
                completed = hooks.run_command([otool, "-l", str(path)])
                record.otool_returncode = completed.returncode
                record.otool_output = ((completed.stdout or "") + (completed.stderr or "")).strip()
                if completed.returncode != 0:
                    record.inspection_errors.append(f"otool exited {completed.returncode}")
                (
                    record.install_name,
                    record.uuid,
                    record.linker_version,
                    record.sdk_version,
                ) = parse_macho_identity(record.otool_output or "")
                record.install_name_ok = record.install_name == expected_install_name
                if not record.install_name_ok:
                    record.inspection_errors.append(
                        f"LC_ID_DYLIB {record.install_name!r} != {expected_install_name!r}"
                    )
        if spec.kind == "archive":
            rc, listing, members = archive_members(path, hooks)
            record.ar_tv_returncode = rc
            record.ar_tv = listing
            record.member_hashes = members
            if rc is None:
                record.inspection_errors.append("ar is required for iOS archives")
            elif rc != 0:
                record.inspection_errors.append(f"ar exited {rc}")
    else:
        record.arch_ok = token_ok
        if not record.arch_ok:
            record.inspection_errors.append(
                f"file(1) did not confirm {spec.expected_file_tokens}: {file_text!r}"
            )

    nm_command = _nm_command(spec, path, hooks)
    if nm_command is None:
        record.inspection_errors.append("nm/llvm-nm is required")
        record.symbol_ok = False
    else:
        record.nm_command = nm_command
        completed = hooks.run_command(nm_command)
        record.nm_returncode = completed.returncode
        record.nm_output = ((completed.stdout or "") + (completed.stderr or "")).strip()
        if completed.returncode != 0:
            record.inspection_errors.append(f"nm exited {completed.returncode}")
            record.symbol_ok = False
        else:
            record.symbols = exported_sign_symbols(record.nm_output)
            record.symbol_ok = any(SIGN_SYMBOL in line for line in record.symbols)
            if not record.symbol_ok:
                record.inspection_errors.append(f"{SIGN_SYMBOL} is not exported")

    record.embedded_paths = scan_embedded_absolute_paths(path)
    if record.embedded_paths:
        record.inspection_errors.append(
            "embedded host-absolute paths: " + "; ".join(record.embedded_paths[:8])
        )

    if not require_inspection:
        record.inspection_errors.clear()
        if record.symbol_ok is None:
            record.symbol_ok = True
        if record.arch_ok is None:
            record.arch_ok = True
        if spec.kind == "dylib" and record.install_name_ok is None:
            record.install_name_ok = True
    return record


def write_inspect_evidence(record: ArtifactRecord, evidence_dir: Path) -> list[Path]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    artifact_id = record.spec.artifact_id
    written: list[Path] = []

    def dump(suffix: str, text: str) -> Path:
        dest = evidence_dir / f"{artifact_id}{suffix}"
        dest.write_text(text, encoding="utf-8")
        written.append(dest)
        return dest

    inspect_payload = {
        "id": artifact_id,
        "path": record.path,
        "exists": record.exists,
        "size": record.size,
        "sha256": record.sha256,
        "file_returncode": record.file_returncode,
        "file": record.file_output,
        "lipo_returncode": record.lipo_returncode,
        "lipo": record.lipo_output,
        "otool_returncode": record.otool_returncode,
        "install_name": record.install_name,
        "uuid": record.uuid,
        "linker_version": record.linker_version,
        "sdk_version": record.sdk_version,
        "nm_command": record.nm_command,
        "nm_returncode": record.nm_returncode,
        "sign_symbols": record.symbols,
        "symbol_ok": record.symbol_ok,
        "arch_ok": record.arch_ok,
        "install_name_ok": record.install_name_ok,
        "ar_tv_returncode": record.ar_tv_returncode,
        "member_hashes": record.member_hashes,
        "embedded_paths": record.embedded_paths,
        "inspection_errors": record.inspection_errors,
    }
    import json

    dump(".inspect.json", json.dumps(inspect_payload, indent=2, sort_keys=True) + "\n")
    dump(".file.txt", (record.file_output or "") + "\n")
    dump(".nm.txt", (record.nm_output or "") + "\n")
    dump(".path-scan.txt", "\n".join(record.embedded_paths) + ("\n" if record.embedded_paths else ""))
    if record.spec.kind in {"dylib", "archive"}:
        dump(".lipo.txt", (record.lipo_output or "") + "\n")
    if record.spec.kind == "dylib":
        dump(".otool-l.txt", (record.otool_output or "") + "\n")
    if record.spec.kind == "archive":
        dump(".ar-tv.txt", (record.ar_tv or "") + "\n")
        dump(
            ".members.json",
            json.dumps(record.member_hashes, indent=2, sort_keys=True) + "\n",
        )
    return written


def required_evidence_names(spec: ArtifactSpec) -> list[str]:
    return [f"{spec.artifact_id}{suffix}" for suffix in REQUIRED_EVIDENCE_SUFFIXES[spec.kind]]


def check_evidence_dir(
    evidence_dir: Path,
    *,
    groups: tuple[str, ...] | None = None,
    logs_dir: Path | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    wanted = [
        spec for spec in EXISTING_ARTIFACTS if groups is None or spec.group in groups
    ]
    if not evidence_dir.is_dir():
        findings.append(
            Finding("missing-evidence", None, str(evidence_dir), "evidence directory is missing")
        )
        return findings
    for spec in wanted:
        for name in required_evidence_names(spec):
            path = evidence_dir / name
            if not path.is_file() or path.stat().st_size == 0:
                findings.append(
                    Finding(
                        "missing-evidence",
                        spec.artifact_id,
                        str(path),
                        "required evidence file is missing or empty",
                    )
                )
    if logs_dir is not None:
        if not logs_dir.is_dir():
            findings.append(
                Finding("missing-log", None, str(logs_dir), "command log directory is missing")
            )
        else:
            metas = list(logs_dir.glob("*.meta.json"))
            if not metas:
                findings.append(
                    Finding(
                        "missing-log",
                        None,
                        str(logs_dir),
                        "no command *.meta.json logs were retained",
                    )
                )
    return findings


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
                "artifact is absent from the checksum manifest",
            )
        )
    for relative in sorted(listed - expected):
        findings.append(
            Finding(
                "extra-manifest",
                None,
                relative,
                "checksum manifest lists a path that is not in the existing-artifact catalog",
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
    compare_committed: bool = True,
    require_inspection: bool = True,
    expected_install_name: str = STABLE_INSTALL_NAME,
    hooks: InspectHooks | None = None,
    evidence_dir: Path | None = None,
    logs_dir: Path | None = None,
) -> tuple[list[Finding], list[ArtifactRecord], list[ArtifactRecord]]:
    wanted = [
        spec
        for spec in EXISTING_ARTIFACTS
        if groups is None or spec.group in groups
    ]
    if checksums is None:
        checksums = load_checksums(committed_root)
    findings = check_manifest_coverage(checksums)
    if groups is not None:
        findings = [
            item
            for item in findings
            if item.kind != "missing-manifest"
            or (
                item.path in ARTIFACT_BY_RELATIVE
                and ARTIFACT_BY_RELATIVE[item.path].group in groups
            )
        ]
        findings = [
            item
            for item in findings
            if item.kind != "extra-manifest"
            or ARTIFACT_BY_RELATIVE.get(item.path) is None
            or ARTIFACT_BY_RELATIVE[item.path].group in groups
        ]
    hooks = hooks or InspectHooks(ndk_home=ndk_home)
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
        committed = inspect_artifact(
            spec,
            committed_path,
            hooks=hooks,
            require_inspection=False,
            expected_install_name=expected_install_name,
        )
        staged = inspect_artifact(
            spec,
            staged_path,
            hooks=hooks,
            require_inspection=require_inspection,
            expected_install_name=expected_install_name,
        )
        committed_records.append(committed)
        staged_records.append(staged)
        expected_digest = checksums.get(spec.relative_path)
        if compare_committed:
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
                        f"committed SHA-256 {committed.sha256} != manifest {expected_digest}",
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
        if expected_digest and staged.sha256 != expected_digest:
            kind = "byte-mismatch" if compare_committed else "candidate-mismatch"
            findings.append(
                Finding(
                    kind,
                    spec.artifact_id,
                    spec.relative_path,
                    f"staged {staged.sha256} != manifest {expected_digest} "
                    f"(size {staged.size})",
                )
            )
        elif (
            compare_committed
            and committed.exists
            and committed.sha256 != staged.sha256
        ):
            findings.append(
                Finding(
                    "byte-mismatch",
                    spec.artifact_id,
                    spec.relative_path,
                    f"staged {staged.sha256} != committed {committed.sha256} "
                    f"(sizes {staged.size} vs {committed.size})",
                )
            )
        if require_inspection:
            for message in staged.inspection_errors:
                kind = "inspection-error"
                if "LC_ID_DYLIB" in message:
                    kind = "install-name-mismatch"
                elif "not exported" in message or "nm exited" in message or "nm/llvm-nm" in message:
                    kind = "missing-symbol" if "not exported" in message else "nm-failed"
                elif "architecture" in message or "file(1)" in message or "lipo" in message:
                    kind = "arch-mismatch"
                elif "embedded host-absolute" in message:
                    kind = "embedded-path"
                elif "required" in message:
                    kind = "missing-tool"
                findings.append(
                    Finding(kind, spec.artifact_id, spec.relative_path, message)
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
    if evidence_dir is not None:
        findings.extend(
            check_evidence_dir(evidence_dir, groups=groups, logs_dir=logs_dir)
        )
    elif logs_dir is not None:
        findings.extend(
            check_evidence_dir(
                Path("/__missing_evidence__"),
                groups=(),
                logs_dir=logs_dir,
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
