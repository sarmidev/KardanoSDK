#!/bin/sh
# Rebuild macOS JVM cdylibs (arm64 host + x86_64 cross) into a fresh staging directory.
# Does not write into src/.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$here/rebuild_into_staging.py" --groups macos-jvm "$@"
