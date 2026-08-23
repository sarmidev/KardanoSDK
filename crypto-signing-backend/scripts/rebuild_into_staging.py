#!/usr/bin/env python3
"""Rebuild committed signing-backend natives into a fresh staging directory.

Uses `cargo --locked` / `cargo ndk ... --locked`. Never copies into src/.
The default recipe matches README.md. `--deterministic` adds extra flags
that the original committed binaries were not built with.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import native_artifacts as natives  # noqa: E402

LIB = natives.LIB_STEM
CARGO_NDK_VERSION = "4.1.2"
NDK_REVISION = "27.2.12479018"
RUST_CHANNEL = "1.97.0"


class RebuildError(RuntimeError):
    pass


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(command), flush=True)
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RebuildError(f"command failed ({completed.returncode}): {' '.join(command)}")
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


def _require_empty_staging(staging: Path) -> None:
    if staging.exists():
        if not staging.is_dir():
            raise RebuildError(f"staging path exists and is not a directory: {staging}")
        if any(staging.iterdir()):
            raise RebuildError(f"staging directory is not empty: {staging}")
    staging.mkdir(parents=True, exist_ok=True)


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
        "expected_cargo_ndk": CARGO_NDK_VERSION,
        "ndk_home": ndk,
        "ndk_source_properties": ndk_revision,
        "expected_ndk_revision": NDK_REVISION,
        "xcodebuild": _capture(["xcodebuild", "-version"]),
        "sw_vers": _capture(["sw_vers"]) if platform.system() == "Darwin" else "",
        "rust_channel": RUST_CHANNEL,
    }


def base_env(
    *,
    deterministic: bool,
    module_root: Path,
    cargo_target_dir: Path,
) -> dict[str, str]:
    env = os.environ.copy()
    env["CARGO_INCREMENTAL"] = "0"
    # Default is the crate `target/` directory (gitignored), matching README.md.
    # A separate staging cargo-target changes Mach-O LC_ID_DYLIB (absolute path)
    # and therefore LC_UUID. Do not point this at src/.
    env["CARGO_TARGET_DIR"] = str(cargo_target_dir)
    env.setdefault("CARGO_TERM_COLOR", "never")
    if deterministic:
        env["SOURCE_DATE_EPOCH"] = "1"
        env["ZERO_AR_DATE"] = "1"
        env["RUSTFLAGS"] = (
            env.get("RUSTFLAGS", "")
            + f" --remap-path-prefix {module_root}=."
            + f" --remap-path-prefix {Path.home()}=/home/rebuild"
        ).strip()
    return env


def copy_into_staging(src: Path, staging: Path, relative: str) -> Path:
    if not src.is_file():
        raise RebuildError(f"cargo output missing: {src}")
    dest = staging / "artifacts" / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def _ensure_target(rust_target: str, *, module_root: Path, env: dict[str, str]) -> None:
    completed = subprocess.run(
        ["rustup", "target", "add", rust_target],
        cwd=module_root,
        env=env,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RebuildError(f"rustup target add {rust_target} failed ({completed.returncode})")


def rebuild_macos_jvm(module_root: Path, staging: Path, env: dict[str, str]) -> None:
    target_dir = Path(env["CARGO_TARGET_DIR"])
    _run(["cargo", "build", "--locked", "--release", "--lib"], cwd=module_root, env=env)
    copy_into_staging(
        target_dir / "release" / f"{LIB}.dylib",
        staging,
        natives.ARTIFACT_BY_ID["macos-jvm-arm64"].relative_path,
    )
    _ensure_target("x86_64-apple-darwin", module_root=module_root, env=env)
    _run(
        ["cargo", "build", "--locked", "--release", "--lib", "--target", "x86_64-apple-darwin"],
        cwd=module_root,
        env=env,
    )
    copy_into_staging(
        target_dir / "x86_64-apple-darwin" / "release" / f"{LIB}.dylib",
        staging,
        natives.ARTIFACT_BY_ID["macos-jvm-x86_64"].relative_path,
    )


def rebuild_android(module_root: Path, staging: Path, env: dict[str, str]) -> None:
    ndk = env.get("ANDROID_NDK_HOME") or env.get("ANDROID_NDK_ROOT")
    if not ndk:
        raise RebuildError("ANDROID_NDK_HOME is required for Android rebuilds")
    props = Path(ndk) / "source.properties"
    if props.is_file() and NDK_REVISION not in props.read_text(encoding="utf-8"):
        raise RebuildError(f"NDK at {ndk} is not revision {NDK_REVISION}")
    out = staging / "jniLibs"
    _run(
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
    )
    for spec in natives.EXISTING_ARTIFACTS:
        if spec.group != "android":
            continue
        abi = Path(spec.relative_path).parent.name
        copy_into_staging(out / abi / spec.filename, staging, spec.relative_path)


def rebuild_ios(module_root: Path, staging: Path, env: dict[str, str]) -> None:
    target_dir = Path(env["CARGO_TARGET_DIR"])
    for artifact_id, rust_target in (
        ("ios-arm64", "aarch64-apple-ios"),
        ("ios-simulator-arm64", "aarch64-apple-ios-sim"),
    ):
        _ensure_target(rust_target, module_root=module_root, env=env)
        _run(
            ["cargo", "build", "--locked", "--release", "--lib", "--target", rust_target],
            cwd=module_root,
            env=env,
        )
        copy_into_staging(
            target_dir / rust_target / "release" / f"{LIB}.a",
            staging,
            natives.ARTIFACT_BY_ID[artifact_id].relative_path,
        )


BUILDERS = {
    "macos-jvm": rebuild_macos_jvm,
    "android": rebuild_android,
    "ios": rebuild_ios,
}


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
        help="Empty directory that will receive cargo-target/, artifacts/, and reports.",
    )
    parser.add_argument(
        "--groups",
        default="macos-jvm,android,ios",
        help="Comma-separated groups to rebuild.",
    )
    parser.add_argument(
        "--cargo-target-dir",
        type=Path,
        help="Cargo target directory (default: <module>/target, the README recipe).",
    )
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Add SOURCE_DATE_EPOCH/ZERO_AR_DATE/remap-path-prefix (not the README recipe).",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="After rebuilding, run verify-artifacts against committed bytes.",
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
        _require_empty_staging(staging)
        cargo_target_dir = (
            args.cargo_target_dir.resolve()
            if args.cargo_target_dir
            else (module_root / "target")
        )
        env = base_env(
            deterministic=args.deterministic,
            module_root=module_root,
            cargo_target_dir=cargo_target_dir,
        )
        provenance = collect_provenance(module_root, env)
        provenance["deterministic_flags"] = bool(args.deterministic)
        provenance["cargo_target_dir"] = str(cargo_target_dir)
        provenance["groups"] = list(groups)
        (staging / "provenance.json").write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            f"ANDROID_NDK_HOME={env.get('ANDROID_NDK_HOME', '')} "
            f"CARGO_TARGET_DIR={env.get('CARGO_TARGET_DIR', '')}",
            flush=True,
        )
        for group in groups:
            BUILDERS[group](module_root, staging, env)
        if args.compare:
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
                ]
            )
            return rc
    except RebuildError as error:
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
