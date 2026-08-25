"""Pin the documented MSVC Hostx64/x64 link.exe on windows-2022.

Selects toolset 14.44.35207 / link 14.44.35228.0 and Windows SDK
10.0.26100.0, prepends those directories, asserts ``where.exe link``
first result matches, and records ImageOS / ImageVersion without
claiming the hosted image is immutable.
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
    sdk = info["windows_sdk"]
    if github_path:
        with Path(github_path).open("a", encoding="utf-8") as handle:
            handle.write(f"{host_dir}\n")
            handle.write(f"{sdk['bin']}\n")
    if github_env:
        with Path(github_env).open("a", encoding="utf-8") as handle:
            handle.write(f"KARDANO_MSVC_LINK={info['link_path']}\n")
            handle.write(f"KARDANO_MSVC_TOOLSET={info['msvc_toolset']}\n")
            handle.write(
                f"CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER={info['link_path']}\n"
            )
            handle.write(f"KARDANO_WINDOWS_SDK_VERSION={sdk['version']}\n")
            handle.write(f"KARDANO_WINDOWS_SDK_DIR={sdk['root']}\n")
            handle.write(f"WindowsSdkDir={sdk['root']}\\\n")
            handle.write(f"WindowsSDKVersion={sdk['version']}\\\n")
            handle.write(f"WindowsSdkVerBinPath={sdk['bin']}\\\n")
            handle.write(f"UCRTVersion={sdk['version']}\\\n")
            handle.write(
                "INCLUDE="
                f"{sdk['include_um']};{sdk['include_ucrt']};{sdk['include_shared']}\n"
            )
            handle.write(f"LIB={sdk['lib_um']};{sdk['lib_ucrt']}\n")
    print(json.dumps(info, indent=2, sort_keys=True))
    print(f"ImageOS={info['image_os']}")
    print(f"ImageVersion={info['image_version']}")
    print("hosted ImageVersion is recorded; the image is not claimed immutable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
