"""Pinned toolchains and deterministic rustc flags for native rebuilds.

Cross-host byte comparison requires a staging-owned CARGO_TARGET_DIR, path
remapping of every absolute source root that rustc/ld may embed, and a
stable Darwin install name. Flags are recorded in provenance; remapping
does not hide unmatched source bytes.
"""

from __future__ import annotations

import glob
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

LIB_STEM = "libkardano_ed25519_bip32_signing"
STABLE_INSTALL_NAME = f"@rpath/{LIB_STEM}.dylib"
STABLE_LINUX_SONAME = f"{LIB_STEM}.so"
LINUX_JVM_TARGET = "x86_64-unknown-linux-gnu"
EXPECTED_LINUX_IMAGE_OS = "ubuntu22"
EXPECTED_LINUX_RUNS_ON = "ubuntu-22.04"
WINDOWS_JVM_TARGET = "x86_64-pc-windows-msvc"
EXPECTED_WINDOWS_IMAGE_OS = "win22"
EXPECTED_WINDOWS_RUNS_ON = "windows-2022"
# Observed on windows-2022 rustc 1.97.0 Phase B (run 32715104620).
# Fail on drift until an independent review changes this pin.
# Hosted ImageVersion is recorded; it is not an immutable-image claim.
EXPECTED_MSVC_TOOLSET = "14.44.35207"
EXPECTED_MSVC_LINK_VERSION = "14.44.35228.0"
EXPECTED_MSVC_LINK_VERSION_PREFIX = "14.44."
EXPECTED_WINDOWS_SDK_VERSION = "10.0.26100.0"
MSVC_HOST_ARCH = "Hostx64"
MSVC_TARGET_ARCH = "x64"
VSWHERE_DEFAULT = Path(
    r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
)
WINDOWS_KITS_ROOT = Path(r"C:\Program Files (x86)\Windows Kits\10")
# Consumer/runtime floor is the pinned runner's glibc. Ubuntu 22.04 is 2.35.
# Measured at rebuild time; do not assume. musl and older glibc are out of scope.
EXPECTED_LINUX_GLIBC_BASELINE = (2, 35, 0)
EXPECTED_LINUX_GLIBC_LABEL = "2.35"

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


def require_native_linux_x86_64() -> None:
    """Refuse macOS cross-builds and Linux ARM hosts."""
    system = platform.system()
    machine = platform.machine().lower()
    if system != "Linux":
        raise ToolchainError(
            "linux-jvm rebuilds require a native Linux x86-64 host; "
            f"{system} cross-builds are refused"
        )
    if machine not in {"x86_64", "amd64"}:
        raise ToolchainError(
            "linux-jvm rebuilds require x86_64-unknown-linux-gnu; "
            f"host machine {machine} is refused (Linux ARM is out of scope)"
        )


def parse_link_version(text: str) -> str:
    match = re.search(r"Version\s+(\d+\.\d+\.\d+(?:\.\d+)?)", text)
    return match.group(1) if match else ""


def parse_msvc_toolset_from_path(path: Path) -> str:
    parts = Path(str(path).replace("\\", "/")).parts
    for index, part in enumerate(parts):
        if part == "MSVC" and index + 1 < len(parts):
            return parts[index + 1]
    return ""


def find_vswhere() -> Path | None:
    found = shutil.which("vswhere") or shutil.which("vswhere.exe")
    if found:
        return Path(found)
    if VSWHERE_DEFAULT.is_file():
        return VSWHERE_DEFAULT
    return None


def discover_msvc_link(
    *,
    expected_toolset: str = EXPECTED_MSVC_TOOLSET,
    vswhere_output: str | None = None,
    glob_matches: list[str] | None = None,
) -> Path:
    pattern = rf"**\VC\Tools\MSVC\{expected_toolset}\bin\{MSVC_HOST_ARCH}\{MSVC_TARGET_ARCH}\link.exe"
    lines: list[str] = []
    if vswhere_output is not None:
        lines = [line.strip() for line in vswhere_output.splitlines() if line.strip()]
    else:
        vswhere = find_vswhere()
        if vswhere is not None:
            completed = subprocess.run(
                [str(vswhere), "-products", "*", "-find", pattern],
                capture_output=True,
                text=True,
                check=False,
            )
            lines = [
                line.strip() for line in (completed.stdout or "").splitlines() if line.strip()
            ]
    for candidate in lines:
        path = Path(candidate)
        if path.is_file():
            toolset = parse_msvc_toolset_from_path(path)
            if toolset != expected_toolset:
                raise ToolchainError(
                    f"MSVC toolset {toolset} != pinned {expected_toolset} "
                    "(review before changing EXPECTED_MSVC_TOOLSET)"
                )
            return path
    matches = glob_matches
    if matches is None:
        matches = sorted(
            glob.glob(
                rf"C:\Program Files\Microsoft Visual Studio\2022\*\VC\Tools\MSVC\{expected_toolset}\bin\{MSVC_HOST_ARCH}\{MSVC_TARGET_ARCH}\link.exe"
            )
        )
    if matches and Path(matches[-1]).is_file():
        return Path(matches[-1])
    raise ToolchainError(
        f"MSVC toolset {expected_toolset} Hostx64/x64 link.exe was not found; "
        "review before changing EXPECTED_MSVC_TOOLSET"
    )


def first_where(name: str, env: dict[str, str]) -> Path | None:
    where = shutil.which("where.exe", path=env.get("PATH")) or shutil.which(
        "where", path=env.get("PATH")
    )
    if where is None:
        return None
    completed = subprocess.run(
        [where, name],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    lines = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
    return Path(lines[0]) if lines else None


def require_windows_sdk(
    *,
    kits_root: Path | None = None,
    expected_version: str = EXPECTED_WINDOWS_SDK_VERSION,
) -> dict[str, object]:
    """Select the pinned Windows 10 SDK; drift fails until reviewed."""
    root = kits_root if kits_root is not None else WINDOWS_KITS_ROOT
    if not root.is_dir():
        raise ToolchainError(
            f"Windows Kits root is missing: {root} "
            "(review before changing EXPECTED_WINDOWS_SDK_VERSION)"
        )
    version = expected_version
    include_um = root / "Include" / version / "um"
    include_ucrt = root / "Include" / version / "ucrt"
    include_shared = root / "Include" / version / "shared"
    lib_um = root / "Lib" / version / "um" / "x64"
    lib_ucrt = root / "Lib" / version / "ucrt" / "x64"
    bin_x64 = root / "bin" / version / "x64"
    required_dirs = (include_um, include_ucrt, include_shared, lib_um, lib_ucrt, bin_x64)
    required_files = (
        include_um / "Windows.h",
        include_ucrt / "stdlib.h",
        lib_um / "kernel32.lib",
        lib_ucrt / "libucrt.lib",
    )
    missing = [str(path) for path in required_dirs if not path.is_dir()]
    missing.extend(str(path) for path in required_files if not path.is_file())
    if missing:
        raise ToolchainError(
            f"Windows SDK {version} is missing required paths: {missing}; "
            "review before changing EXPECTED_WINDOWS_SDK_VERSION"
        )
    return {
        "root": str(root),
        "version": version,
        "include_um": str(include_um),
        "include_ucrt": str(include_ucrt),
        "include_shared": str(include_shared),
        "lib_um": str(lib_um),
        "lib_ucrt": str(lib_ucrt),
        "bin": str(bin_x64),
    }


def apply_windows_sdk_env(env: dict[str, str], sdk: dict[str, object]) -> None:
    root = str(sdk["root"])
    version = str(sdk["version"])
    bin_path = str(sdk["bin"])
    sep = "\\"
    env["WindowsSdkDir"] = root if root.endswith(("\\", "/")) else root + sep
    env["WindowsSDKVersion"] = version if version.endswith("\\") else version + sep
    env["WindowsSdkVerBinPath"] = (
        bin_path if bin_path.endswith(("\\", "/")) else bin_path + sep
    )
    env["UCRTVersion"] = env["WindowsSDKVersion"]
    includes = [str(sdk["include_um"]), str(sdk["include_ucrt"]), str(sdk["include_shared"])]
    libs = [str(sdk["lib_um"]), str(sdk["lib_ucrt"])]
    existing_inc = env.get("INCLUDE", "")
    existing_lib = env.get("LIB", "")
    env["INCLUDE"] = os.pathsep.join(includes + ([existing_inc] if existing_inc else []))
    env["LIB"] = os.pathsep.join(libs + ([existing_lib] if existing_lib else []))
    env["PATH"] = f"{bin_path}{os.pathsep}{env.get('PATH', '')}"
    env["KARDANO_WINDOWS_SDK_VERSION"] = version
    env["KARDANO_WINDOWS_SDK_DIR"] = root


def discover_windows_sdk(*, kits_root: Path | None = None) -> dict[str, object]:
    return require_windows_sdk(kits_root=kits_root)


def activate_pinned_msvc_linker(
    env: dict[str, str],
    *,
    link_path: Path | None = None,
    where_first: Path | None = None,
    banner: str | None = None,
    kits_root: Path | None = None,
) -> dict[str, object]:
    """Select one explicit MSVC Hostx64/x64 link.exe and put it first on PATH."""
    link = link_path if link_path is not None else discover_msvc_link()
    host_dir = link.parent
    if host_dir.name != MSVC_TARGET_ARCH or host_dir.parent.name != MSVC_HOST_ARCH:
        raise ToolchainError(f"link.exe is not {MSVC_HOST_ARCH}/{MSVC_TARGET_ARCH}: {link}")
    toolset = parse_msvc_toolset_from_path(link)
    if toolset != EXPECTED_MSVC_TOOLSET:
        raise ToolchainError(
            f"MSVC toolset {toolset} != pinned {EXPECTED_MSVC_TOOLSET} "
            "(review before changing EXPECTED_MSVC_TOOLSET)"
        )
    env["PATH"] = f"{host_dir}{os.pathsep}{env.get('PATH', '')}"
    env["KARDANO_MSVC_LINK"] = str(link)
    env["KARDANO_MSVC_TOOLSET"] = toolset
    env["CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER"] = str(link)
    first = where_first if where_first is not None else first_where("link", env)
    if first is None:
        raise ToolchainError("where.exe link returned no results after PATH prepend")
    if first.resolve() != link.resolve():
        raise ToolchainError(
            f"where.exe link first result {first} != pinned {link}"
        )
    text = banner if banner is not None else (
        _capture([str(link)], env=env) + "\n" + _capture([str(link), "/?"], env=env)
    )
    version = parse_link_version(text)
    if version != EXPECTED_MSVC_LINK_VERSION:
        raise ToolchainError(
            f"link.exe Version {version!r} != pinned {EXPECTED_MSVC_LINK_VERSION} "
            f"(toolset folder {EXPECTED_MSVC_TOOLSET})"
        )
    sdk = require_windows_sdk(kits_root=kits_root)
    apply_windows_sdk_env(env, sdk)
    env["PATH"] = f"{host_dir}{os.pathsep}{env.get('PATH', '')}"
    return {
        "msvc_toolset": toolset,
        "link_path": str(link),
        "link_version": version,
        "link_banner": text[:2000],
        "windows_sdk": sdk,
        "image_os": os.environ.get("ImageOS", env.get("ImageOS", "")),
        "image_version": os.environ.get("ImageVersion", env.get("ImageVersion", "")),
        "hosted_image_immutable": False,
        "where_link": str(first),
    }


def require_native_windows_x86_64() -> None:
    """Refuse macOS/Linux cross-builds and Windows ARM hosts."""
    system = platform.system()
    machine = platform.machine().lower()
    if system != "Windows":
        raise ToolchainError(
            "windows-jvm rebuilds require a native Windows x86-64 host; "
            f"{system} cross-builds are refused"
        )
    if machine not in {"x86_64", "amd64"}:
        raise ToolchainError(
            "windows-jvm rebuilds require x86_64-pc-windows-msvc; "
            f"host machine {machine} is refused (Windows ARM is out of scope)"
        )


def _capture(command: list[str], *, env: dict[str, str] | None = None) -> str:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    except FileNotFoundError:
        return ""
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
    if platform.system() == "Darwin":
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
    # GitHub-hosted Ubuntu roots that are not always the repo or cargo-target.
    runner_temp = os.environ.get("RUNNER_TEMP")
    if runner_temp:
        pairs.append((Path(runner_temp), "/runner-temp"))
    runner_workspace = os.environ.get("RUNNER_WORKSPACE")
    if runner_workspace:
        pairs.append((Path(runner_workspace), "/runner-workspace"))
    github_workspace = os.environ.get("GITHUB_WORKSPACE")
    if github_workspace:
        pairs.append((Path(github_workspace), "/kardano"))

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
        "-Wl,-reproducible\n"
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
    # macos-26 dyld refuses dylibs without LC_UUID ("missing LC_UUID load
    # command"). Ask ld for a content-derived UUID instead of omitting it.
    flags.append("-Clink-arg=-Wl,-reproducible")
    return flags


def rustflags_android(pairs: list[tuple[str, str]]) -> list[str]:
    return [
        *rustflags_common(pairs),
        "-Clink-arg=-Wl,--build-id=none",
    ]


def rustflags_linux_jvm(pairs: list[tuple[str, str]]) -> list[str]:
    """Native x86_64-unknown-linux-gnu flags. No macOS cross-link, no rpath."""
    return [
        *rustflags_common(pairs),
        "--remap-cwd-prefix=/kardano/crypto-signing-backend",
        "-Cdebuginfo=0",
        "-Cstrip=symbols",
        f"-Clink-arg=-Wl,-soname,{STABLE_LINUX_SONAME}",
        "-Clink-arg=-Wl,--build-id=none",
    ]


def rustflags_windows_jvm(pairs: list[tuple[str, str]]) -> list[str]:
    """Native x86_64-pc-windows-msvc flags. No macOS/Linux cross-link."""
    return [
        *rustflags_common(pairs),
        "--remap-cwd-prefix=/kardano/crypto-signing-backend",
        "-Cdebuginfo=0",
        "-Cstrip=symbols",
        "-Clink-arg=/Brepro",
        "-Clink-arg=/DEBUG:NONE",
        "-Clink-arg=/INCREMENTAL:NO",
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
    linux = rustflags_linux_jvm(pairs)
    windows = rustflags_windows_jvm(pairs)
    env["RUSTFLAGS"] = " ".join(common)
    env["CARGO_TARGET_AARCH64_APPLE_DARWIN_RUSTFLAGS"] = " ".join(darwin)
    env["CARGO_TARGET_X86_64_APPLE_DARWIN_RUSTFLAGS"] = " ".join(darwin)
    env["CARGO_TARGET_AARCH64_APPLE_IOS_RUSTFLAGS"] = " ".join(common)
    env["CARGO_TARGET_AARCH64_APPLE_IOS_SIM_RUSTFLAGS"] = " ".join(common)
    env["CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUSTFLAGS"] = " ".join(linux)
    env["CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_RUSTFLAGS"] = " ".join(windows)
    for rust_target in ANDROID_TARGETS:
        key = f"CARGO_TARGET_{rust_target.upper().replace('-', '_')}_RUSTFLAGS"
        env[key] = " ".join(android)
    return {
        "remap_path_prefix": [f"{src}={dst}" for src, dst in pairs],
        "common_rustflags": common,
        "darwin_jvm_rustflags": darwin,
        "android_rustflags": android,
        "linux_jvm_rustflags": linux,
        "linux_soname": STABLE_LINUX_SONAME,
        "linux_build_id": "none",
        "windows_jvm_rustflags": windows,
        "windows_link_repro": "/Brepro",
        "windows_debug": "NONE",
        "ios_rustflags": common,
        "stable_install_name": STABLE_INSTALL_NAME,
        "darwin_linker": str(darwin_linker) if darwin_linker else None,
        "source_date_epoch": SOURCE_DATE_EPOCH,
        "zero_ar_date": ZERO_AR_DATE,
        "cargo_incremental": "0",
        "darwin_uuid_normalize": {
            "digest": "hashlib.sha256",
            "uuid": "RFC 9562 version 8 from first 16 digest bytes",
            "canonical": (
                "zero LC_UUID; exclude validated LC_CODE_SIGNATURE command/blob "
                "and restore ncmds/sizeofcmds/__LINKEDIT filesize/vmsize"
            ),
            "identifier": "org.sarmidev.kardano.ed25519-bip32-signing",
            "identifier_match": "exact",
            "arm64_codesign": "adhoc --timestamp=none TeamIdentifier=not set",
            "x86_64_codesign": "unsigned after LC_UUID patch",
        },
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


def _find_rustup(env: dict[str, str]) -> str | None:
    cargo_home = Path(env.get("CARGO_HOME") or (Path.home() / ".cargo"))
    names = ("rustup.exe", "rustup") if os.name == "nt" else ("rustup",)
    for name in names:
        candidate = cargo_home / "bin" / name
        if candidate.is_file():
            return str(candidate)
    return shutil.which("rustup", path=env.get("PATH"))


def activate_pinned_rustc(env: dict[str, str]) -> Path | None:
    """Prefer the pinned rustc bin over an image-provided newer rustc on PATH."""
    env["RUSTUP_TOOLCHAIN"] = RUST_CHANNEL
    rustup = _find_rustup(env)
    if rustup is None:
        return None
    env.setdefault("CARGO_HOME", str(Path.home() / ".cargo"))
    env.setdefault("RUSTUP_HOME", str(Path.home() / ".rustup"))
    completed = subprocess.run(
        [rustup, "run", RUST_CHANNEL, "rustc", "--print", "sysroot"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    sysroot = Path((completed.stdout or "").strip())
    toolchain_bin = sysroot / "bin"
    rustc_name = "rustc.exe" if os.name == "nt" else "rustc"
    if completed.returncode != 0 or not (toolchain_bin / rustc_name).is_file():
        raise ToolchainError(
            f"pinned rustc {RUST_CHANNEL} is not installed via rustup"
        )
    env["PATH"] = f"{toolchain_bin}{os.pathsep}{env.get('PATH', '')}"
    return toolchain_bin


def assert_pinned_toolchain(env: dict[str, str], *, groups: tuple[str, ...]) -> dict[str, object]:
    """Fail if rustc/Xcode/runner pins do not match the documented values."""
    activate_pinned_rustc(env)
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
    needs_linux = "linux-jvm" in groups
    needs_windows = "windows-jvm" in groups
    exclusive = [name for name, flag in (
        ("macos-jvm/ios", needs_apple),
        ("linux-jvm", needs_linux),
        ("windows-jvm", needs_windows),
    ) if flag]
    if len(exclusive) > 1:
        raise ToolchainError(
            f"{' and '.join(exclusive)} cannot share one runner"
        )
    linux_os_release = ""
    linux_ldd = ""
    linux_cc = ""
    linux_ld = ""
    host_glibc = None
    windows_os = ""
    windows_cl = ""
    windows_link = ""
    windows_dumpbin = ""
    if needs_linux:
        require_native_linux_x86_64()
        os_release_path = Path("/etc/os-release")
        linux_os_release = (
            os_release_path.read_text(encoding="utf-8") if os_release_path.is_file() else ""
        )
        linux_ldd = _capture(["ldd", "--version"])
        linux_cc = _capture(["cc", "--version"]) or _capture(["gcc", "--version"])
        linux_ld = _capture(["ld", "--version"])
        from linux_elf_verify import parse_ldd_glibc_version

        host_glibc = parse_ldd_glibc_version(linux_ldd)
        if host_glibc is None:
            raise ToolchainError(
                "unable to parse host glibc from ldd --version "
                f"({linux_ldd!r}); Linux x86-64 glibc "
                f">= {EXPECTED_LINUX_GLIBC_LABEL} is required"
            )
        if host_glibc < EXPECTED_LINUX_GLIBC_BASELINE:
            raise ToolchainError(
                f"host glibc {host_glibc[0]}.{host_glibc[1]} is older than "
                f"documented baseline {EXPECTED_LINUX_GLIBC_LABEL}"
            )
    windows_msvc: dict[str, object] = {}
    if needs_windows:
        require_native_windows_x86_64()
        windows_msvc = activate_pinned_msvc_linker(env)
        windows_os = platform.platform()
        windows_cl = _capture(["cl"], env=env)
        windows_link = str(windows_msvc.get("link_banner") or "")
        from windows_pe_verify import find_dumpbin

        dumpbin = find_dumpbin()
        windows_dumpbin = _capture([dumpbin], env=env) if dumpbin else ""
        if not dumpbin:
            raise ToolchainError("dumpbin is required on the Windows rebuild host")
        rustc_verbose_after = _capture(["rustc", "--version", "--verbose"], env=env)
        if rustc_verbose_after:
            windows_msvc["rustc_verbose_after_linker_pin"] = rustc_verbose_after
    if os.environ.get("GITHUB_ACTIONS") == "true":
        if needs_linux:
            if image_os != EXPECTED_LINUX_IMAGE_OS:
                raise ToolchainError(
                    f"GitHub ImageOS {image_os!r} != pinned {EXPECTED_LINUX_IMAGE_OS} "
                    f"(workflow must use runs-on: {EXPECTED_LINUX_RUNS_ON})"
                )
        elif needs_windows:
            if image_os != EXPECTED_WINDOWS_IMAGE_OS:
                raise ToolchainError(
                    f"GitHub ImageOS {image_os!r} != pinned {EXPECTED_WINDOWS_IMAGE_OS} "
                    f"(workflow must use runs-on: {EXPECTED_WINDOWS_RUNS_ON})"
                )
        elif image_os != EXPECTED_GITHUB_IMAGE_OS:
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
        "linux_os_release": linux_os_release,
        "linux_ldd_version": linux_ldd,
        "linux_cc_version": linux_cc,
        "linux_ld_version": linux_ld,
        "linux_glibc_host": (
            f"{host_glibc[0]}.{host_glibc[1]}"
            + (f".{host_glibc[2]}" if host_glibc and host_glibc[2] else "")
            if host_glibc
            else ""
        ),
        "linux_glibc_baseline_documented": EXPECTED_LINUX_GLIBC_LABEL,
        "linux_runs_on": EXPECTED_LINUX_RUNS_ON if needs_linux else "",
        "linux_image_os": EXPECTED_LINUX_IMAGE_OS if needs_linux else "",
        "windows_os": windows_os,
        "windows_cl": windows_cl,
        "windows_link": windows_link,
        "windows_dumpbin": windows_dumpbin,
        "windows_msvc": windows_msvc,
        "windows_runs_on": EXPECTED_WINDOWS_RUNS_ON if needs_windows else "",
        "windows_image_os": EXPECTED_WINDOWS_IMAGE_OS if needs_windows else "",
        "windows_image_version": os.environ.get("ImageVersion", ""),
        "windows_hosted_image_immutable": False,
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
    if "ASCII text" in clang_file:
        raise ToolchainError(
            f"NDK clang at {clang} is a flattened zip symlink ({clang_file!r}). "
            "extract_zip must recreate Unix symlinks such as clang -> clang-18."
        )
    try:
        can_run = subprocess.run(
            [str(clang), "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (PermissionError, OSError) as error:
        raise ToolchainError(
            f"NDK clang could not be executed ({clang}): {error}. "
            "Python zipfile extract must restore Unix symlinks and execute bits."
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
