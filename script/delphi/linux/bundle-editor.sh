#!/usr/bin/env bash
# Follow bundle-linux's native editor/CLI layout without compiling remote-server.
set -euo pipefail
cd "$(dirname "$0")/../../.."
export ZED_BUNDLE=true
export RELEASE_VERSION="$(script/get-crate-version zed)"
script/generate-licenses
host=$(rustc --version --verbose | sed -n 's/^host: //p')
target_dir=${CARGO_TARGET_DIR:-target}
export CC=${CC:-$(command -v clang)}
lld=${LLD:-$("$CC" -print-prog-name=ld.lld)}
[[ $lld == /* && -x $lld ]] || { echo 'Set LLD to an absolute executable linker path' >&2; exit 1; }
version=$("$lld" --version)
[[ $version =~ LLD\ ([0-9]+)\. && ${BASH_REMATCH[1]} -ge 12 ]] || { echo 'LLD >=12 required' >&2; exit 1; }
cargo --config .cargo/bundle-config.toml rustc --locked --release --target "$host" --package zed --bin zed -- -C linker="$CC" -C llvm-args=-addrsig -C link-arg=-fuse-ld=lld -C link-arg="--ld-path=$lld" -C link-arg=-Wl,--icf=safe
cargo --config .cargo/bundle-config.toml build --locked --release --target "$host" --package cli
channel=$(<crates/zed/RELEASE_CHANNEL)
suffix=""
[[ $channel == stable ]] || suffix="-$channel"
temporary=$(mktemp -d "$target_dir/editor-bundle.XXXXXX")
trap 'rm -rf "$temporary"' EXIT
app="$temporary/zed$suffix.app"
mkdir -p "$app/bin" "$app/libexec" "$app/lib" "$target_dir/release"
llvm-objcopy --strip-unneeded "$target_dir/$host/release/zed" "$app/libexec/zed-editor"
llvm-objcopy --strip-debug --discard-all "$target_dir/$host/release/cli" "$app/bin/zed"
# Match bundle-linux's host GLib exclusion: loading host modules against another GLib breaks symbols.
python3 - "$target_dir/$host/release/zed" "$app/lib" <<'PY'
import pathlib,re,shutil,subprocess,sys
result=subprocess.run(['ldd',sys.argv[1]],check=True,capture_output=True,text=True)
if 'not found' in result.stdout:
    raise SystemExit('Missing editor runtime libraries')
excluded=re.compile(r'^(?:libc|libgcc_s|libm|libpthread|libdl|libasound|libglib-2\.0|libgobject-2\.0|libgio-2\.0|libgmodule-2\.0|libpcre|libpcre2-8|libmount|libblkid|libselinux|libffi|libresolv|libz)\.so(?:\.|$)')
for line in result.stdout.splitlines():
    match=re.search(r'=>\s+(/\S+)',line)
    if match and not excluded.match(pathlib.Path(match[1]).name):
        shutil.copy2(match[1],sys.argv[2])
PY
for size in 512 1024; do
  extra=""; [[ $size != 1024 ]] || extra=@2x
  mkdir -p "$app/share/icons/hicolor/${size}x${size}/apps"
  cp "crates/zed/resources/app-icon$suffix$extra.png" "$app/share/icons/hicolor/${size}x${size}/apps/zed.png"
done
export DO_STARTUP_NOTIFY=true APP_CLI=zed APP_ICON=zed APP_ARGS=%U APP_NAME='Zed Delphi'
mkdir -p "$app/share/applications"
envsubst < crates/zed/resources/zed.desktop.in > "$app/share/applications/dev.zed.Zed-Delphi.desktop"
cp assets/licenses.md "$app/licenses.md"
tar -czf "$target_dir/release/zed-linux-$(uname -m).tar.gz" -C "$temporary" "zed$suffix.app"
