# Multi-unit Delphi acceptance project

Open this directory itself as the Zed worktree. Put `fpc` on the editor's PATH, then run **FPC: build multi-unit (Debug)**. The program prints `42` and exits with status 0. Debug profiles use CodeLLDB and invoke the same build task before launching.

For the desktop acceptance check, open `MultiUnit.dpr`, navigate to `TCalculator.Calculate` in `Arithmetic.pas`, and place a breakpoint on `Result := LeftValue + RightValue` inside `AddValues`. Launch the debugger; verify the stack spans the program and unit, `LeftValue = 20`, `RightValue = 22`, stepping computes `Result = 42`, and continuation exits normally. The integer arguments are suitable for inspecting even where LLDB's Pascal object/property display is limited.

The sources deliberately use classic Delphi `uses ... in 'Arithmetic.pas'`, a class/property and a separate function. FPC is selected with `-Mdelphi`; no source mode directive or external framework is needed. Command-line compilation alone does not establish Zed UI/debugger acceptance.
