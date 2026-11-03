# Linux package for Zed Delphi

This entrypoint builds the current fork editor and CLI using the Cargo configuration, linker flags and application layout from `script/bundle-linux`. The default compact package omits remote-server. Add `--with-remote-server` to use the full existing `script/bundle-linux --skip-sentry` instead. Both paths generate licenses and package the native Linux application. It does not publish artifacts or upload debug symbols. Telemetry removal belongs to the fork's source changes, not a runtime environment toggle in this script.

Use a dedicated Linux x86_64 machine/container for Astra Linux 1.8 x86_64. Native aarch64 Linux builds are also allowed, but do not produce an x86_64 application. Build on Astra itself or an appropriately old compatible system; a successful Debian/Ubuntu build is not Astra acceptance. The target machine still needs compatible glibc, graphics drivers, Vulkan, and the host libraries intentionally excluded by the bundler.

Requires Python 3.9+, the repository's pinned Rust toolchain, Clang, LLD >=12, llvm-objcopy and the libraries/tools listed in `script/linux`. Inspect that script before installing dependencies on Astra: repository and package availability differ. The entrypoint does not install OS packages. The bundler may fetch Rust targets, Cargo dependencies and cargo-about 0.8.2 for license generation. Keep this checkout, Cargo.lock and access to those sources for rebuilding.

```sh
# No downloads, Rust commands or build during preflight.
CARGO_TARGET_DIR=/large-disk/zed-target \
  python3 script/delphi/linux/build.py \
  --output-dir /large-disk/results/zed-delphi-run1 --preflight-only

CARGO_TARGET_DIR=/large-disk/zed-target CARGO_BUILD_JOBS=2 \
  CC=/usr/bin/clang LLD=/usr/bin/ld.lld \
  python3 script/delphi/linux/build.py \
  --output-dir /large-disk/results/zed-delphi-run1
```

Default preflight requires **30 GiB free disk** at both build and output locations and **8 GiB available RAM**, respecting container limits. These are conservative minimum budgets, not measured guarantees. `--min-free-gib` (alias `--min-disk-gib`) and `--min-memory-gib` permit explicit changes for a measured environment; lowering them cannot make an undersized build reliable. The output directory must not already exist. Target paths must have no whitespace because the upstream bundler has unquoted paths. Jobs, CC, CXX, LLD, and REMOTE_SERVER_TARGET remain explicit environment overrides; RUSTFLAGS overrides are rejected by the bundler contract. When requested, default remote-server uses musl and needs musl-gcc. Cargo profile environment overrides are preserved and recorded; this recipe does not change the repository profile defaults.

The output contains the app archive, optional remote-server archive, BUILD.log, provenance, SHA256SUMS, source commit/status/diff and a source snapshot of tracked and untracked non-ignored files. Git metadata, target outputs and ignored files are excluded; any required ignored source inputs must be supplied separately. No bit-identical output is promised. On build failure, logs remain; use a new output directory for the next attempt. Generated `assets/licenses.md` and the Cargo target directory are owned outputs of the existing bundler.

Before accepting the archive, the script extracts it and runs `ldd` on both bundled CLI and editor, failing for missing libraries. This checks the build machine's loader only, not rendering or project/debug behavior. Repeat loader checks on Astra, then launch the app under a real desktop session and test Delphi editing, completion, FPC project build/run, breakpoint/locals/step and cancellation. Existing `script/delphi/tests/smoke_lldb.py` checks real FPC/DAP behavior separately; successful protocol smoke does not prove Zed UI acceptance. Embarcadero compilation/debug still requires its licensed Windows tools.

## Run the packaged editor

Extract the archive for your CPU architecture into a separate folder, then run
its CLI (the current development channel uses `zed-dev.app`):

```sh
tar -xzf zed-linux-x86_64.tar.gz
./zed-dev.app/bin/zed /absolute/path/to/project
```

Install FPC and a compatible CodeLLDB separately. Copy
`script/delphi/examples/multi_unit` to a writable folder, set the CodeLLDB binary
path in Zed settings if it is not managed by Zed, then select the example's build,
run and debug tasks. The project enables `pasls`; install/configure it using
[the language-server guide](../PASLS.md) or disable that server until installed.

The package is not a system installer. It includes the editor, CLI and selected
shared libraries, but still uses host glibc/GLib/audio/graphics libraries. Do not
rename an Ubuntu24.04 archive as an Astra package without testing its loader and
GUI on the actual target release.
