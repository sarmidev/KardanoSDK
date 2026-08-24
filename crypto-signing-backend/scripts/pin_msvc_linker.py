"""Pin the documented MSVC Hostx64/x64 link.exe on windows-2022.

Selects toolset 14.44.35207, prepends that directory, asserts
``where.exe link`` first result matches, and records ImageOS /
ImageVersion without claiming the hosted image is immutable.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import native_toolchain as toolchain  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    del argv
    env = os.environ.copy()
    try:
        info = toolchain.activate_pinned_msvc_linker(env)
    except toolchain.ToolchainError as error:
        print(f"pin MSVC linker failed: {error}", file=sys.stderr)
        return 1
    github_path = env.get("GITHUB_PATH")
    github_env = env.get("GITHUB_ENV")
    host_dir = Path(str(info["link_path"])).parent
    if github_path:
        with Path(github_path).open("a", encoding="utf-8") as handle:
            handle.write(f"{host_dir}\n")
    if github_env:
        with Path(github_env).open("a", encoding="utf-8") as handle:
            handle.write(f"KARDANO_MSVC_LINK={info['link_path']}\n")
            handle.write(f"KARDANO_MSVC_TOOLSET={info['msvc_toolset']}\n")
            handle.write(
                f"CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER={info['link_path']}\n"
            )
    print(json.dumps(info, indent=2, sort_keys=True))
    print(f"ImageOS={info['image_os']}")
    print(f"ImageVersion={info['image_version']}")
    print("hosted ImageVersion is recorded; the image is not claimed immutable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
