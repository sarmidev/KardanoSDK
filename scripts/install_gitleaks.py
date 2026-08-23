#!/usr/bin/env python3
"""Download Gitleaks and verify the official SHA-256 before install.

Never commit the binary. Checksums were resolved live on 2026-08-23 from:

  https://github.com/gitleaks/gitleaks/releases/latest
    → tag v8.30.1 (published 2026-03-21T02:17:58Z)
  https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_checksums.txt
    → SHA-256 061476c21adaf5441516f96f185c1a4706a83cd6329b9b38762271b3d4a52fae

Archive SHA-256 values below are copied from that checksums.txt after the
checksums file itself hashed to the recorded digest. They are not taken from
a prior audit report.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import stat
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

GITLEAKS_VERSION = "8.30.1"
RELEASE_TAG = f"v{GITLEAKS_VERSION}"
RELEASE_BASE = (
    f"https://github.com/gitleaks/gitleaks/releases/download/{RELEASE_TAG}"
)
CHECKSUMS_NAME = f"gitleaks_{GITLEAKS_VERSION}_checksums.txt"
CHECKSUMS_URL = f"{RELEASE_BASE}/{CHECKSUMS_NAME}"
CHECKSUMS_SHA256 = "061476c21adaf5441516f96f185c1a4706a83cd6329b9b38762271b3d4a52fae"

# Subset of the official checksums.txt, keyed by archive filename.
ARCHIVE_SHA256: dict[str, str] = {
    f"gitleaks_{GITLEAKS_VERSION}_darwin_arm64.tar.gz": (
        "b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5"
    ),
    f"gitleaks_{GITLEAKS_VERSION}_darwin_x64.tar.gz": (
        "dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709"
    ),
    f"gitleaks_{GITLEAKS_VERSION}_linux_arm64.tar.gz": (
        "e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080"
    ),
    f"gitleaks_{GITLEAKS_VERSION}_linux_x64.tar.gz": (
        "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"
    ),
}

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEST = REPO_ROOT / ".gitleaks-bin" / f"gitleaks-{GITLEAKS_VERSION}"


class InstallError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_checksum(data: bytes, expected: str, label: str) -> None:
    actual = sha256_bytes(data)
    if actual != expected:
        raise InstallError(f"{label} SHA-256 {actual} != pinned {expected}")


def archive_name_for(system: str | None = None, machine: str | None = None) -> str:
    system = (system or platform.system()).lower()
    machine = (machine or platform.machine()).lower()
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        name = f"gitleaks_{GITLEAKS_VERSION}_darwin_arm64.tar.gz"
    elif system == "darwin" and machine in {"x86_64", "amd64"}:
        name = f"gitleaks_{GITLEAKS_VERSION}_darwin_x64.tar.gz"
    elif system == "linux" and machine in {"x86_64", "amd64"}:
        name = f"gitleaks_{GITLEAKS_VERSION}_linux_x64.tar.gz"
    elif system == "linux" and machine in {"arm64", "aarch64"}:
        name = f"gitleaks_{GITLEAKS_VERSION}_linux_arm64.tar.gz"
    else:
        raise InstallError(f"unsupported platform {system}/{machine}")
    if name not in ARCHIVE_SHA256:
        raise InstallError(f"no pinned checksum for {name}")
    return name


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "kardano-gitleaks-installer"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _read_tar_member(archive_path: Path) -> bytes:
    with tarfile.open(archive_path, "r:gz") as archive:
        try:
            member = archive.getmember("gitleaks")
        except KeyError as error:
            raise InstallError("archive member gitleaks is missing") from error
        if member.mode & 0o002:
            raise InstallError("archive member gitleaks is world-writable")
        src = archive.extractfile(member)
        if src is None:
            raise InstallError("archive member gitleaks is missing")
        return src.read()


def _read_zip_member(archive_path: Path) -> bytes:
    with zipfile.ZipFile(archive_path) as archive:
        info = archive.getinfo("gitleaks")
        # Zip external attributes: UNIX mode is in the high 16 bits when present.
        unix_mode = (info.external_attr >> 16) & 0o7777
        if unix_mode and unix_mode & 0o002:
            raise InstallError("archive member gitleaks is world-writable")
        return archive.read("gitleaks")


def _write_atomic_binary(dest: Path, payload: bytes) -> None:
    if dest.is_symlink():
        raise InstallError("refusing to write through a destination symlink")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.{os.urandom(8).hex()}.tmp")
    fd = None
    try:
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o755)
        os.write(fd, payload)
        os.fchmod(fd, 0o755)
        os.close(fd)
        fd = None
        if dest.is_symlink():
            raise InstallError("refusing to write through a destination symlink")
        os.replace(str(tmp), str(dest))
        os.chmod(dest, 0o755)
    except Exception:
        if fd is not None:
            os.close(fd)
        if tmp.exists() or tmp.is_symlink():
            tmp.unlink()
        raise


def extract_binary(archive_path: Path, archive_name: str, dest: Path) -> None:
    if dest.is_symlink():
        raise InstallError("refusing to write through a destination symlink")
    if archive_name.endswith(".zip"):
        payload = _read_zip_member(archive_path)
    else:
        payload = _read_tar_member(archive_path)
    _write_atomic_binary(dest, payload)


def install(
    dest: Path = DEFAULT_DEST,
    system: str | None = None,
    machine: str | None = None,
    checksums_bytes: bytes | None = None,
    archive_bytes: bytes | None = None,
) -> Path:
    archive_name = archive_name_for(system, machine)
    if checksums_bytes is None:
        checksums_bytes = download(CHECKSUMS_URL)
    verify_checksum(checksums_bytes, CHECKSUMS_SHA256, CHECKSUMS_NAME)
    expected_archive = ARCHIVE_SHA256[archive_name]
    listed = None
    for line in checksums_bytes.decode("ascii").splitlines():
        if line.endswith(archive_name):
            listed = line.split()[0]
            break
    if listed != expected_archive:
        raise InstallError(
            f"{archive_name} digest in checksums.txt ({listed}) != pinned {expected_archive}"
        )
    if archive_bytes is None:
        archive_bytes = download(f"{RELEASE_BASE}/{archive_name}")
    verify_checksum(archive_bytes, expected_archive, archive_name)
    with tempfile.TemporaryDirectory() as tmp:
        archive_path = Path(tmp) / archive_name
        archive_path.write_bytes(archive_bytes)
        extract_binary(archive_path, archive_name, dest)
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help=f"Output path for the gitleaks binary (default: {DEFAULT_DEST})",
    )
    args = parser.parse_args(argv)
    try:
        dest = install(dest=args.dest)
    except InstallError as error:
        print(f"gitleaks install failed: {error}", file=sys.stderr)
        return 1
    print(f"installed gitleaks {GITLEAKS_VERSION} -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
