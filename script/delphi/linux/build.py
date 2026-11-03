#!/usr/bin/env python3
"""Build this checkout with the existing Linux bundler and verify its package."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import tarfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
GIB = 1024**3


def available_memory():
    """Respect container memory ceilings as well as the host's available RAM."""
    entries = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    available = int(entries['MemAvailable'].split()[0]) * 1024
    for limit_path, usage_path, stat_key in [
        ('/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory.current', 'inactive_file'),
        ('/sys/fs/cgroup/memory/memory.limit_in_bytes', '/sys/fs/cgroup/memory/memory.usage_in_bytes', 'total_inactive_file'),
    ]:
        try:
            limit = Path(limit_path).read_text().strip()
            if limit == 'max':
                continue
            limit = int(limit)
            usage = int(Path(usage_path).read_text())
        except FileNotFoundError:
            continue
        try:
            statistics = dict(line.split() for line in Path(limit_path).with_name('memory.stat').read_text().splitlines())
            reclaimable = max(0, int(statistics.get(stat_key, '0')))
        except FileNotFoundError:
            reclaimable = 0
        # Inactive file cache is reclaimable; counting it as live memory blocks resumed builds.
        available = min(available, limit, max(0, limit - usage + reclaimable))
    return available


def existing_parent(path):
    while not path.exists():
        path = path.parent
    return path


def preflight(target, output, disk_gib, memory_gib, with_remote=False):
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'aarch64'):
        raise RuntimeError('Run on Linux x86_64 or aarch64; Astra x86_64 requires an x86_64 host/container')
    if any(character.isspace() for character in str(target)):
        raise RuntimeError('Upstream bundle-linux requires CARGO_TARGET_DIR without whitespace')
    if 'RUSTFLAGS' in os.environ or 'CARGO_ENCODED_RUSTFLAGS' in os.environ:
        raise RuntimeError('Unset RUSTFLAGS and CARGO_ENCODED_RUSTFLAGS as required by bundle-linux')
    for path in (target, output):
        free = shutil.disk_usage(existing_parent(path)).free / GIB
        if free < disk_gib:
            raise RuntimeError(f'{path}: {free:.1f} GiB free; require {disk_gib:g} GiB')
    memory = available_memory() / GIB
    if memory < memory_gib:
        raise RuntimeError(f'{memory:.1f} GiB RAM available within host/container limits; require {memory_gib:g} GiB')
    required = ['bash', 'git', 'cargo', 'rustc', 'clang', 'cmake', 'pkg-config', 'make',
                'llvm-objcopy', 'ldd', 'tar', 'gzip', 'envsubst', 'jq', 'curl']
    if with_remote and not os.environ.get('REMOTE_SERVER_TARGET'):
        required.append('musl-gcc')
    missing = [tool for tool in required if not shutil.which(tool)]
    if missing:
        raise RuntimeError('Missing tools: ' + ', '.join(missing) + '; inspect script/linux')


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def check_dynamic_libraries(binary, log):
    result = subprocess.run(['ldd', str(binary)], capture_output=True, text=True)
    text = result.stdout + result.stderr
    log.write(f'\n$ ldd {binary}\n{text}')
    log.flush()
    if result.returncode or 'not found' in text:
        raise RuntimeError(f'Runtime libraries unresolved for {binary}; see BUILD.log')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True, help='New directory for artifacts and logs')
    parser.add_argument('--preflight-only', action='store_true', help='No installation, rustup, Cargo or build commands')
    parser.add_argument('--min-disk-gib', '--min-free-gib', type=float, default=30)
    parser.add_argument('--with-remote-server', action='store_true', help='Use the full upstream bundle-linux including remote-server')
    parser.add_argument('--min-memory-gib', type=float, default=8)
    args = parser.parse_args()
    if any(not math.isfinite(value) or value <= 0 for value in (args.min_disk_gib, args.min_memory_gib)):
        parser.error('Resource thresholds must be positive')
    target = Path(os.environ.get('CARGO_TARGET_DIR', str(ROOT / 'target/linux-delphi'))).resolve()
    output = args.output_dir.resolve()
    preflight(target, output, args.min_disk_gib, args.min_memory_gib, args.with_remote_server)
    print('Preflight passed. This is not a compilation or Linux UI acceptance result.')
    if args.preflight_only:
        return
    if output.exists():
        raise RuntimeError('Output directory already exists; choose a new directory to preserve earlier results')
    output.mkdir(parents=True)
    target.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment['CARGO_TARGET_DIR'] = str(target)
    environment.setdefault('CARGO_BUILD_JOBS', '2')
    environment.pop('ALLOW_MISSING_LICENSES', None)
    metadata = {
        'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'os_release': Path('/etc/os-release').read_text(),
        'architecture': platform.machine(), 'target_directory': str(target),
        'resource_thresholds_gib': {'disk': args.min_disk_gib, 'memory': args.min_memory_gib},
        'command': ['bash', 'script/bundle-linux', '--skip-sentry'] if args.with_remote_server else ['bash', 'script/delphi/linux/bundle-editor.sh'],
        'ui_acceptance': 'not performed', 'astra_acceptance': 'not established by this build',
        'bit_identical_rebuild_claimed': False,
        'environment': {key: environment.get(key) for key in ('CARGO_BUILD_JOBS', 'CC', 'CXX', 'LLD', 'REMOTE_SERVER_TARGET', 'SOURCE_DATE_EPOCH', 'CARGO_PROFILE_RELEASE_DEBUG', 'CARGO_PROFILE_RELEASE_LTO', 'CARGO_PROFILE_RELEASE_CODEGEN_UNITS', 'CARGO_PROFILE_RELEASE_OPT_LEVEL')},
        'cargo_lock_sha256': digest(ROOT / 'Cargo.lock'),
    }
    for arguments, filename in [(['git', 'rev-parse', 'HEAD'], 'commit.txt'),
                                (['git', 'status', '--short'], 'git-status.txt'),
                                (['git', 'diff', '--binary', 'HEAD'], 'source.patch'),
                                (['rustc', '--version', '--verbose'], 'rustc.txt'),
                                (['cargo', '--version'], 'cargo.txt')]:
        result = subprocess.run(arguments, cwd=ROOT, env=environment, check=True, capture_output=True)
        (output / filename).write_bytes(result.stdout)
    source_files = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT, check=True, capture_output=True).stdout
    with tarfile.open(output / 'source-snapshot.tar.gz', 'w:gz') as source_archive:
        for name in sorted(set(source_files.decode().split('\0'))):
            if name and (ROOT / name).exists() and not (ROOT / name).resolve().is_relative_to(output):
                source_archive.add(ROOT / name, arcname=name, recursive=False)
    (output / 'provenance.json').write_text(json.dumps(metadata, indent=2) + '\n')
    with (output / 'BUILD.log').open('w', buffering=1) as log:
        with subprocess.Popen(metadata['command'], cwd=ROOT, env=environment, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, errors='replace') as process:
            for line in process.stdout:
                print(line, end='')
                log.write(line)
            if process.wait():
                raise RuntimeError('bundle-linux failed; see preserved BUILD.log')
        if digest(ROOT / 'Cargo.lock') != metadata['cargo_lock_sha256']:
            raise RuntimeError('Cargo.lock changed during build; review the change before packaging')
        archive = target / 'release' / f'zed-linux-{platform.machine()}.tar.gz'
        with tempfile.TemporaryDirectory(prefix='zed-delphi-runtime-', dir=target) as temporary:
            subprocess.run(['tar', '-xzf', str(archive), '-C', temporary], check=True)
            applications = list(Path(temporary).glob('zed*.app'))
            if len(applications) != 1:
                raise RuntimeError('Expected exactly one Zed app in bundle')
            for relative in ('bin/zed', 'libexec/zed-editor'):
                check_dynamic_libraries(applications[0] / relative, log)
        shutil.copy2(archive, output / archive.name)
        if args.with_remote_server:
            remote = target / f'zed-remote-server-linux-{platform.machine()}.gz'
            shutil.copy2(remote, output / remote.name)
    metadata.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), bundled_elf_ldd='passed')
    (output / 'provenance.json').write_text(json.dumps(metadata, indent=2) + '\n')
    files = sorted(path for path in output.iterdir() if path.is_file())
    (output / 'SHA256SUMS').write_text(''.join(f'{digest(path)}  {path.name}\n' for path in files))
    print(f'Bundle and loader checks passed: {output}. Launch/project/debug acceptance remains separate.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f'Zed Delphi Linux build: {error}', file=sys.stderr)
        sys.exit(1)
