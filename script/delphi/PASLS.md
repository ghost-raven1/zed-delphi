# Tested Free Pascal language server

The real `pasls` process was built and tested on macOS ARM64 with Free Pascal 3.2.2. The smoke test exercises initialization, opening valid source, definition lookup, completion, a syntax error, clearing that error after repair, and orderly shutdown. This verifies the server protocol, not the complete Zed UI.

Sources used without local patches:

| Component | Source revision |
| --- | --- |
| [pasls](https://github.com/genericptr/pascal-language-server) | `818f6330b721ed5c89d1fd8f66186f11b7b242b4` |
| [Lazarus](https://gitlab.com/freepascal.org/lazarus/lazarus) | `9d15c73c91a1545be50bee02b27bd3b43f9d90e8` (`lazarus_4_0`) |
| [Free Pascal source](https://gitlab.com/freepascal.org/fpc/source) | `0d122c49534b480be9284c21bd60b53d99904346` (`release_3_2_2`) |

The installed test toolchain lives in `$HOME/.local/share/zed-delphi/toolchains/pasls/`. Its `installation.json` records source revisions, selected source directories, compiler and build command. The launcher `$HOME/.local/bin/pasls` supplies the matching source paths unless `PP`, `FPCDIR` or `LAZARUSDIR` are explicitly set by the caller. The sources are retained because CodeTools needs them at runtime. Build intermediates were removed; the installation occupies about 92 MB.

Lazarus was checked out sparsely: `components/codetools`, `components/lazutils`, `components/jcf2`. Free Pascal sources include `rtl`, `packages/fcl-base`, `packages/fcl-json`. Projects that depend on other source packages need those packages added to the source checkout or their own CodeTools search paths. No Lazarus GUI installation was needed.

To rebuild with these checkouts, from the installation's `source` directory:

```sh
LAZARUSDIR="$HOME/.local/share/zed-delphi/toolchains/pasls/lazarus" \
FPC=/opt/homebrew/bin/fpc bash src/build_fpc.sh aarch64-darwin
```

The upstream build writes `dist/aarch64-darwin/pasls`. Other targets require the corresponding compiler; change the explicit target instead of assuming this macOS binary works on Windows or Linux.

Choose `pasls` for an FPC project. Replace the example executable path with the absolute path to the installed launcher:

The built-in adapter enables syntax checking, published diagnostics and Delphi mode (`-Mdelphi`) by default. Explicit project initialization options can override these settings; an ObjFPC project can use `fpcOptions: ["-Mobjfpc"]`. The example spells out the defaults for reproducibility with external clients as well. The smoke fixture deliberately has no `{$mode}` directive, so its mode comes from initialization options.

```json
{
  "languages": { "Delphi": { "language_servers": ["pasls"] } },
  "lsp": {
    "pasls": {
      "binary": { "path": "/absolute/path/to/.local/bin/pasls" },
      "initialization_options": {
        "checkSyntax": true,
        "publishDiagnostics": true,
        "fpcOptions": ["-Mdelphi"]
      }
    }
  }
}
```

Run the real-server smoke test from the fork root:

```sh
python3 script/delphi/tests/smoke_pasls.py \
  --pasls "$HOME/.local/bin/pasls" \
  --compiler /opt/homebrew/bin/fpc \
  --fpc-source "$HOME/.local/share/zed-delphi/toolchains/pasls/fpc-source" \
  --lazarus-source "$HOME/.local/share/zed-delphi/toolchains/pasls/lazarus"
```

The test uses a temporary project and bounded waits. A successful result includes `initialize`, `definition`, `completion`, `diagnostics_and_recovery` as `passed`, and `shutdown_exit_code: 0`.

This pasls revision expects `clientInfo` during initialization and rejects an explicit JSON `null` for shutdown parameters. Zed supplies client information in normal app startup and omits unit-valued parameters, so no adapter workaround was needed. These observations are protocol checks, not evidence of Embarcadero DelphiLSP compatibility or Windows execution.
