#!/usr/bin/env bash
# Build the pinned native Linux x86_64 Free Pascal compiler, RTL and packages.
set -euo pipefail

version=3.2.2
source_sha=d542e349de246843d4f164829953d1f5b864126c5b62fd17c9b45b33e23d2f44
source_archive=
work_dir=
output_dir=
bootstrap=fpc
jobs=2
same_version=0
recipe_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)

usage() {
  printf '%s\n' 'Usage: build.sh --source ARCHIVE --work-dir EMPTY_DIR --output-dir DIR [--bootstrap /path/to/fpc] [--jobs 2] [--allow-same-version-bootstrap]'
}
fail() { printf 'FPC build: %s\n' "$*" >&2; exit 1; }
while (($#)); do
  case "$1" in
    --source|--work-dir|--output-dir|--bootstrap|--jobs)
      (($# >= 2)) || fail "Missing value for $1"
      case "$1" in
        --source) source_archive=$2;;
        --work-dir) work_dir=$2;;
        --output-dir) output_dir=$2;;
        --bootstrap) bootstrap=$2;;
        --jobs) jobs=$2;;
      esac
      shift 2;;
    --allow-same-version-bootstrap) same_version=1; shift;;
    --help|-h) usage; exit 0;;
    *) usage; fail "Unknown option: $1";;
  esac
done
[[ -n $source_archive && -n $work_dir && -n $output_dir ]] || { usage; exit 1; }
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || fail 'Run inside native/emulated Linux x86_64, not ARM64 or macOS'
[[ $jobs =~ ^[1-9][0-9]*$ ]] || fail '--jobs must be a positive integer'
for tool in make gcc as ld ar ranlib install tar gzip sha256sum python3 realpath readlink file readelf; do
  command -v "$tool" >/dev/null || fail "Missing build dependency: $tool"
done
bootstrap=$(command -v "$bootstrap") || fail 'Bootstrap FPC was not found'
bootstrap=$(realpath "$bootstrap")
source_archive=$(realpath "$source_archive")
[[ -f $source_archive ]] || fail 'Source archive is not a regular file'
printf '%s  %s\n' "$source_sha" "$source_archive" | sha256sum -c -
mkdir -p -- "$work_dir" "$output_dir"
work_dir=$(realpath "$work_dir")
output_dir=$(realpath "$output_dir")
[[ $work_dir != *[[:space:]]* ]] || fail 'Upstream Makefiles require a work directory without whitespace'
[[ -z $(find "$work_dir" -mindepth 1 -maxdepth 1 -print -quit) ]] || fail 'Work directory must be empty; existing data is never deleted'
python3 - "$work_dir" "$output_dir" <<'PY'
import shutil,sys
for path,minimum in [(sys.argv[1],4*1024**3),(sys.argv[2],1024**3)]:
    free=shutil.disk_usage(path).free
    if free<minimum:
        raise SystemExit(f'Insufficient space at {path}: {free/1024**3:.2f} GiB; need at least {minimum/1024**3:.0f} GiB')
PY
artifact="$output_dir/fpc-$version-linux-x86_64.tar.gz"
[[ ! -e $artifact && ! -e $artifact.sha256 && ! -e $output_dir/BUILD.log ]] || fail 'Output artifact/log already exists; select a fresh output directory'
bootstrap_version=$("$bootstrap" -iV)
[[ $("$bootstrap" -iTP) == x86_64 && $("$bootstrap" -iTO) == linux ]] || fail 'Bootstrap compiler must target native x86_64-linux'
override=()
case "$bootstrap_version" in
  3.0.4|3.2.0) ;;
  3.2.2)
    ((same_version == 1)) || fail 'Upstream officially accepts bootstrap 3.0.4 or 3.2.0; use --allow-same-version-bootstrap to explicitly permit 3.2.2'
    override=(OVERRIDEVERSIONCHECK=1);;
  *) fail "Unsupported bootstrap $bootstrap_version; require 3.0.4, 3.2.0 or explicitly permitted 3.2.2";;
esac
exec > >(tee "$output_dir/BUILD.log") 2>&1
printf 'Building FPC %s using bootstrap %s; target x86_64-linux\n' "$version" "$bootstrap_version"
[[ ${#override[@]} == 0 ]] || printf '%s\n' 'Explicit same-version bootstrap override is enabled and will be recorded.'
if [[ -z ${SOURCE_DATE_EPOCH:-} ]]; then
  SOURCE_DATE_EPOCH=$(python3 - "$source_archive" <<'PY'
import sys,tarfile
with tarfile.open(sys.argv[1]) as archive:
    print(int(max(member.mtime for member in archive)))
PY
)
fi
[[ $SOURCE_DATE_EPOCH =~ ^[0-9]+$ ]] || fail 'SOURCE_DATE_EPOCH must be an integer'
export SOURCE_DATE_EPOCH TZ=UTC LC_ALL=C

tar --no-same-owner --no-same-permissions -xzf "$source_archive" -C "$work_dir"
source_dir="$work_dir/fpc-$version"
prefix="$work_dir/stage/opt/zed-delphi/fpc/$version"
common=(CPU_TARGET=x86_64 OS_TARGET=linux OPT=-O2 ALLTARGET=all "${override[@]}")
# Confirmed against the pinned archive: all cycles compiler, then builds RTL and packages.
make -C "$source_dir" -j"$jobs" all "FPC=$bootstrap" "${common[@]}"
# install needs a freshly built fpcmake, without pulling in the optional full utilities/IDE.
make -C "$source_dir/utils/fpcm" -j"$jobs" all "FPC=$source_dir/compiler/ppcx64" "FPCFPMAKE=$source_dir/compiler/ppcx64" CPU_TARGET=x86_64 OS_TARGET=linux OPT=-O2
make -C "$source_dir" install "FPC=$source_dir/compiler/ppcx64" "INSTALL_PREFIX=$prefix" INSTALLTARGET=install "${common[@]}"
[[ -x $prefix/bin/fpc && -x $prefix/lib/fpc/$version/ppcx64 ]] || fail 'Expected compiler/driver were not installed'
[[ -f $prefix/lib/fpc/$version/units/x86_64-linux/rtl/system.ppu ]] || fail 'RTL was not installed'
[[ -f $prefix/lib/fpc/$version/units/x86_64-linux/fcl-json/fpjson.ppu ]] || fail 'FCL packages were not installed'
mv "$prefix/bin/fpc" "$prefix/bin/fpc-driver"
install -m 755 "$recipe_dir/fpc-wrapper.sh" "$prefix/bin/fpc"
install -d "$prefix/etc" "$prefix/share/zed-delphi/build-recipe"
install -m 644 "$recipe_dir/fpc.cfg" "$prefix/etc/fpc.cfg"
install -m 644 "$recipe_dir/"{build.sh,fpc-wrapper.sh,fpc.cfg,smoke.pas,provenance.py,README.md} "$prefix/share/zed-delphi/build-recipe/"
mkdir -p "$work_dir/smoke" "$work_dir/smoke-units"
"$prefix/bin/fpc" -Mdelphi -g -gl -gw3 -O- "-FU$work_dir/smoke-units" "-o$work_dir/smoke/DelphiSmoke" "$recipe_dir/smoke.pas"
[[ $("$work_dir/smoke/DelphiSmoke") == 'ASTRA_FPC_SMOKE_OK:42' ]] || fail 'Delphi-mode compiler/RTL/FCL smoke failed'
# Moving only the staged package proves that the wrapper/config do not depend on the build prefix.
relocated="$work_dir/relocated prefix with spaces"
mv "$prefix" "$relocated"
"$relocated/bin/fpc" -Mdelphi "-FU$work_dir/smoke-units" "-o$work_dir/smoke/RelocatedSmoke" "$recipe_dir/smoke.pas"
[[ $("$work_dir/smoke/RelocatedSmoke") == 'ASTRA_FPC_SMOKE_OK:42' ]] || fail 'Relocated compiler smoke failed'
mv "$relocated" "$prefix"
python3 "$recipe_dir/provenance.py" --prefix "$prefix" --source-dir "$source_dir" --source-archive "$source_archive" --bootstrap "$bootstrap" --bootstrap-version "$bootstrap_version" --same-version-override "$same_version"
cp "$prefix/share/zed-delphi/provenance.json" "$output_dir/provenance.json"
source_copy="$output_dir/fpc-$version.source.tar.gz"
if [[ $source_archive != "$source_copy" ]]; then
  [[ ! -e $source_copy ]] || fail 'Companion source archive already exists in output directory'
  cp "$source_archive" "$source_copy"
fi
tar --sort=name --format=gnu --mtime="@$SOURCE_DATE_EPOCH" --owner=0 --group=0 --numeric-owner -C "$work_dir/stage" -cf - opt | gzip -n > "$artifact"
(cd "$output_dir" && sha256sum "$(basename "$artifact")" > "$(basename "$artifact").sha256" && sha256sum "$(basename "$artifact")" "$(basename "$source_copy")" provenance.json > SHA256SUMS)
printf 'Built and smoke-tested package: %s\n' "$artifact"
printf '%s\n' 'A non-Astra build is a Linux candidate for Astra validation, not confirmed Astra compatibility.'
du -sh "$work_dir" "$prefix" "$artifact"
