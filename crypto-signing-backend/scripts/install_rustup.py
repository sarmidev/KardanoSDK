#!/usr/bin/env python3
"""Install rustup-init 1.29.0 after verifying the pinned SHA-256.

Checksums were resolved live on 2026-08-23 from
https://static.rust-lang.org/rustup/archive/1.29.0/<triple>/rustup-init.sha256
and must match the downloaded rustup-init bytes. The rustc channel itself
comes from rust-toolchain.toml (1.97.0), not from this installer.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import stat
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

RUSTUP_VERSION = "1.29.0"
ARCHIVE_BASE = f"https://static.rust-lang.org/rustup/archive/{RUSTUP_VERSION}"

# Values copied from the official rustup-init.sha256 files (2026-08-23).
RUSTUP_INIT_SHA256: dict[str, str] = {
    "aarch64-apple-darwin": (
        "aeb4105778ca1bd3c6b0e75768f581c656633cd51368fa61289b6a71696ac7e1"
    ),
    "x86_64-apple-darwin": (
        "33cf85df9142bc6d29cbc62fa5ca1d4c29622cddb55213a4c1a43c457fb9b2d7"
    ),
    "x86_64-unknown-linux-gnu": (
        "4acc9acc76d5079515b46346a485974457b5a79893cfb01112423c89aeb5aa10"
    ),
    "aarch64-unknown-linux-gnu": (
        "9732d6c5e2a098d3521fca8145d826ae0aaa067ef2385ead08e6feac88fa5792"
    ),
    # Copied from the official rustup-init.exe.sha256 (fetched 2026-08-24).
    "x86_64-pc-windows-msvc": (
        "86478e53f769379d7f0ebfa7c9aa97cb76ca92233f79aa2cc0dbee2efaac73c7"
    ),
}


class InstallError(RuntimeError):
    pass


def host_triple(system: str | None = None, machine: str | None = None) -> str:
    system = (system or platform.system()).lower()
    machine = (machine or platform.machine()).lower()
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return "aarch64-apple-darwin"
    if system == "darwin" and machine in {"x86_64", "amd64"}:
        return "x86_64-apple-darwin"
    if system == "linux" and machine in {"x86_64", "amd64"}:
        return "x86_64-unknown-linux-gnu"
    if system == "linux" and machine in {"arm64", "aarch64"}:
        return "aarch64-unknown-linux-gnu"
    if system == "windows" and machine in {"x86_64", "amd64"}:
        return "x86_64-pc-windows-msvc"
    raise InstallError(f"unsupported rustup-init host {system}/{machine}")


def rustup_init_filename(triple: str) -> str:
    if triple.endswith("-windows-msvc"):
        return "rustup-init.exe"
    return "rustup-init"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "kardano-rustup-installer"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def parse_rustc_release(text: str) -> str:
    """Return the rustc release token. '1.97.0' is not a prefix of '1.97.1'."""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "rustc":
            return parts[1]
    return ""


def rustc_matches(channel: str) -> bool:
    rustc = shutil_which("rustc")
    if rustc is None:
        return False
    env = os.environ.copy()
    env.pop("RUSTUP_TOOLCHAIN", None)
    completed = subprocess.run(
        [rustc, "--version"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return completed.returncode == 0 and parse_rustc_release(completed.stdout or "") == channel


def rustup_home_for(cargo_home: Path) -> Path:
    """Standard rustup layout: ~/.cargo pairs with ~/.rustup, not ~/rustup."""
    override = os.environ.get("RUSTUP_HOME")
    if override:
        return Path(override)
    if cargo_home.name == ".cargo":
        return cargo_home.with_name(".rustup")
    return cargo_home.parent / ".rustup"


def rustup_process_env(cargo_home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["CARGO_HOME"] = str(cargo_home)
    env["RUSTUP_HOME"] = str(rustup_home_for(cargo_home))
    env["PATH"] = f"{cargo_home / 'bin'}{os.pathsep}{env.get('PATH', '')}"
    return env


def rustc_binary_name() -> str:
    return "rustc.exe" if os.name == "nt" else "rustc"


def pinned_toolchain_bin(channel: str, cargo_home: Path) -> Path:
    rustup = rustup_bin(cargo_home)
    if rustup is None:
        raise InstallError(f"rustup missing at {cargo_home / 'bin'}")
    completed = subprocess.run(
        [str(rustup), "run", channel, "rustc", "--print", "sysroot"],
        env=rustup_process_env(cargo_home),
        capture_output=True,
        text=True,
        check=False,
    )
    sysroot = Path((completed.stdout or "").strip())
    toolchain_bin = sysroot / "bin"
    rustc = toolchain_bin / rustc_binary_name()
    if completed.returncode != 0 or not rustc.is_file():
        detail = (completed.stderr or completed.stdout or "").strip()
        raise InstallError(f"rustc {channel} sysroot missing: {detail}")
    return toolchain_bin


def activate_pinned_toolchain(channel: str, cargo_home: Path) -> Path:
    """Put the pinned rustc bin ahead of any image-provided rustc on PATH.

    GitHub-hosted images may ship rustc 1.97.1 as a standalone binary that
    stays first even after rustup installs 1.97.0 and rustup default is set.
    Subsequent CI steps read GITHUB_PATH / GITHUB_ENV when present.
    """
    toolchain_bin = pinned_toolchain_bin(channel, cargo_home)
    cargo_bin = cargo_home / "bin"
    github_path = os.environ.get("GITHUB_PATH")
    if github_path:
        # GITHUB_PATH prepends each line; the last line becomes first on PATH.
        with open(github_path, "a", encoding="utf-8") as handle:
            handle.write(f"{cargo_bin}\n")
            handle.write(f"{toolchain_bin}\n")
    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        with open(github_env, "a", encoding="utf-8") as handle:
            handle.write(f"RUSTUP_TOOLCHAIN={channel}\n")
            handle.write(f"CARGO_HOME={cargo_home}\n")
            handle.write(f"RUSTUP_HOME={rustup_home_for(cargo_home)}\n")
    rustc = toolchain_bin / rustc_binary_name()
    completed = subprocess.run(
        [str(rustc), "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    release = parse_rustc_release(completed.stdout or "")
    if completed.returncode != 0 or release != channel:
        raise InstallError(f"activated rustc {release!r} != {channel}")
    print(f"activated rustc {channel} at {toolchain_bin}")
    return toolchain_bin


def shutil_which(name: str) -> str | None:
    from shutil import which

    return which(name)


def install_rustup_init(dest: Path, triple: str) -> Path:
    expected = RUSTUP_INIT_SHA256.get(triple)
    if expected is None:
        raise InstallError(f"no pinned rustup-init SHA-256 for {triple}")
    filename = rustup_init_filename(triple)
    payload = download(f"{ARCHIVE_BASE}/{triple}/{filename}")
    actual = sha256_bytes(payload)
    if actual != expected:
        raise InstallError(f"rustup-init {triple} SHA-256 {actual} != pinned {expected}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.{os.urandom(8).hex()}.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o755)
    try:
        view = memoryview(payload)
        written = 0
        while written < len(payload):
            written += os.write(fd, view[written:])
        if hasattr(os, "fchmod"):
            try:
                os.fchmod(fd, 0o755)
            except OSError:
                pass
        os.close(fd)
        fd = None
        os.replace(str(tmp), str(dest))
    finally:
        if fd is not None:
            os.close(fd)
        if tmp.exists():
            tmp.unlink()
    on_disk = sha256_bytes(dest.read_bytes())
    if on_disk != expected:
        raise InstallError(
            f"written rustup-init {dest} SHA-256 {on_disk} != pinned {expected}"
        )
    try:
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR)
    except OSError:
        pass
    print(f"verified rustup-init {filename} for {triple} ({len(payload)} bytes)")
    return dest


def rustup_bin(cargo_home: Path) -> Path | None:
    for name in ("rustup", "rustup.exe"):
        candidate = cargo_home / "bin" / name
        if candidate.is_file():
            return candidate
    found = shutil_which("rustup")
    return Path(found) if found else None


def ensure_toolchain(channel: str, cargo_home: Path) -> None:
    env = rustup_process_env(cargo_home)
    rustup = rustup_bin(cargo_home)
    if rustup is None:
        raise InstallError(f"rustup missing after rustup-init at {cargo_home / 'bin'}")
    completed = subprocess.run(
        [str(rustup), "toolchain", "install", channel, "--profile", "minimal"],
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        raise InstallError(f"rustup toolchain install {channel} failed")
    completed = subprocess.run(
        [str(rustup), "default", channel],
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        raise InstallError(f"rustup default {channel} failed")
    activate_pinned_toolchain(channel, cargo_home)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
        / "kardano-rustup-init",
        help="Where to write the verified rustup-init binary.",
    )
    parser.add_argument(
        "--cargo-home",
        type=Path,
        default=Path.home() / ".cargo",
        help="CARGO_HOME used by rustup-init (default: ~/.cargo).",
    )
    parser.add_argument(
        "--channel",
        default="1.97.0",
        help="rustc channel to install after rustup-init (default: 1.97.0).",
    )
    parser.add_argument(
        "--skip-if-present",
        action="store_true",
        help="Skip rustup-init only when rustc already equals --channel and rustup is absent.",
    )
    args = parser.parse_args(argv)
    try:
        existing = rustup_bin(args.cargo_home)
        if (
            args.skip_if_present
            and rustc_matches(args.channel)
            and existing is None
        ):
            print(f"rustc {args.channel} already on PATH; rustup-init not downloaded")
            return 0
        if existing is not None:
            print(f"using existing rustup at {existing}; rustup-init not downloaded")
            ensure_toolchain(args.channel, args.cargo_home)
            print(f"installed rustup channel {args.channel}")
            return 0
        triple = host_triple()
        print(f"downloading rustup-init for {triple}")
        init = install_rustup_init(args.dest, triple)
        completed = subprocess.run(
            [
                str(init),
                "-y",
                "--default-toolchain",
                args.channel,
                "--profile",
                "minimal",
                "--no-modify-path",
            ],
            check=False,
        )
        if completed.returncode != 0:
            raise InstallError("rustup-init failed")
        ensure_toolchain(args.channel, args.cargo_home)
    except InstallError as error:
        print(f"rustup install failed: {error}", file=sys.stderr)
        return 1
    print(f"installed rustup {RUSTUP_VERSION} and rustc {args.channel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
