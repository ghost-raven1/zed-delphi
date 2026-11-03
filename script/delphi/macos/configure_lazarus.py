#!/usr/bin/env python3
"""Create isolated Lazarus launchers for an installed macOS FPC toolchain."""

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--fpc', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--classic-linker-dir', type=Path,
                        help='Xcode bin directory containing ld and ld-classic (FPC 3.2.2 Cocoa workaround)')
    options = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('This configuration is for macOS only')
    source = options.source_dir.resolve(strict=True)
    compiler = options.fpc.resolve(strict=True)
    lazbuild = source / 'lazbuild'
    if not lazbuild.is_file():
        parser.error('Build Lazarus lazbuild before configuring it')
    flags = []
    if options.classic_linker_dir:
        linker = options.classic_linker_dir.resolve(strict=True)
        if not all((linker / name).is_file() for name in ('ld', 'ld-classic')):
            parser.error('The selected directory must contain ld and ld-classic')
        flags = ['-FD' + str(linker), '-k-ld_classic']
    output = options.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    fpc_launcher = output / 'fpc-cocoa'
    fpc_launcher.write_text('#!/bin/sh\nexec ' + shlex.join([str(compiler), *flags]) + ' "$@"\n')
    fpc_launcher.chmod(0o755)
    command = [str(lazbuild), '--lazarusdir=' + str(source),
               '--primary-config-path=' + str(output / 'config'), '--compiler=' + str(fpc_launcher)]
    launcher = output / 'lazbuild'
    launcher.write_text('#!/bin/sh\nexec ' + shlex.join(command) + ' "$@"\n')
    launcher.chmod(0o755)
    versions = {
        'lazarus_source': str(source), 'compiler': str(compiler), 'compiler_flags': flags,
        'fpc_version': subprocess.check_output([str(compiler), '-iV'], text=True).strip(),
        'lazbuild_version': subprocess.check_output([str(launcher), '--version'], text=True).strip(),
    }
    (output / 'toolchain.json').write_text(json.dumps(versions, indent=2) + '\n')
    print(launcher)


if __name__ == '__main__':
    main()
