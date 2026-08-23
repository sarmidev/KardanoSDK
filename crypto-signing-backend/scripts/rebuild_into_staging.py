#!/usr/bin/env python3
"""Rebuild signing-backend natives into a fresh staging-owned cargo target.

Always uses an empty staging CARGO_TARGET_DIR (never the module target/).
Records per-command stdout/stderr, timestamps, exit codes, and output paths.
Deterministic remapping and a stable Darwin @rpath install name are required.
Never copies into src/ and never rewrites CHECKSUMS.sha256.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import native_artifacts as natives  # noqa: E402
import native_toolchain as toolchain  # noqa: E402

LIB = natives.LIB_STEM


class RebuildError(RuntimeError):
    pass


class CommandRecorder:
    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.entries: list[dict[str, object]] = []
        self._index = 0

    def run(
        self,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        name: str,
        outputs: list[Path] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self._index += 1
        slug = f"{self._index:04d}-{name}"
        started = datetime.now(timezone.utc)
        started_monotonic = time.monotonic()
        print("+", " ".join(command), flush=True)
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        ended = datetime.now(timezone.utc)
        stdout_path = self.log_dir / f"{slug}.stdout.txt"
        stderr_path = self.log_dir / f"{slug}.stderr.txt"
        meta_path = self.log_dir / f"{slug}.meta.json"
        stdout_path.write_text(completed.stdout or "", encoding="utf-8")
        stderr_path.write_text(completed.stderr or "", encoding="utf-8")
        if completed.stdout:
            print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
        if completed.stderr:
            print(completed.stderr, end="" if completed.stderr.endswith("\n") else "\n", file=sys.stderr)
        output_meta: list[dict[str, object]] = []
        for path in outputs or []:
            output_meta.append(
                {
                    "path": str(path),
                    "exists": path.is_file(),
                    "size": path.stat().st_size if path.is_file() else None,
                    "mtime": path.stat().st_mtime if path.is_file() else None,
                }
            )
        meta = {
            "name": name,
            "command": command,
            "cwd": str(cwd),
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "duration_seconds": round(time.monotonic() - started_monotonic, 3),
            "returncode": completed.returncode,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "outputs": output_meta,
        }
        meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.entries.append(meta)
        if completed.returncode != 0:
            raise RebuildError(
                f"command failed ({completed.returncode}): {' '.join(command)}; "
                f"stderr={stderr_path}"
            )
        return completed


def _capture(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return ((completed.stdout or "") + (completed.stderr or "")).strip()


def _require_empty_dir(path: Path, label: str) -> None:
    if path.exists():
        if not path.is_dir():
            raise RebuildError(f"{label} exists and is not a directory: {path}")
        if any(path.iterdir()):
            raise RebuildError(f"{label} is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def resolve_cargo_target_dir(staging: Path, module_root: Path, override: Path | None) -> Path:
    module_target = (module_root / "target").resolve()
    if override is not None:
        cargo_target = override.resolve()
    else:
        cargo_target = (staging / "cargo-target").resolve()
    if cargo_target == module_target:
        raise RebuildError(
            "refusing module target/ as CARGO_TARGET_DIR; use a staging-owned empty directory"
        )
    try:
        cargo_target.relative_to(staging.resolve())
    except ValueError as error:
        raise RebuildError(
            f"CARGO_TARGET_DIR must be inside staging ({staging}): {cargo_target}"
        ) from error
    _require_empty_dir(cargo_target, "CARGO_TARGET_DIR")
    return cargo_target


def collect_provenance(module_root: Path, env: dict[str, str]) -> dict[str, object]:
    cargo_lock = module_root / "Cargo.lock"
    commit = _capture(["git", "rev-parse", "HEAD"], cwd=module_root)
    ndk = env.get("ANDROID_NDK_HOME") or env.get("ANDROID_NDK_ROOT") or ""
    ndk_revision = ""
    if ndk:
        props = Path(ndk) / "source.properties"
        if props.is_file():
            ndk_revision = props.read_text(encoding="utf-8")
    return {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": commit,
        "cargo_lock_sha256": natives.sha256_file(cargo_lock) if cargo_lock.is_file() else None,
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        },
        "rustc": _capture(["rustc", "--version", "--verbose"], cwd=module_root, env=env),
        "cargo": _capture(["cargo", "--version", "--verbose"], cwd=module_root, env=env),
        "cargo_ndk": _capture(["cargo", "ndk", "--version"], cwd=module_root, env=env),
        "expected_cargo_ndk": toolchain.CARGO_NDK_VERSION,
        "ndk_home": ndk,
        "ndk_source_properties": ndk_revision,
        "expected_ndk_revision": toolchain.NDK_REVISION,
        "xcodebuild": _capture(["xcodebuild", "-version"], env=env),
        "sw_vers": _capture(["sw_vers"]) if platform.system() == "Darwin" else "",
        "ld_version": _capture(["ld", "-v"]) if platform.system() == "Darwin" else "",
        "rust_channel": toolchain.RUST_CHANNEL,
        "expected_xcode": {
            "version": toolchain.EXPECTED_XCODE_VERSION,
            "build": toolchain.EXPECTED_XCODE_BUILD,
            "runs_on": toolchain.EXPECTED_GITHUB_RUNS_ON,
            "image_os": toolchain.EXPECTED_GITHUB_IMAGE_OS,
        },
    }


def base_env(
    *,
    module_root: Path,
    cargo_target_dir: Path,
) -> tuple[dict[str, str], dict[str, object]]:
    env = os.environ.copy()
    env["CARGO_INCREMENTAL"] = "0"
    env["CARGO_TARGET_DIR"] = str(cargo_target_dir)
    env.setdefault("CARGO_TERM_COLOR", "never")
    env["SOURCE_DATE_EPOCH"] = toolchain.SOURCE_DATE_EPOCH
    env["ZERO_AR_DATE"] = toolchain.ZERO_AR_DATE
    ndk = env.get("ANDROID_NDK_HOME") or env.get("ANDROID_NDK_ROOT")
    ndk_home = Path(ndk) if ndk else None
    pairs = toolchain.remap_pairs(
        module_root=module_root,
        cargo_target_dir=cargo_target_dir,
        ndk_home=ndk_home,
        env=env,
    )
    darwin_linker = toolchain.write_darwin_cc_wrapper(
        cargo_target_dir.parent / "bin" / toolchain.DARWIN_CC_WRAPPER_NAME
    )
    env["KARDANO_DARWIN_CC"] = str(darwin_linker)
    flags = toolchain.apply_rustflags(env, pairs, darwin_linker=darwin_linker)
    return env, flags


def copy_fresh_output(
    src: Path,
    staging: Path,
    relative: str,
    *,
    started_monotonic: float,
) -> Path:
    if not src.is_file():
        raise RebuildError(f"cargo output missing (no-op or failed write): {src}")
    age = time.monotonic() - started_monotonic
    # Reject outputs that predate this command by more than clock slack.
    # A leftover file from a previous cargo run in a dirty target is stale.
    mtime = src.stat().st_mtime
    now = time.time()
    if mtime < now - age - 2:
        raise RebuildError(
            f"stale cargo output {src} (mtime {mtime} older than this command start)"
        )
    if src.stat().st_size == 0:
        raise RebuildError(f"cargo output is empty: {src}")
    dest = staging / "artifacts" / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def _ensure_target(
    rust_target: str,
    *,
    module_root: Path,
    env: dict[str, str],
    recorder: CommandRecorder,
) -> None:
    recorder.run(
        ["rustup", "target", "add", rust_target],
        cwd=module_root,
        env=env,
        name=f"rustup-target-add-{rust_target}",
    )


def rebuild_macos_jvm(
    module_root: Path,
    staging: Path,
    env: dict[str, str],
    recorder: CommandRecorder,
) -> None:
    target_dir = Path(env["CARGO_TARGET_DIR"])
    for spec in natives.EXISTING_ARTIFACTS:
        if spec.group != "macos-jvm":
            continue
        rust_target = spec.rust_target
        _ensure_target(rust_target, module_root=module_root, env=env, recorder=recorder)
        output = target_dir / rust_target / "release" / f"{LIB}.dylib"
        started = time.monotonic()
        recorder.run(
            [
                "cargo",
                "rustc",
                "--locked",
                "--release",
                "--lib",
                "--target",
                rust_target,
                "--",
                f"-Clinker={env['KARDANO_DARWIN_CC']}",
                f"-Clink-arg=-Wl,-install_name,{toolchain.STABLE_INSTALL_NAME}",
            ],
            cwd=module_root,
            env=env,
            name=f"cargo-rustc-{rust_target}",
            outputs=[output],
        )
        dest = copy_fresh_output(output, staging, spec.relative_path, started_monotonic=started)
        record = natives.inspect_artifact(spec, dest)
        natives.write_inspect_evidence(record, staging / "evidence")
        _require_fatal_inspection(spec, record)


def rebuild_android(
    module_root: Path,
    staging: Path,
    env: dict[str, str],
    recorder: CommandRecorder,
) -> None:
    ndk = env.get("ANDROID_NDK_HOME") or env.get("ANDROID_NDK_ROOT")
    if not ndk:
        raise RebuildError("ANDROID_NDK_HOME is required for Android rebuilds")
    ndk_home = Path(ndk)
    props = ndk_home / "source.properties"
    if props.is_file() and toolchain.NDK_REVISION not in props.read_text(encoding="utf-8"):
        raise RebuildError(f"NDK at {ndk} is not revision {toolchain.NDK_REVISION}")
    android_host = toolchain.assert_android_host(ndk_home)
    (staging / "android-host.json").write_text(
        json.dumps(android_host, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    cargo_ndk = _capture(["cargo", "ndk", "--version"], cwd=module_root, env=env)
    if toolchain.CARGO_NDK_VERSION not in cargo_ndk:
        raise RebuildError(
            f"cargo-ndk version {cargo_ndk!r} does not contain pinned "
            f"{toolchain.CARGO_NDK_VERSION}"
        )
    for rust_target in toolchain.ANDROID_TARGETS:
        _ensure_target(rust_target, module_root=module_root, env=env, recorder=recorder)
    out = staging / "jniLibs"
    outputs = [
        out / toolchain.ANDROID_ABI_BY_TARGET[target] / f"{LIB}.so"
        for target in toolchain.ANDROID_TARGETS
    ]
    started = time.monotonic()
    recorder.run(
        [
            "cargo",
            "ndk",
            "-t",
            "arm64-v8a",
            "-t",
            "armeabi-v7a",
            "-t",
            "x86_64",
            "-t",
            "x86",
            "-o",
            str(out),
            "build",
            "--locked",
            "--release",
            "--lib",
        ],
        cwd=module_root,
        env=env,
        name="cargo-ndk-build",
        outputs=outputs,
    )
    for spec in natives.EXISTING_ARTIFACTS:
        if spec.group != "android":
            continue
        abi = Path(spec.relative_path).parent.name
        dest = copy_fresh_output(
            out / abi / spec.filename,
            staging,
            spec.relative_path,
            started_monotonic=started,
        )
        record = natives.inspect_artifact(spec, dest, hooks=natives.InspectHooks(ndk_home=ndk_home))
        natives.write_inspect_evidence(record, staging / "evidence")
        _require_fatal_inspection(spec, record)


def rebuild_ios(
    module_root: Path,
    staging: Path,
    env: dict[str, str],
    recorder: CommandRecorder,
) -> None:
    target_dir = Path(env["CARGO_TARGET_DIR"])
    for spec in natives.EXISTING_ARTIFACTS:
        if spec.group != "ios":
            continue
        rust_target = spec.rust_target
        _ensure_target(rust_target, module_root=module_root, env=env, recorder=recorder)
        output = target_dir / rust_target / "release" / f"{LIB}.a"
        started = time.monotonic()
        recorder.run(
            [
                "cargo",
                "build",
                "--locked",
                "--release",
                "--lib",
                "--target",
                rust_target,
            ],
            cwd=module_root,
            env=env,
            name=f"cargo-build-{rust_target}",
            outputs=[output],
        )
        dest = copy_fresh_output(output, staging, spec.relative_path, started_monotonic=started)
        record = natives.inspect_artifact(spec, dest)
        natives.write_inspect_evidence(record, staging / "evidence")
        _require_fatal_inspection(spec, record)


def _require_fatal_inspection(spec: natives.ArtifactSpec, record: natives.ArtifactRecord) -> None:
    fatal = [
        message
        for message in record.inspection_errors
        if not message.startswith("embedded host-absolute")
    ]
    if fatal:
        raise RebuildError(f"{spec.artifact_id} inspection failed: " + "; ".join(fatal))


BUILDERS = {
    "macos-jvm": rebuild_macos_jvm,
    "android": rebuild_android,
    "ios": rebuild_ios,
}


def write_candidate_outputs(
    staging: Path,
    dest: Path,
    *,
    groups: tuple[str, ...],
    provenance: dict[str, object],
) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    rows: dict[str, str] = {}
    for spec in natives.EXISTING_ARTIFACTS:
        if spec.group not in groups:
            continue
        artifact = staging / "artifacts" / spec.relative_path
        if not artifact.is_file():
            raise RebuildError(f"candidate missing: {artifact}")
        rows[spec.relative_path] = natives.sha256_file(artifact)
    manifest = dest / natives.CANDIDATE_MANIFEST_NAME
    manifest.write_text(natives.format_checksums(rows), encoding="utf-8")
    report = {
        "kind": "candidate",
        "groups": list(groups),
        "hashes": rows,
        "stable_install_name": toolchain.STABLE_INSTALL_NAME,
        "provenance": provenance,
        "note": (
            "Candidate bytes only. CHECKSUMS.sha256 and src/ natives are unchanged. "
            "Replace committed binaries only after a clean runner matches these hashes."
        ),
    }
    (dest / "CANDIDATE_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Candidate native rebuild report",
        "",
        "These hashes are **not** CHECKSUMS.sha256. Committed src/ binaries are unchanged.",
        "",
        f"Stable Darwin install name: `{toolchain.STABLE_INSTALL_NAME}`",
        "",
        "| Artifact | SHA-256 |",
        "|---|---|",
    ]
    for spec in natives.EXISTING_ARTIFACTS:
        if spec.relative_path in rows:
            lines.append(f"| `{spec.artifact_id}` | `{rows[spec.relative_path]}` |")
    lines.append("")
    (dest / "CANDIDATE_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--module-root",
        type=Path,
        default=natives.MODULE_ROOT,
        help="crypto-signing-backend module root.",
    )
    parser.add_argument(
        "--staging",
        type=Path,
        required=True,
        help="Empty directory that will receive cargo-target/, artifacts/, logs/, and evidence/.",
    )
    parser.add_argument(
        "--groups",
        default="macos-jvm,android,ios",
        help="Comma-separated groups to rebuild.",
    )
    parser.add_argument(
        "--cargo-target-dir",
        type=Path,
        help="Must be empty and inside --staging. Default: <staging>/cargo-target.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="After rebuilding, compare staged bytes to --manifest.",
    )
    parser.add_argument(
        "--mode",
        choices=("committed", "candidate"),
        default="committed",
        help="committed: compare to CHECKSUMS + src/. candidate: compare to --manifest only.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Checksum manifest (default: CHECKSUMS.sha256 or rebuild-candidates/CANDIDATE_MANIFEST.sha256).",
    )
    parser.add_argument(
        "--write-candidates",
        type=Path,
        help="Write CANDIDATE_MANIFEST.sha256 + report here. Does not touch src/ or CHECKSUMS.",
    )
    args = parser.parse_args(argv)
    groups = tuple(item.strip() for item in args.groups.split(",") if item.strip())
    unknown = sorted(set(groups) - set(BUILDERS))
    if unknown:
        print(f"unknown groups: {', '.join(unknown)}", file=sys.stderr)
        return 2
    module_root = args.module_root.resolve()
    staging = args.staging.resolve()
    try:
        _require_empty_dir(staging, "staging")
        cargo_target_dir = resolve_cargo_target_dir(staging, module_root, args.cargo_target_dir)
        env, flags = base_env(module_root=module_root, cargo_target_dir=cargo_target_dir)
        pin_info = toolchain.assert_pinned_toolchain(env, groups=groups)
        provenance = collect_provenance(module_root, env)
        provenance["deterministic_flags"] = flags
        provenance["toolchain_pins"] = pin_info
        provenance["cargo_target_dir"] = str(cargo_target_dir)
        provenance["groups"] = list(groups)
        (staging / "provenance.json").write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (staging / "flags.json").write_text(
            json.dumps(flags, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        recorder = CommandRecorder(staging / "logs")
        print(
            f"ANDROID_NDK_HOME={env.get('ANDROID_NDK_HOME', '')} "
            f"CARGO_TARGET_DIR={env.get('CARGO_TARGET_DIR', '')}",
            flush=True,
        )
        print(f"effective remap prefixes: {flags['remap_path_prefix']}", flush=True)
        for group in groups:
            BUILDERS[group](module_root, staging, env, recorder)
        (staging / "commands.json").write_text(
            json.dumps(recorder.entries, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if args.write_candidates:
            write_candidate_outputs(
                staging,
                args.write_candidates.resolve(),
                groups=groups,
                provenance=provenance,
            )
        if args.compare:
            manifest = args.manifest
            if manifest is None:
                if args.mode == "candidate":
                    manifest = module_root / "rebuild-candidates" / natives.CANDIDATE_MANIFEST_NAME
                else:
                    manifest = module_root / natives.CHECKSUMS_NAME
            report_path = staging / "compare-report.json"
            rc = _verify_cli().main(
                [
                    "--module-root",
                    str(module_root),
                    "--staging",
                    str(staging / "artifacts"),
                    "--groups",
                    ",".join(groups),
                    "--report",
                    str(report_path),
                    "--mode",
                    args.mode,
                    "--manifest",
                    str(manifest),
                    "--evidence",
                    str(staging / "evidence"),
                    "--logs",
                    str(staging / "logs"),
                ]
            )
            return rc
    except (RebuildError, toolchain.ToolchainError) as error:
        print(f"rebuild failed: {error}", file=sys.stderr)
        return 1
    print(f"rebuilt {', '.join(groups)} into {staging / 'artifacts'}")
    return 0


def _verify_cli():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "verify_artifacts_cli",
        SCRIPT_DIR / "verify-artifacts.py",
    )
    if spec is None or spec.loader is None:
        raise RebuildError("unable to load verify-artifacts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    raise SystemExit(main())
