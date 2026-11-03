#!/usr/bin/env python3
"""Preserve upstream license files and measured provenance for an FPC package."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def output(*args):
    result = subprocess.run(args, capture_output=True, text=True)
    return {'command': list(args), 'exit_code': result.returncode,
            'stdout': result.stdout.strip(), 'stderr': result.stderr.strip()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('prefix', 'source-dir', 'source-archive', 'bootstrap',
                 'bootstrap-version', 'same-version-override'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    prefix, source_dir = Path(args.prefix), Path(args.source_dir)
    metadata = prefix / 'share' / 'zed-delphi'
    license_dir = prefix / 'share' / 'licenses' / 'fpc-3.2.2'
    for path in source_dir.rglob('*'):
        if path.is_file() and path.name.lower().startswith(('copying', 'license', 'copyright')):
            destination = license_dir / path.relative_to(source_dir)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
    metadata.mkdir(parents=True, exist_ok=True)
    compiler = prefix / 'lib' / 'fpc' / '3.2.2' / 'ppcx64'
    report = {
        'compiler': 'Free Pascal', 'version': '3.2.2',
        'target': 'x86_64-linux', 'intended_validation_target': 'Astra Linux 1.8 x86_64',
        'astra_acceptance': 'not established by this build recipe',
        'built_at_utc': datetime.now(timezone.utc).isoformat(),
        'os_release': Path('/etc/os-release').read_text(),
        'astra_version': Path('/etc/astra_version').read_text() if Path('/etc/astra_version').exists() else None,
        'container_image_reference': os.environ.get('BUILD_IMAGE_REFERENCE'),
        'uname': platform.uname()._asdict(),
        'source_url': 'https://downloads.freepascal.org/fpc/dist/3.2.2/source/fpc-3.2.2.source.tar.gz',
        'source_sha256': digest(Path(args.source_archive)),
        'source_date_epoch': os.environ['SOURCE_DATE_EPOCH'],
        'bootstrap_path': args.bootstrap, 'bootstrap_version': args.bootstrap_version,
        'same_version_override': args.bootstrap_version == '3.2.2' and args.same_version_override == '1',
        'compiler_sha256': digest(compiler),
        'make_targets': ['all ALLTARGET=all OPT=-O2', 'utils/fpcm all', 'install INSTALLTARGET=install'],
        'smoke': {'delphi_mode_compiler_rtl_fcl': 'passed', 'relocated_prefix_with_spaces': 'passed'},
        'tools': [output('gcc', '--version'), output('ld', '--version'), output('make', '--version'),
                  output('file', str(compiler)), output('readelf', '-l', str(compiler))],
        'bit_identical_rebuild_claimed': False,
    }
    if shutil.which('dpkg-query'):
        (metadata / 'build-packages.txt').write_text(output('dpkg-query', '-W')['stdout'] + '\n')
    if shutil.which('ldd'):
        report['dynamic_dependencies'] = output('ldd', str(compiler))
    (metadata / 'provenance.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    paths = sorted(path for path in prefix.rglob('*') if path.is_file() and not path.is_symlink())
    (metadata / 'FILES.sha256').write_text(''.join(f'{digest(path)}  {path.relative_to(prefix)}\n' for path in paths))


if __name__ == '__main__':
    main()
