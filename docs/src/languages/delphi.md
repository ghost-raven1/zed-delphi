---
title: Delphi / Object Pascal
description: Built-in Object Pascal editing, compiler tasks and Delphi debugging.
---

# Delphi / Object Pascal

This fork includes a native Tree-sitter grammar for `.pas`, `.dpr`, `.dpk` and
`.lpr` files, with highlighting, an outline, brackets and indentation. Compiler,
language-server and debugger executables are installed separately.

The vendored grammar includes project `uses ... in 'file.pas'` declarations and
package `requires`/`contains` declarations. `.dfm` and `.fmx` form designers are not
implemented. VCL and FMX projects can be built by their installed Embarcadero
toolchain; this does not provide a visual form designer.

## Platform coverage {#platform-coverage}

The editor remains a native Rust/GPUI application. Editor host, compiler host and
application target are separate choices:

| Editor host | Local compilation              | Embarcadero integration               | Debugging                                                     |
| ----------- | ------------------------------ | ------------------------------------- | ------------------------------------------------------------- |
| Windows x64 | FPC, Lazarus, installed Delphi | Local DelphiLSP and MSBuild           | FPC through LLDB/GDB; Delphi through MCA DAP                  |
| macOS ARM64 | FPC, Lazarus                   | Windows SSH build and language server | Local FPC through LLDB; Delphi through Windows DAP bridge     |
| macOS x64   | FPC, Lazarus                   | Windows SSH build and language server | Same configured adapters as ARM64                             |
| Linux x64   | FPC, Lazarus                   | Windows SSH build and language server | Local FPC through LLDB/GDB; Delphi through Windows DAP bridge |

This table describes implemented integration paths, not completed acceptance on
every platform. On Ubuntu 24.04 ARM64, the packaged native editor passed FPC
multi-unit build/run and CodeLLDB breakpoint, stack, integer locals, stepping and
exit checks, including a project path with spaces. Native pasls navigation and
protocol diagnostics/completion checks passed. Standalone FPC/DAP also passed on
macOS ARM64. See [fork verification](../../../FORK.md) for current platform results.

The manually dispatched fork workflows build native applications and retain test
logs and artifacts. Linux x86_64 uses the separate `Delphi Linux x86_64 bundle`
workflow. These results do not imply Astra ABI compatibility, signed installers,
or licensed Embarcadero and remote Windows acceptance. Windows ARM64 is not
covered by the fork's CI matrix.

Include files are ambiguous across languages. To treat your project's `.inc`
files as Delphi, add this to your project settings:

```json [settings]
{
  "file_types": { "Delphi": ["**/*.inc"] }
}
```

## Language servers {#language-servers}

Select one server in the Settings Editor, or configure it explicitly. Neither
server is automatically downloaded or enabled.

For Free Pascal, install `pasls` and configure its CodeTools search paths:

```json [settings]
{
  "languages": { "Delphi": { "language_servers": ["pasls"] } },
  "lsp": {
    "pasls": { "binary": { "path": "/absolute/path/to/pasls" } }
  }
}
```

For Embarcadero, use the DelphiLSP from your licensed installation on Windows:

```json [settings]
{
  "languages": { "Delphi": { "language_servers": ["delphilsp"] } },
  "lsp": {
    "delphilsp": {
      "binary": { "path": "C:\\Delphi\\bin\\DelphiLSP.exe" },
      "settings": { "settingsFile": "file:///C:/Projects/App/.delphilsp.json" }
    }
  }
}
```

Follow the [Embarcadero external-editor setup](https://docwiki.embarcadero.com/RADStudio/Alexandria/en/Using_DelphiLSP_Code_Insight_with_Other_Editors)
for the project configuration. `pasls` uses Free Pascal semantics; it does not
replace DelphiLSP for Embarcadero-specific APIs.

For a Mac/Linux editor with a Windows language server, configure the included
stdio bridge instead of the Windows executable:

```json [settings]
{
  "languages": { "Delphi": { "language_servers": ["delphilsp"] } },
  "lsp": {
    "delphilsp": {
      "binary": {
        "path": "/absolute/path/to/python3",
        "arguments": [
          "/path/to/zed/script/delphi/lsp_remote.py",
          "--host",
          "delphi-builder",
          "--server",
          "C:\\Delphi\\bin\\DelphiLSP.exe",
          "--local-root",
          "/projects/App",
          "--remote-root",
          "C:\\Projects\\App"
        ]
      },
      "settings": { "settingsFile": "file:///projects/App/.delphilsp.json" }
    }
  }
}
```

Use a noninteractive OpenSSH host alias. Synchronize source files yourself and
generate `.delphilsp.json` for the Windows compiler paths. The bridge maps rooted
file URIs, paths and workspace-edit keys in both directions. Framing and mapping
have automated tests; completion/navigation against an actual Windows DelphiLSP
has not been validated. Mac/Linux LSP transport does not install or license
Delphi on the build host.

## Build and run {#build-and-run}

The task picker includes Free Pascal Debug and Release compilation for the current
file. Open the program entry point before using it. A unit can compile without
producing an executable. Debug uses Delphi mode, DWARF symbols and no optimization.
See the [Free Pascal compiler options](https://www.freepascal.org/docs-html/3.0.2/user/userap1.html).

For a complete project, use `script/delphi/build.py` from this fork. It requires
Python 3.9 or newer and invokes installed tools; it does not install compilers.
Paths supplied to this helper are process arguments, not shell commands. It
returns compiler failures unchanged and runs a program only after a successful
build. Relative output and program paths are resolved beside the project file.

```sh
python3 script/delphi/build.py --tool fpc --project /projects/App/App.dpr --run
python3 script/delphi/build.py --tool lazarus --project /projects/App/App.lpi --config Debug --run --program bin/App
```

Lazarus build modes must already exist in the `.lpi`. The helper uses `lazbuild`;
it does not replace the Lazarus form designer.

On Windows, select your Delphi installation explicitly:

```powershell
python script/delphi/build.py --tool delphi --project "C:\Projects\App\App.dproj" --rsvars "C:\Program Files (x86)\Embarcadero\Studio\23.0\bin\rsvars.bat" --config Debug --platform Win64 --run --program "Win64\Debug\App.exe"
```

You can omit `--rsvars` when launching from a configured RAD Studio command prompt.
The helper uses [MSBuild project configuration and platform properties](https://docwiki.embarcadero.com/RADStudio/Sydney/en/Building_a_Project_Using_an_MSBuild_Command).
Use the platform name available in your installed compiler and project. Legacy
`.dpr`/`.dpk` builds without `.dproj` need explicit compiler tasks. Mobile deployment,
code signing and platform SDK setup remain responsibilities of the toolchain.

To expose a helper invocation in Zed, create `.zed/tasks.json`:

```json [tasks]
[
  {
    "label": "Delphi: build project",
    "command": "python3",
    "args": [
      "\"/path/to/zed/script/delphi/build.py\"",
      "--tool",
      "fpc",
      "--project",
      "\"$ZED_WORKTREE_ROOT/App.dpr\""
    ],
    "save": "all"
  }
]
```

Use `python` on Windows if that is the installed command. Set `--compiler` to
select a specific compiler executable. Repeat `--arg=value` to pass arguments to
the program when using `--run`.

### Cross-compile an application {#cross-compilation}

For Free Pascal, pass its target identifiers explicitly:

```sh
python3 script/delphi/build.py --tool fpc --project /projects/App/App.dpr --target-os linux --target-cpu x86_64 --output /projects/App/build/linux-x64/App
```

The helper forwards these as `-Tlinux` and `-Px86_64`. Install the matching cross
compiler, RTL units, linker and target libraries first; flags alone do not install
a cross toolchain or port platform-specific code. Create the output folder before
building. `--target-os` and `--target-cpu` apply only to FPC. `--run` rejects an
explicit target OS or CPU different from the build host, including combinations
that would need an emulator. Cross-target compilation has command-construction
tests but has not been run against an installed cross toolchain here.

For Embarcadero, `--platform` selects the target defined in your `.dproj`. Available
targets, SDK setup, deployment and framework compatibility depend on the selected
licensed installation. `--run` is accepted only for `Win32` or `Win64` on a
Windows host. Build Linux, macOS, Android and iOS targets without `--run`, then
deploy and execute them on their target platform with the appropriate tools.
The helper does not perform mobile deployment. Lazarus cross targets are
configured in the selected project build mode.

### Build on Windows from macOS or Linux {#remote-build}

Configure a Windows OpenSSH host alias and key authentication. Install Python and
Delphi on that host and copy `build.py` there. Keep an existing checkout on each
machine at the same source revision. This helper does not synchronize or delete
files.

```sh
python3 script/delphi/build.py --tool delphi --project 'C:\Projects\App\App.dproj' --rsvars 'C:\Delphi\bin\rsvars.bat' --ssh-host delphi-builder --remote-helper 'C:\Tools\build.py' --config Debug --platform Win64
```

All build paths in this mode refer to the Windows host. `--remote-python` selects
its Python executable. SSH runs without a terminal and without interactive
password prompts. The remote compiler's output and exit status return to Zed.
Stopping SSH does not guarantee that Windows has stopped every compiler child;
check the host before restarting an interrupted build. Remote GUI programs run
in the SSH session, not necessarily on the interactive desktop.

## Debugging {#debugging}

### Free Pascal and Lazarus

Compile with debug symbols and disabled optimization. Use the built-in `CodeLLDB`
adapter (or GDB with DAP support on an appropriate host). Open
`script/delphi/examples` as a project for a runnable sample with build and debug
profiles. See [debugger settings](../debugger.md#customizing-debug-adapters) to
select an existing `lldb-dap` binary, with `args: []`, instead of downloading
CodeLLDB.

Pascal expression evaluation and complex type inspection depend on the debugger.
Apple LLDB reports that it lacks a Pascal language plugin; basic source
breakpoints, stepping, stack frames and integer locals were tested on the sample.
This does not establish complete Pascal debugger compatibility.

### Embarcadero Delphi on Windows

The built-in `Delphi` adapter launches the separately installed
[MCA Delphi DAP debugger](https://github.com/csm101/delphi-visual-studio-code-debugger/tree/599d4bf04b14daee91b7606c18b0b1df2098f5b8).
That project is MIT licensed; its executable is not bundled or downloaded. The
integration uses its stdio DAP contract and supports explicit launch/attach
profiles. Configure the executable in your user settings:

```json [settings]
{
  "dap": {
    "Delphi": {
      "binary": "C:\\Tools\\VisualStudioCodeDelphiDebugger.exe",
      "args": []
    }
  }
}
```

Create `.zed/debug.json` in the project:

```json [debug]
[
  {
    "label": "Delphi Win64",
    "adapter": "Delphi",
    "request": "launch",
    "program": "$ZED_WORKTREE_ROOT/Win64/Debug/App.exe",
    "sourceRoot": "$ZED_WORKTREE_ROOT",
    "stopAtEntry": true,
    "build": "Delphi: build project"
  }
]
```

Use a Windows MSBuild task for the referenced build label. For attach, set
`request: "attach"` and an integer `processId` or `processName`. Preserve `.map`
and `.rsm` beside your executable and enable debug information, local symbols and
remote symbols while disabling optimization. Packages need their own symbols.
The adapter's Win32/Win64 behavior depends on the installed version. It has not
been executed on Windows as part of this fork's local validation.

### Delphi debugging through a Windows SSH host

`script/delphi/dap_remote.py` forwards stdio DAP and maps one local source root to a
Windows source root. Install Python locally and the MCA adapter on Windows. Set
`dap.Delphi.binary` to your local Python and its `args` to:

```json
[
  "/path/to/zed/script/delphi/dap_remote.py",
  "--host",
  "delphi-builder",
  "--adapter",
  "C:\\Tools\\VisualStudioCodeDelphiDebugger.exe",
  "--local-root",
  "/projects/App",
  "--remote-root",
  "C:\\Projects\\App"
]
```

Keep both source trees synchronized. The debug profile can use local paths under
`--local-root`; the proxy translates source and launch paths in both directions.
It does not translate expressions or arbitrary string values. Sources outside
that root and case mismatches on a case-sensitive local filesystem require
matching local files. SSH authentication must be noninteractive. The proxy's
framing, Unicode, quoting and mapping have automated tests; Windows OpenSSH,
remote process cleanup and a complete remote breakpoint session remain untested.
