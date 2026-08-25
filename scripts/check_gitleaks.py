#!/usr/bin/env python3
"""Run Gitleaks against full git history with redacted output.

Installs the pinned CLI via scripts/install_gitleaks.py when --binary is
omitted. Does not use a third-party GitHub Action wrapper.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Import installer without requiring a package.
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import install_gitleaks  # noqa: E402


def build_command(
    binary: Path,
    source: Path,
    config: Path,
    no_git: bool = False,
    report_path: Path | None = None,
) -> list[str]:
    command = [
        str(binary),
        "detect",
        "--source",
        str(source),
        "--config",
        str(config),
        "--redact",
        "--no-banner",
        "--verbose",
    ]
    if no_git:
        command.append("--no-git")
    else:
        # Single --log-opts string, compatible with pinned Gitleaks v8.30.1.
        # --full-history disables history simplification. --all covers every
        # ref the checkout fetched. -m emits one diff per merge parent so a
        # resolution-only line is visible. Reachable commits are
        # `git rev-list --all`; scanned diffs are `git log` with these opts.
        command.append("--log-opts=--full-history --all -m")
    if report_path is not None:
        command.extend(["--report-format", "json", "--report-path", str(report_path)])
    return command


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--binary", type=Path, default=None)
    parser.add_argument("--no-git", action="store_true")
    parser.add_argument("--report-path", type=Path, default=None)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    binary = args.binary
    if binary is None:
        binary = install_gitleaks.install()
    config = root / ".gitleaks.toml"
    command = build_command(
        binary=binary,
        source=root,
        config=config,
        no_git=args.no_git,
        report_path=args.report_path,
    )
    completed = subprocess.run(command, cwd=root)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
