#!/usr/bin/env python3
"""Install Android NDK 27.2.12479018 (r27c) after verifying Google's SHA-1.

Google's repository2-3.xml (fetched 2026-08-23) publishes SHA-1 only for
these zips. This installer verifies that official SHA-1, then records the
SHA-256 of the same bytes in the install report. It does not invent a
SHA-256 pin before the download.

If ANDROID_NDK_HOME already points at revision 27.2.12479018, the zip is
not downloaded — unless `--require-dest` is set, in which case only the
`--dest` tree is accepted. macos-26 runners export 27.3.13750724 and must
use `--require-dest`.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

NDK_REVISION = "27.2.12479018"
NDK_RELEASE = "r27c"
REPO_XML = "https://dl.google.com/android/repository/repository2-3.xml"
DOWNLOAD_BASE = "https://dl.google.com/android/repository"

# Official SHA-1 values from repository2-3.xml package ndk;27.2.12479018
# (resolved 2026-08-23). Not copied from a prior audit note.
NDK_ZIP_SHA1: dict[str, tuple[str, int]] = {
    "android-ndk-r27c-darwin.zip": ("0217c10ffbec496bb9fbfbb3c6fc2477c6b77297", 836128272),
    "android-ndk-r27c-linux.zip": ("090e8083a715fdb1a3e402d0763c388abb03fb4e", 663987688),
    "android-ndk-r27c-windows.zip": ("ac5f7762764b1f15341094e148ad4f847d050c38", 781511249),
}


class InstallError(RuntimeError):
    pass


def zip_name_for(system: str | None = None) -> str:
    system = (system or platform.system()).lower()
    if system == "darwin":
        return f"android-ndk-{NDK_RELEASE}-darwin.zip"
    if system == "linux":
        return f"android-ndk-{NDK_RELEASE}-linux.zip"
    if system == "windows":
        return f"android-ndk-{NDK_RELEASE}-windows.zip"
    raise InstallError(f"unsupported NDK host {system}")


def ndk_revision(ndk_home: Path) -> str:
    props = ndk_home / "source.properties"
    if not props.is_file():
        return ""
    for line in props.read_text(encoding="utf-8").splitlines():
        if line.startswith("Pkg.Revision"):
            return line.split("=", 1)[-1].strip()
    return ""


def dest_ndk(dest: Path) -> Path | None:
    extracted = dest / f"android-ndk-{NDK_RELEASE}"
    if ndk_revision(extracted) == NDK_REVISION:
        return extracted
    return None


def existing_ndk() -> Path | None:
    for key in ("ANDROID_NDK_HOME", "ANDROID_NDK_ROOT"):
        value = os.environ.get(key)
        if value:
            path = Path(value)
            if ndk_revision(path) == NDK_REVISION:
                return path
    default = Path.home() / "Library" / "Android" / "sdk" / "ndk" / NDK_REVISION
    if ndk_revision(default) == NDK_REVISION:
        return default
    linux_default = Path.home() / "Android" / "Sdk" / "ndk" / NDK_REVISION
    if ndk_revision(linux_default) == NDK_REVISION:
        return linux_default
    return None


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_to(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "kardano-ndk-installer"})
    with urllib.request.urlopen(request, timeout=600) as response, dest.open("wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)


def extract_zip(archive: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(dest)
    extracted = dest / f"android-ndk-{NDK_RELEASE}"
    if not extracted.is_dir():
        raise InstallError(f"zip did not contain android-ndk-{NDK_RELEASE}")
    return extracted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / "kardano-ndk",
        help="Directory that will hold the extracted NDK (if a download is needed).",
    )
    parser.add_argument(
        "--cache-zip",
        type=Path,
        help="Optional path to write/reuse the downloaded zip.",
    )
    parser.add_argument(
        "--print-home",
        action="store_true",
        help="Print the NDK home path on stdout.",
    )
    parser.add_argument(
        "--require-dest",
        action="store_true",
        help=(
            "Ignore ANDROID_NDK_HOME/ROOT and default SDK copies. Only accept "
            f"or install revision {NDK_REVISION} under --dest. Needed on "
            "macos-26 runners whose image default is 27.3.13750724."
        ),
    )
    args = parser.parse_args(argv)
    try:
        present = dest_ndk(args.dest) if args.require_dest else existing_ndk()
        if present is not None:
            if args.print_home:
                print(present)
            else:
                print(f"using existing NDK {NDK_REVISION} at {present}", file=sys.stderr)
            return 0
        name = zip_name_for()
        expected_sha1, expected_size = NDK_ZIP_SHA1[name]
        zip_path = args.cache_zip or (args.dest / name)
        if not zip_path.is_file():
            print(
                f"downloading {name} from {DOWNLOAD_BASE} ({expected_size} bytes)",
                file=sys.stderr,
            )
            download_to(f"{DOWNLOAD_BASE}/{name}", zip_path)
        actual_size = zip_path.stat().st_size
        if actual_size != expected_size:
            raise InstallError(f"{name} size {actual_size} != publisher {expected_size}")
        actual_sha1 = sha1_file(zip_path)
        if actual_sha1 != expected_sha1:
            raise InstallError(f"{name} SHA-1 {actual_sha1} != publisher {expected_sha1}")
        actual_sha256 = sha256_file(zip_path)
        print(
            f"{name} SHA-1 matches Google repository2-3.xml ({REPO_XML})",
            file=sys.stderr,
        )
        print(
            f"{name} SHA-256 (computed after SHA-1 match): {actual_sha256}",
            file=sys.stderr,
        )
        extracted = extract_zip(zip_path, args.dest)
        if ndk_revision(extracted) != NDK_REVISION:
            raise InstallError(
                f"extracted NDK revision {ndk_revision(extracted)!r} != {NDK_REVISION}"
            )
        if args.print_home:
            print(extracted)
        else:
            print(f"installed NDK {NDK_REVISION} -> {extracted}", file=sys.stderr)
    except InstallError as error:
        print(f"NDK install failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
