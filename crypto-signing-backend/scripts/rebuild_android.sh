#!/bin/sh
# Rebuild Android jniLibs (arm64-v8a, armeabi-v7a, x86, x86_64) into staging.
# Requires ANDROID_NDK_HOME = NDK 27.2.12479018 and cargo-ndk 4.1.2.
# Does not write into src/.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$here/rebuild_into_staging.py" --groups android "$@"
