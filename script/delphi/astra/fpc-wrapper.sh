#!/usr/bin/env sh
# Locate this package even when bin/fpc is reached through a symlink on PATH.
set -eu
launcher=$(readlink -f -- "$0")
prefix=$(CDPATH= cd -- "$(dirname -- "$launcher")/.." && pwd -P)
export FPCDIR="$prefix/lib/fpc/3.2.2"
export ZED_DELPHI_FPC_ROOT="$FPCDIR"
if command -v gcc >/dev/null 2>&1; then
  ZED_DELPHI_GCC_LIBDIR=$(dirname -- "$(gcc -print-libgcc-file-name)")
else
  ZED_DELPHI_GCC_LIBDIR=/usr/lib/x86_64-linux-gnu
fi
export ZED_DELPHI_GCC_LIBDIR
# -n isolates package units from an unrelated host /etc/fpc.cfg/bootstrap install.
exec "$prefix/bin/fpc-driver" "-Xp$FPCDIR/" -n "@$prefix/etc/fpc.cfg" "$@"
