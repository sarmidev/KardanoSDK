#!/bin/sh
# Rebuild iOS static libs (device arm64 + simulator arm64) into staging.
# Does not write into src/.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$here/rebuild_into_staging.py" --groups ios "$@"
