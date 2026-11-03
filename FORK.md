# Zed Delphi

This fork adds built-in Object Pascal editing, compiler tasks and debugger integration,
and removes application telemetry collectors and senders. The Linux ARM64 application has passed local build/run/debug acceptance.
It does not include the RAD Studio form designer.

The source baseline is `8a47b3510959f5daba5c8b45bc3d04d68c5bd551` from
https://github.com/zed-industries/zed. Local work is on
`feature/delphi-no-telemetry`.

## Use and build

See [Delphi setup](docs/src/languages/delphi.md) for Free Pascal, Lazarus,
Embarcadero MSBuild, local debugging and Windows SSH transports. External compilers,
language servers and debuggers are not bundled. An Embarcadero installation and
its license must be supplied by the user.

See the [tested pasls setup](script/delphi/PASLS.md) and the
[Free Pascal build recipe for Astra validation](script/delphi/astra/README.md)
for separately built language tools.

Follow the upstream platform build prerequisites in [development](docs/src/development.md).
The pinned Rust toolchain is in `rust-toolchain.toml`. On macOS, use a full Xcode
developer directory for the build, without changing the system-wide selection:

```sh
. "$HOME/.cargo/env"
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer cargo build --locked -p zed --bin zed
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer cargo run --locked -p zed --bin zed
```

The Linux packager is documented in [Linux builds](script/delphi/linux/README.md).
The fork is published at https://github.com/ghost-raven1/zed-delphi.
Keep separate from an existing Zed installation while evaluating this fork.

## Privacy and updates

See [privacy behavior](docs/src/telemetry.md). Legacy telemetry settings cannot
enable the removed collectors. Local troubleshooting logs, explicitly submitted
feedback and requested network features remain available. External tools and hosted
services have their own behavior.

Upstream application updates and symbol uploads in the platform bundling scripts
are disabled. Updating this fork requires a reviewed rebuild. A pending Windows
upstream update is not applied on exit.

Zed's remote editor backend must also come from this fork. Official remote-server
downloads are disabled, and SSH, WSL and Docker use a separate
`zed-delphi-remote-server-*` filename to avoid reusing stock binaries.

Set `ZED_DELPHI_REMOTE_SERVER_DIR` in the editor's environment to a directory
containing your own builds for the destination platform:

```text
remote-artifacts/
  linux-x86_64/remote-server.gz
  macos-aarch64/remote-server.gz
  windows-x86_64/remote-server.zip
```

Unix files are gzip-compressed `remote-server` binaries. A Windows ZIP must contain
`remote_server.exe` at its root. Use matching fork revisions on both ends. The
directory is a trusted, explicitly supplied build source, not an artifact
signature verifier. Development builds can also use the upstream
`ZED_BUILD_REMOTE_SERVER` source-build workflow. The Delphi Python SSH helpers
are separate from Zed's remote editor backend.

## Verification

Run from the checkout root:

```sh
python3 -m unittest discover -s script/delphi/tests -v
python3 script/delphi/tests/smoke_lldb.py --fpc /path/to/fpc --lldb-dap /path/to/lldb-dap
cargo test --locked -p telemetry
cargo test --locked -p grammars --features load-grammars --test delphi
cargo test --locked -p client telemetry
cargo test --locked -p auto_update
cargo test --locked -p dap_adapters delphi
```

## Acceptance status (2026-11-04)

- Ubuntu 24.04 ARM64: release editor and CLI built; packaged loader checks passed.
  The extracted package opened a multi-unit Object Pascal project in Xvfb/Mesa.
  Native highlighting, pasls definition/completion/diagnostics, FPC build/run,
  CodeLLDB breakpoint, call stack, integer locals, step and exit 0 passed.
  Project paths containing spaces were also exercised in the editor debugger.
- Python helpers: 30 tests, 29 passed and one Windows-only test skipped on Linux.
- macOS ARM64: helper, grammar, telemetry and standalone FPC/DAP checks passed;
  the complete macOS application has not passed acceptance.
- Linux x86_64: native Ubuntu CI release build is being prepared; no Astra result
  is inferred from Ubuntu or ARM64 results.
- Windows: integration source and CI recipe exist; commercial Delphi, remote
  Windows sessions and full application acceptance remain unverified.

FPC is not a drop-in replacement for every Embarcadero Delphi project. Lazarus,
VCL/FMX applications and complex Pascal debugger expressions require separate
acceptance. External compilers, language servers and debug adapters must be
installed; there is no visual DFM/FMX designer. This is a source fork with a
verified Linux scenario, not a claim of complete RAD Studio compatibility.
