#!/usr/bin/env python3
"""Build and smoke-test a relocatable Linux pasls package with matching sources."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tarfile


ROOT = Path(__file__).resolve().parents[3]
SOURCES = {
    'source': ('https://github.com/genericptr/pascal-language-server.git',
               '818f6330b721ed5c89d1fd8f66186f11b7b242b4', []),
    'lazarus': ('https://gitlab.com/freepascal.org/lazarus/lazarus.git',
                '9d15c73c91a1545be50bee02b27bd3b43f9d90e8',
                ['components/codetools', 'components/lazutils', 'components/jcf2']),
    'fpc-source': ('https://gitlab.com/freepascal.org/fpc/source.git',
                   '0d122c49534b480be9284c21bd60b53d99904346',
                   ['rtl', 'packages/fcl-base', 'packages/fcl-json']),
}
LAUNCHER = '''#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
: "${PP:=$(command -v fpc)}"
: "${FPCDIR:=$root/fpc-source}"
: "${LAZARUSDIR:=$root/lazarus}"
export PP FPCDIR LAZARUSDIR
exec "$root/bin/pasls-server" "$@"
'''


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def copy_tracked(source, destination):
    """Retain checked-out source and notices, excluding Git state and compiler outputs."""
    names = subprocess.check_output(['git', '-C', str(source), 'ls-files', '-z']).decode().split('\0')
    for name in names:
        path = source / name
        if not name or not path.is_file():
            continue
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target, follow_symlinks=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True, help='New build directory without spaces')
    parser.add_argument('--output-dir', type=Path, required=True, help='New artifact directory')
    parser.add_argument('--compiler', default='fpc')
    options = parser.parse_args()
    architecture = platform.machine()
    if platform.system() != 'Linux' or architecture not in ('x86_64', 'aarch64'):
        parser.error('Native Linux x86_64 or aarch64 is required')
    compiler = shutil.which(options.compiler)
    if not compiler:
        parser.error('Install Free Pascal 3.2.2, fp-units-base and fp-units-fcl')
    version = subprocess.check_output([compiler, '-iV'], text=True).strip()
    target = '-'.join(subprocess.check_output([compiler, option], text=True).strip()
                      for option in ('-iTP', '-iTO'))
    if version != '3.2.2' or target != f'{architecture}-linux':
        parser.error(f'Expected native FPC 3.2.2, found {version} for {target}')
    work, output = options.work_dir.resolve(), options.output_dir.resolve()
    if any(character.isspace() for character in str(work)):
        parser.error('Upstream build options require a work directory without whitespace')
    if work.exists() or output.exists():
        parser.error('Work and output directories must not exist; previous results are preserved')
    if work == output or work.is_relative_to(output) or output.is_relative_to(work):
        parser.error('Work and output must be separate directories')
    work.mkdir(parents=True)
    output.mkdir(parents=True)
    with (output / 'BUILD.log').open('w', buffering=1) as log:
        def run(arguments, **kwargs):
            log.write('\n$ ' + shlex.join(map(str, arguments)) + '\n')
            with subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, errors='replace', **kwargs) as process:
                for line in process.stdout:
                    print(line, end='', flush=True)
                    log.write(line)
                if process.wait():
                    raise subprocess.CalledProcessError(process.returncode, arguments)

        for name, (repository, revision, paths) in SOURCES.items():
            checkout = work / name
            run(['git', 'init', str(checkout)])
            run(['git', '-C', str(checkout), 'remote', 'add', 'origin', repository])
            if paths:
                run(['git', '-C', str(checkout), 'sparse-checkout', 'init', '--cone'])
                run(['git', '-C', str(checkout), 'sparse-checkout', 'set', *paths])
            run(['git', '-C', str(checkout), 'fetch', '--depth=1', '--filter=blob:none', 'origin', revision])
            run(['git', '-C', str(checkout), 'checkout', '--detach', 'FETCH_HEAD'])
            actual = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
            if actual != revision:
                raise RuntimeError(f'{name}: expected {revision}, got {actual}')

        environment = dict(os.environ, FPC=compiler, LAZARUSDIR=str(work / 'lazarus'))
        environment.pop('FPCUPDELUXE', None)
        environment.pop('FPC_CROSS_UNITS', None)
        run(['bash', 'src/build_fpc.sh', target], cwd=work / 'source', env=environment)
        binary = work / 'source/dist' / target / 'pasls'
        if not binary.is_file():
            raise RuntimeError('Upstream build did not produce pasls')

        # Exercise the shipped layout in a path with spaces, not the build checkout.
        package = work / 'relocated pasls'
        (package / 'bin').mkdir(parents=True)
        for name in SOURCES:
            copy_tracked(work / name, package / name)
        shutil.copy2(binary, package / 'bin/pasls-server')
        (package / 'bin/pasls').write_text(LAUNCHER)
        (package / 'bin/pasls').chmod(0o755)
        probe = work / 'pasls-defaults'
        probe.write_text('#!/bin/sh\nunset PP FPCDIR LAZARUSDIR\nexec '
                         + shlex.quote(str(package / 'bin/pasls')) + ' "$@"\n')
        probe.chmod(0o755)
        # The wrapper clears smoke-test overrides so the real relocatable defaults are tested.
        environment = dict(os.environ, PATH=str(Path(compiler).parent) + os.pathsep + os.environ['PATH'])
        run([sys.executable, str(ROOT / 'script/delphi/tests/smoke_pasls.py'),
             '--pasls', str(probe), '--compiler', compiler,
             '--fpc-source', str(package / 'fpc-source'),
             '--lazarus-source', str(package / 'lazarus')], env=environment)
        (package / 'README.txt').write_text(
            'pasls with pinned runtime sources for Linux ' + architecture + '.\n'
            'Extract anywhere, then configure lsp.pasls.binary.path to bin/pasls.\n'
            'Install matching native Free Pascal 3.2.2 (fpc, base and FCL units) separately.\n'
            'PP, FPCDIR and LAZARUSDIR can override launcher defaults.\n'
            'Only rtl, fcl-base and fcl-json FPC sources are included; other packages need extra sources.\n'
            'Licenses and corresponding sources remain in source/, lazarus/ and fpc-source/.\n'
            'Protocol smoke passed after relocation with spaces. Zed GUI/Astra acceptance is separate.\n')
        shutil.copy2(__file__, package / 'build_pasls.py')
        metadata = {
            'built_at_utc': datetime.now(timezone.utc).isoformat(),
            'target': target, 'compiler': compiler, 'compiler_version': version,
            'os_release': Path('/etc/os-release').read_text(),
            'sources': {name: {'repository': repository, 'revision': revision, 'sparse_paths': paths}
                        for name, (repository, revision, paths) in SOURCES.items()},
            'build_command': ['bash', 'src/build_fpc.sh', target],
            'source_patches': [], 'compiler_bundled': False,
            'smoke': 'initialize, definition, completion, diagnostics/recovery, shutdown: passed',
            'relocated_default_launcher_with_spaces': 'passed',
            'astra_acceptance': 'not tested', 'zed_gui_acceptance': 'not tested',
            'binary_sha256': digest(package / 'bin/pasls-server'),
        }
        (package / 'provenance.json').write_text(json.dumps(metadata, indent=2) + '\n')
        shutil.copy2(package / 'provenance.json', output / 'provenance.json')
        files = sorted(path for path in package.rglob('*') if path.is_file())
        (package / 'FILES.sha256').write_text(''.join(f'{digest(path)}  {path.relative_to(package)}\n'
                                                    for path in files))
        with tarfile.open(output / f'pasls-linux-{architecture}.tar.gz', 'w:gz') as archive:
            archive.add(package, arcname='pasls')
    files = sorted(path for path in output.iterdir() if path.is_file())
    (output / 'SHA256SUMS').write_text(''.join(f'{digest(path)}  {path.name}\n' for path in files))
    print(f'PASS: native pasls build and relocated real LSP smoke; artifacts: {output}')


if __name__ == '__main__':
    main()
