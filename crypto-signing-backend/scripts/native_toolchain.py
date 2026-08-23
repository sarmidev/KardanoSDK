"""Pinned toolchains and deterministic rustc flags for native rebuilds.

Cross-host byte comparison requires a staging-owned CARGO_TARGET_DIR, path
remapping of every absolute source root that rustc/ld may embed, and a
stable Darwin install name. Flags are recorded in provenance; remapping
does not hide unmatched source bytes.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

LIB_STEM = "libkardano_ed25519_bip32_signing"
STABLE_INSTALL_NAME = f"@rpath/{LIB_STEM}.dylib"

RUST_CHANNEL = "1.97.0"
RUSTC_COMMIT = "2d8144b7880597b6e6d3dfd63a9a9efae3f533d3"
CARGO_NDK_VERSION = "4.1.2"
NDK_REVISION = "27.2.12479018"

EXPECTED_XCODE_VERSION = "26.6"
EXPECTED_XCODE_BUILD = "17F113"
EXPECTED_GITHUB_IMAGE_OS = "macos26"
EXPECTED_GITHUB_RUNS_ON = "macos-26"
XCODE_26_6_APP = Path("/Applications/Xcode_26.6.app")
XCODE_DEFAULT_APP = Path("/Applications/Xcode.app")

SOURCE_DATE_EPOCH = "1"
ZERO_AR_DATE = "1"

DARWIN_JVM_TARGETS = ("aarch64-apple-darwin", "x86_64-apple-darwin")
IOS_TARGETS = ("aarch64-apple-ios", "aarch64-apple-ios-sim")
ANDROID_TARGETS = (
    "aarch64-linux-android",
    "armv7-linux-androideabi",
    "i686-linux-android",
    "x86_64-linux-android",
)

ANDROID_ABI_BY_TARGET = {
    "aarch64-linux-android": "arm64-v8a",
    "armv7-linux-androideabi": "armeabi-v7a",
    "i686-linux-android": "x86",
    "x86_64-linux-android": "x86_64",
}


class ToolchainError(RuntimeError):
    pass


def _capture(command: list[str], *, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return ((completed.stdout or "") + (completed.stderr or "")).strip()


def rustc_sysroot(env: dict[str, str] | None = None, cwd: Path | None = None) -> Path | None:
    completed = subprocess.run(
        ["rustc", "--print", "sysroot"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=cwd,
    )
    text = ((completed.stdout or "") + (completed.stderr or "")).strip()
    if not text:
        return None
    path = Path(text.splitlines()[0].strip())
    return path if path.is_dir() else None


def cargo_home() -> Path:
    value = os.environ.get("CARGO_HOME")
    return Path(value).expanduser() if value else Path.home() / ".cargo"


def rustup_home() -> Path:
    value = os.environ.get("RUSTUP_HOME")
    return Path(value).expanduser() if value else Path.home() / ".rustup"


def remap_pairs(
    *,
    module_root: Path,
    cargo_target_dir: Path,
    ndk_home: Path | None,
    env: dict[str, str] | None = None,
) -> list[tuple[str, str]]:
    """Most-specific filesystem prefixes first.

    Host-specific absolute roots map onto stable placeholders so two
    machines that compile the same sources emit the same path strings.
    """
    repo_root = module_root.parent
    pairs: list[tuple[Path, str]] = [
        (cargo_target_dir, "/cargo-target"),
        (module_root, "/kardano/crypto-signing-backend"),
        (repo_root, "/kardano"),
    ]
    sysroot = rustc_sysroot(env, cwd=module_root)
    if sysroot is not None:
        pairs.append((sysroot, "/rustc"))
    # rustc 1.97 ios std objects embed the SDK used to build that toolchain.
    for name in (
        "Xcode_26.2.app",
        "Xcode_26.3.app",
        "Xcode_26.4.app",
        "Xcode_26.4.1.app",
        "Xcode_26.5.app",
        "Xcode_26.6.app",
    ):
        pairs.append((Path("/Applications") / name, "/xcode-app"))
    pairs.append((rustup_home(), "/rustup"))
    pairs.append((cargo_home(), "/cargo"))
    if ndk_home is not None:
        pairs.append((ndk_home, "/android-ndk"))
    applications = Path("/Applications")
    if applications.is_dir():
        for app in sorted(applications.glob("Xcode*.app")):
            pairs.append((app, "/xcode-app"))
            pairs.append((app / "Contents" / "Developer", "/xcode"))
    else:
        pairs.append((XCODE_26_6_APP, "/xcode-app"))
        pairs.append((XCODE_DEFAULT_APP, "/xcode-app"))
    for sdk in ("macosx", "iphoneos", "iphonesimulator"):
        sdk_path = _capture(["xcrun", "--sdk", sdk, "--show-sdk-path"], env=env)
        if sdk_path and not sdk_path.startswith("xcrun:"):
            pairs.append((Path(sdk_path.splitlines()[0]), f"/sdk/{sdk}"))
    pairs.append((Path.home(), "/home/rebuild"))

    resolved: list[tuple[str, str]] = []
    seen: set[str] = set()
    for source, dest in pairs:
        key = str(source)
        if key in seen:
            continue
        seen.add(key)
        resolved.append((key, dest))
    # rustc applies remap flags last-match-wins; keep the longest prefix last.
    resolved.sort(key=lambda item: len(item[0]))
    return resolved


def rustflags_common(pairs: list[tuple[str, str]]) -> list[str]:
    flags: list[str] = []
    for source, dest in pairs:
        flags.append(f"--remap-path-prefix={source}={dest}")
    return flags


DARWIN_CC_WRAPPER_NAME = "kardano-darwin-cc"


def darwin_cc_wrapper_script() -> str:
    return (
        "#!/bin/sh\n"
        "# Link-time override: rustc appends its own -install_name after RUSTFLAGS.\n"
        "# Appending after \"$@\" makes this the last -install_name the linker sees.\n"
        "exec cc \"$@\" "
        f"-Wl,-install_name,{STABLE_INSTALL_NAME} "
        "-Wl,-no_uuid -Wl,-reproducible\n"
    )


def write_darwin_cc_wrapper(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(darwin_cc_wrapper_script(), encoding="utf-8")
    dest.chmod(0o755)
    return dest


def rustflags_darwin_jvm(
    pairs: list[tuple[str, str]],
    *,
    linker: Path | None = None,
) -> list[str]:
    flags = rustflags_common(pairs)
    if linker is not None:
        flags.append(f"-Clinker={linker}")
    flags.append(f"-Clink-arg=-Wl,-install_name,{STABLE_INSTALL_NAME}")
    # Same-size local vs macos-26 dylibs differed only in LC_UUID (and the
    # arm64 ad-hoc signature over that UUID). Drop the UUID and ask ld for
    # reproducible output. iOS archives already matched without these flags.
    flags.append("-Clink-arg=-Wl,-no_uuid")
    flags.append("-Clink-arg=-Wl,-reproducible")
    return flags


def rustflags_android(pairs: list[tuple[str, str]]) -> list[str]:
    return [
        *rustflags_common(pairs),
        "-Clink-arg=-Wl,--build-id=none",
    ]


def encode_rustflags(flags: list[str]) -> str:
    return "\x1f".join(flags)


def apply_rustflags(
    env: dict[str, str],
    pairs: list[tuple[str, str]],
    *,
    darwin_linker: Path | None = None,
) -> dict[str, object]:
    """Write RUSTFLAGS and per-target CARGO_TARGET_*_RUSTFLAGS.

    Target-specific vars replace RUSTFLAGS for that triple, so each list
    includes the common remap prefixes.
    """
    common = rustflags_common(pairs)
    darwin = rustflags_darwin_jvm(pairs, linker=darwin_linker)
    android = rustflags_android(pairs)
    env["RUSTFLAGS"] = " ".join(common)
    env["CARGO_TARGET_AARCH64_APPLE_DARWIN_RUSTFLAGS"] = " ".join(darwin)
    env["CARGO_TARGET_X86_64_APPLE_DARWIN_RUSTFLAGS"] = " ".join(darwin)
    env["CARGO_TARGET_AARCH64_APPLE_IOS_RUSTFLAGS"] = " ".join(common)
    env["CARGO_TARGET_AARCH64_APPLE_IOS_SIM_RUSTFLAGS"] = " ".join(common)
    for rust_target in ANDROID_TARGETS:
        key = f"CARGO_TARGET_{rust_target.upper().replace('-', '_')}_RUSTFLAGS"
        env[key] = " ".join(android)
    return {
        "remap_path_prefix": [f"{src}={dst}" for src, dst in pairs],
        "common_rustflags": common,
        "darwin_jvm_rustflags": darwin,
        "android_rustflags": android,
        "ios_rustflags": common,
        "stable_install_name": STABLE_INSTALL_NAME,
        "darwin_linker": str(darwin_linker) if darwin_linker else None,
        "source_date_epoch": SOURCE_DATE_EPOCH,
        "zero_ar_date": ZERO_AR_DATE,
        "cargo_incremental": "0",
    }


def parse_xcodebuild(text: str) -> tuple[str, str]:
    version = ""
    build = ""
    for line in text.splitlines():
        if line.startswith("Xcode "):
            version = line.split(None, 1)[1].strip()
        elif line.startswith("Build version "):
            build = line.split(None, 2)[-1].strip()
    return version, build


def parse_rustc_release(text: str) -> str:
    match = re.search(r"^rustc\s+(\S+)", text, re.MULTILINE)
    return match.group(1) if match else ""


def parse_rustc_commit(text: str) -> str:
    match = re.search(r"^commit-hash:\s+(\S+)", text, re.MULTILINE)
    return match.group(1) if match else ""


def select_xcode_app() -> Path:
    if XCODE_26_6_APP.is_dir():
        return XCODE_26_6_APP
    if XCODE_DEFAULT_APP.is_dir():
        return XCODE_DEFAULT_APP
    raise ToolchainError(
        "neither /Applications/Xcode_26.6.app nor /Applications/Xcode.app is present"
    )


def assert_pinned_toolchain(env: dict[str, str], *, groups: tuple[str, ...]) -> dict[str, object]:
    """Fail if rustc/Xcode/runner pins do not match the documented values."""
    rustc_text = _capture(["rustc", "--version", "--verbose"], env=env)
    rustc_release = parse_rustc_release(rustc_text)
    rustc_commit = parse_rustc_commit(rustc_text)
    if rustc_release != RUST_CHANNEL:
        raise ToolchainError(
            f"rustc release {rustc_release!r} != pinned {RUST_CHANNEL}"
        )
    if rustc_commit and rustc_commit != RUSTC_COMMIT:
        raise ToolchainError(
            f"rustc commit {rustc_commit} != pinned {RUSTC_COMMIT}"
        )

    xcode_text = ""
    xcode_version = ""
    xcode_build = ""
    developer_dir = ""
    needs_apple = any(group in groups for group in ("macos-jvm", "ios"))
    if platform.system() == "Darwin":
        app = select_xcode_app()
        developer = app / "Contents" / "Developer"
        env["DEVELOPER_DIR"] = str(developer)
        developer_dir = str(developer)
        xcode_text = _capture(["xcodebuild", "-version"], env=env)
        xcode_version, xcode_build = parse_xcodebuild(xcode_text)
        if xcode_version != EXPECTED_XCODE_VERSION or xcode_build != EXPECTED_XCODE_BUILD:
            raise ToolchainError(
                f"Xcode {xcode_version} ({xcode_build}) != pinned "
                f"{EXPECTED_XCODE_VERSION} ({EXPECTED_XCODE_BUILD})"
            )
    elif needs_apple:
        raise ToolchainError("macos-jvm/ios rebuilds require Darwin + Xcode 26.6")

    image_os = os.environ.get("ImageOS", "")
    if os.environ.get("GITHUB_ACTIONS") == "true":
        if image_os != EXPECTED_GITHUB_IMAGE_OS:
            raise ToolchainError(
                f"GitHub ImageOS {image_os!r} != pinned {EXPECTED_GITHUB_IMAGE_OS} "
                f"(workflow must use runs-on: {EXPECTED_GITHUB_RUNS_ON})"
            )

    return {
        "rustc_verbose": rustc_text,
        "rustc_release": rustc_release,
        "rustc_commit": rustc_commit,
        "xcodebuild": xcode_text,
        "xcode_version": xcode_version,
        "xcode_build": xcode_build,
        "developer_dir": developer_dir,
        "image_os": image_os,
        "image_version": os.environ.get("ImageVersion", ""),
        "runner_os": os.environ.get("RUNNER_OS", ""),
        "github_actions": os.environ.get("GITHUB_ACTIONS", ""),
    }


def ndk_prebuilt_triple(ndk_home: Path) -> Path | None:
    prebuilt = ndk_home / "toolchains" / "llvm" / "prebuilt"
    if not prebuilt.is_dir():
        return None
    preferred = (
        "darwin-arm64",
        "darwin-x86_64",
        "linux-x86_64",
        "linux-aarch64",
        "windows-x86_64",
    )
    for name in preferred:
        candidate = prebuilt / name
        if candidate.is_dir():
            return candidate
    children = sorted(p for p in prebuilt.iterdir() if p.is_dir())
    return children[0] if children else None


def ndk_clang(ndk_home: Path) -> Path | None:
    root = ndk_prebuilt_triple(ndk_home)
    if root is None:
        return None
    clang = root / "bin" / "clang"
    return clang if clang.is_file() else None


def rosetta_available() -> bool:
    if platform.system() != "Darwin" or platform.machine() not in {"arm64", "aarch64"}:
        return True
    completed = subprocess.run(
        ["arch", "-x86_64", "/usr/bin/true"],
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def assert_android_host(ndk_home: Path) -> dict[str, object]:
    clang = ndk_clang(ndk_home)
    if clang is None:
        raise ToolchainError(f"NDK clang missing under {ndk_home}")
    clang_file = _capture(["file", str(clang)]) if shutil.which("file") else ""
    try:
        can_run = subprocess.run(
            [str(clang), "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
    except PermissionError as error:
        raise ToolchainError(
            f"NDK clang is not executable ({clang}). "
            "Python zipfile extract must restore the zip Unix execute bits."
        ) from error
    info = {
        "ndk_clang": str(clang),
        "ndk_clang_file": clang_file,
        "ndk_clang_version_rc": can_run.returncode,
        "ndk_clang_version": ((can_run.stdout or "") + (can_run.stderr or "")).strip(),
        "rosetta_available": rosetta_available(),
        "host_machine": platform.machine(),
    }
    if can_run.returncode != 0:
        if (
            platform.system() == "Darwin"
            and platform.machine() in {"arm64", "aarch64"}
            and "darwin-x86_64" in str(clang)
            and not rosetta_available()
        ):
            raise ToolchainError(
                "NDK 27.2.12479018 Darwin zip ships darwin-x86_64 clang only; "
                "this arm64 host cannot execute it (Rosetta missing). "
                f"clang --version rc={can_run.returncode}: {info['ndk_clang_version']}"
            )
        raise ToolchainError(
            f"NDK clang is not executable ({can_run.returncode}): "
            f"{info['ndk_clang_version']}"
        )
    return info
