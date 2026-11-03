#!/usr/bin/env python3
"""Package the freshly built LCL executable for Cocoa launch and debugging."""

import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

BUNDLE_ID = 'dev.zed.delphi.lcldemo'


def package(project):
    if sys.platform != 'darwin':
        raise ValueError('Этот упаковщик предназначен только для macOS.')
    binary = project / 'LclDemo'
    output = project / 'LclDemo.app'
    previous = project / '.LclDemo.previous.app'
    if previous.exists() or previous.is_symlink():
        raise ValueError(f'Сохранена предыдущая сборка: {previous}. Восстановите или переместите её перед повтором.')
    if not binary.is_file() or binary.is_symlink():
        raise ValueError('Сначала соберите LclDemo.lpi для macOS.')
    description = subprocess.check_output(['/usr/bin/file', '-b', str(binary)], text=True)
    if 'Mach-O' not in description:
        raise ValueError('LclDemo не является исполняемым файлом macOS.')
    if output.is_symlink():
        raise ValueError('LclDemo.app не должен быть символической ссылкой.')
    if output.exists():
        with (output / 'Contents/Info.plist').open('rb') as stream:
            existing = plistlib.load(stream)
        if existing.get('CFBundleIdentifier') != BUNDLE_ID:
            raise ValueError('Существующий LclDemo.app принадлежит другому приложению.')

    # Prepare and verify the replacement before moving an earlier working bundle.
    with tempfile.TemporaryDirectory(prefix='.lcl-macos-', dir=project) as temporary:
        directory = Path(temporary)
        app = directory / 'LclDemo.app'
        contents = app / 'Contents'
        executable = contents / 'MacOS/LclDemo'
        executable.parent.mkdir(parents=True)
        resources = contents / 'Resources'
        resources.mkdir()
        shutil.copy2(binary, executable)
        executable.chmod(0o755)
        info = {
            'CFBundleIdentifier': BUNDLE_ID, 'CFBundleName': 'LclDemo',
            'CFBundleDisplayName': 'Демо Lazarus LCL', 'CFBundleExecutable': 'LclDemo',
            'CFBundlePackageType': 'APPL', 'CFBundleVersion': '1',
            'CFBundleShortVersionString': '1.0', 'NSHighResolutionCapable': True,
        }
        (contents / 'Info.plist').write_bytes(plistlib.dumps(info))
        source_hash = hashlib.sha256(binary.read_bytes()).hexdigest()
        (resources / 'build.json').write_text(json.dumps({'source_sha256': source_hash}, indent=2) + '\n')
        subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-', str(app)], check=True)
        subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)], check=True)
        if output.exists():
            output.rename(previous)
        try:
            app.rename(output)
        except OSError:
            if previous.exists():
                try:
                    previous.rename(output)
                except OSError as rollback_error:
                    raise OSError(f'Не удалось восстановить приложение; предыдущая сборка сохранена: {previous}') from rollback_error
            raise
        if previous.exists():
            shutil.rmtree(previous)
    return {'bundle': str(output), 'bundle_id': BUNDLE_ID, 'source_sha256': source_hash}


if __name__ == '__main__':
    try:
        print(json.dumps(package(Path(__file__).resolve().parent), ensure_ascii=False, indent=2))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(f'Упаковка Lazarus LCL: {error}')
