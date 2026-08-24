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


def rustc_matches(channel: str) -> bool:
    rustc = shutil_which("rustc")
    if rustc is None:
        return False
    completed = subprocess.run(
        [rustc, "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0 and channel in (completed.stdout or "")


def shutil_which(name: str) -> str | None:
    from shutil import which

    return which(name)


def install_rustup_init(dest: Path, triple: str) -> Path:
    expected = RUSTUP_INIT_SHA256.get(triple)
    if expected is None:
        raise InstallError(f"no pinned rustup-init SHA-256 for {triple}")
    payload = download(f"{ARCHIVE_BASE}/{triple}/{rustup_init_filename(triple)}")
    actual = sha256_bytes(payload)
    if actual != expected:
        raise InstallError(f"rustup-init {triple} SHA-256 {actual} != pinned {expected}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.{os.urandom(8).hex()}.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o755)
    try:
        os.write(fd, payload)
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
    try:
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR)
    except OSError:
        pass
    return dest


def ensure_toolchain(channel: str, cargo_home: Path) -> None:
    env = os.environ.copy()
    env["CARGO_HOME"] = str(cargo_home)
    env["RUSTUP_HOME"] = str(cargo_home.parent / "rustup")
    env["PATH"] = f"{cargo_home / 'bin'}{os.pathsep}{env.get('PATH', '')}"
    rustup = cargo_home / "bin" / "rustup"
    if not rustup.is_file():
        raise InstallError(f"rustup missing after rustup-init at {rustup}")
    completed = subprocess.run(
        [str(rustup), "toolchain", "install", channel, "--profile", "minimal"],
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        raise InstallError(f"rustup toolchain install {channel} failed")
    subprocess.run(
        [str(rustup), "default", channel],
        env=env,
        check=False,
    )


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
        help="Exit 0 when rustc --version already contains --channel.",
    )
    args = parser.parse_args(argv)
    try:
        if args.skip_if_present and rustc_matches(args.channel):
            print(f"rustc {args.channel} already on PATH; rustup-init not downloaded")
            return 0
        triple = host_triple()
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
