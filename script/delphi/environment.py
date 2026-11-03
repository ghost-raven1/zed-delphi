#!/usr/bin/env python3
"""Inspect local Delphi/FPC tools without installing software or testing a license."""

import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess


def version_probe(path, arguments, timeout=3):
    """Return only a version token, never arbitrary tool output or environment data."""
    if arguments is None or (os.name == 'nt' and Path(path).suffix.lower() in ('.bat', '.cmd')):
        return {'status': 'not_probed', 'version': None}
    try:
        process = subprocess.run([str(path), *arguments], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 text=True, errors='replace', timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {'status': 'timeout', 'version': None}
    except OSError:
        return {'status': 'failed', 'version': None}
    match = re.search(r'(?<![\w.])\d+\.\d+(?:\.\d+){0,2}(?![\w.])', process.stdout)
    if process.returncode != 0 or not match:
        return {'status': 'failed', 'version': None, 'exit_code': process.returncode}
    return {'status': 'reported', 'version': match.group(), 'exit_code': 0}


def locate(name, override=None, candidates=(), version_arguments=None):
    """An explicit missing override must not silently fall back to another installation."""
    if override is not None:
        explicit = str(Path(override).expanduser()) if str(override) else ''
        selected = shutil.which(explicit) or explicit
        origin = 'explicit'
    else:
        selected = shutil.which(name)
        origin = 'path'
        if not selected:
            selected = next((str(path) for path in candidates if path.is_file()), None)
            origin = 'known_location'
    if not selected or not Path(selected).is_file():
        return {'status': 'missing', 'path': str(selected) if override is not None else None,
                'source': origin if override is not None else None, 'version_probe': {'status': 'not_probed', 'version': None}}
    path = Path(selected).absolute()
    if os.name != 'nt' and not os.access(path, os.X_OK):
        return {'status': 'not_executable', 'path': str(path), 'source': origin,
                'version_probe': {'status': 'not_probed', 'version': None}}
    return {'status': 'found', 'path': str(path), 'source': origin,
            'version_probe': version_probe(path, version_arguments)}


def known_tool_paths(name, system, home):
    suffix = '.exe' if system == 'Windows' else ''
    paths = [home / '.local/bin' / (name + suffix)]
    tools = home / '.local/share/zed-delphi/toolchains'
    if name == 'pasls':
        paths.append(tools / 'pasls/bin' / ('pasls-server' + suffix))
    elif name == 'codelldb':
        paths.extend(sorted((tools / 'codelldb').glob('*/extension/adapter/codelldb' + suffix), reverse=True))
        paths.extend(sorted((home / '.vscode/extensions').glob('vadimcn.vscode-lldb-*/adapter/codelldb' + suffix), reverse=True))
        if system == 'Linux':
            paths.append(Path('/opt/codelldb/extension/adapter/codelldb'))
    elif name == 'lazbuild':
        paths.append(tools / 'lazarus-cocoa/lazbuild')
        if system == 'Darwin':
            paths.extend([Path('/Applications/Lazarus/lazbuild'),
                          Path('/Applications/Lazarus.app/Contents/MacOS/lazbuild')])
        elif system == 'Windows':
            paths.append(Path(os.environ.get('SystemDrive', 'C:') + '/') / 'lazarus/lazbuild.exe')
    elif name == 'fpc':
        if system == 'Darwin':
            paths.extend([Path('/opt/homebrew/bin/fpc'), Path('/usr/local/bin/fpc')])
        elif system == 'Linux':
            paths.extend(sorted(Path('/opt/zed-delphi/fpc').glob('*/bin/fpc'), reverse=True))
        elif system == 'Windows':
            drive = Path(os.environ.get('SystemDrive', 'C:') + '/')
            for base in (drive / 'FPC', drive / 'lazarus/fpc'):
                paths.extend(sorted(base.glob('*/bin/*/fpc.exe'), reverse=True))
    return paths


def windows_delphi_registry_roots():
    """Read only the installation directory for BDS 20.0, never licensing keys."""
    try:
        import winreg
    except ImportError:
        return []
    roots = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            try:
                with winreg.OpenKey(hive, r'SOFTWARE\Embarcadero\BDS\20.0', 0,
                                    winreg.KEY_READ | view) as key:
                    value, _ = winreg.QueryValueEx(key, 'RootDir')
                    if isinstance(value, str) and value:
                        roots.append(Path(value))
            except OSError:
                continue
    return roots


def codelldb_version(path):
    """CodeLLDB has no --version switch; identify the adjacent extension manifest."""
    manifest = Path(path).resolve().parent.parent / 'package.json'
    try:
        if manifest.stat().st_size > 1024 * 1024:
            return {'status': 'not_probed', 'version': None}
        package = json.loads(manifest.read_text(encoding='utf-8'))
        version = package.get('version')
        if (package.get('name') == 'vscode-lldb' and package.get('publisher') == 'vadimcn'
                and isinstance(version, str) and re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][\w.-]+)?', version)):
            return {'status': 'manifest', 'version': version, 'manifest_path': str(manifest)}
    except (OSError, UnicodeError, ValueError, AttributeError):
        pass
    return {'status': 'not_probed', 'version': None}


def inspect_delphi(system, overrides):
    result = {'expected_version': 'Delphi 10.3 / BDS 20.0', 'version_verified': False,
              'license_checked': False, 'acceptance': 'not_performed'}
    if system != 'Windows':
        return {**result, 'status': 'unsupported_host', 'root': None, 'files': {}}
    roots = []
    root_override = overrides.get('delphi_root')
    if root_override is not None:
        roots = [(Path(root_override).expanduser(), 'explicit')] if str(root_override) else []
    else:
        roots.extend((path, 'registry_bds_20') for path in windows_delphi_registry_roots())
        bds = os.environ.get('BDS')
        if bds and Path(bds).name == '20.0':
            roots.append((Path(bds), 'environment_bds_20'))
        for name in ('ProgramFiles(x86)', 'ProgramFiles'):
            if os.environ.get(name):
                roots.append((Path(os.environ[name]) / 'Embarcadero/Studio/20.0', 'known_location'))
    selected = next(((path, origin) for path, origin in roots if path.is_dir()), None)
    if selected is None and roots and root_override is not None:
        selected = roots[0]
    root, origin = selected if selected else (None, 'explicit' if root_override is not None else None)
    files = {}
    for name, filename in [('rsvars', 'rsvars.bat'), ('dcc32', 'dcc32.exe'),
                           ('dcc64', 'dcc64.exe'), ('ide', 'bds.exe'),
                           ('delphi_targets', 'CodeGear.Delphi.Targets')]:
        path = root / 'bin' / filename if root else None
        files[name] = {'status': 'found' if path and path.is_file() else 'missing',
                       'path': str(path) if path else None}
    windows = Path(os.environ.get('WINDIR', os.environ.get('SystemRoot', 'C:/Windows')))
    files['msbuild'] = locate('MSBuild.exe', overrides.get('msbuild'),
                               [windows / 'Microsoft.NET/Framework/v4.0.30319/MSBuild.exe',
                                windows / 'Microsoft.NET/Framework64/v4.0.30319/MSBuild.exe'])
    status = 'missing'
    if root and root.is_dir():
        status = 'found' if all(item['status'] == 'found' for item in files.values()) else 'partial'
    return {**result, 'status': status,
            'root': str(root) if root else None, 'source': origin, 'files': files}


def doctor(overrides=None):
    """Produce an inventory; executable discovery is not build/debug acceptance."""
    overrides = overrides or {}
    system = platform.system()
    machine = platform.machine()
    home = Path.home()
    os_version = None
    distribution = None
    if system == 'Darwin':
        os_version = platform.mac_ver()[0] or None
    elif system == 'Windows':
        os_version = platform.win32_ver()[1] or None
    elif system == 'Linux':
        try:
            details = platform.freedesktop_os_release()
            distribution = {key: details[key] for key in ('ID', 'PRETTY_NAME', 'VERSION_ID') if key in details}
            os_version = details.get('VERSION_ID')
        except (OSError, AttributeError):
            pass
    tools = {}
    for name, arguments in [('fpc', ['-iV']), ('lazbuild', ['--version']),
                            ('pasls', None), ('codelldb', None)]:
        executable = name + ('.exe' if system == 'Windows' else '')
        tools[name] = locate(executable, overrides.get(name), known_tool_paths(name, system, home), arguments)
        if name == 'codelldb' and tools[name]['status'] == 'found':
            tools[name]['version_probe'] = codelldb_version(tools[name]['path'])
    return {
        'schema_version': 1,
        'platform': {'os': {'Darwin': 'macos', 'Windows': 'windows', 'Linux': 'linux'}.get(system, system.lower()),
                     'system': system, 'version': os_version, 'distribution': distribution,
                     'kernel_release': platform.release(),
                     'architecture': {'aarch64': 'arm64', 'amd64': 'x86_64'}.get(machine.lower(), machine.lower())},
        'tools': tools, 'delphi_10_3': inspect_delphi(system, overrides),
        'missing_tools': [name for name, item in tools.items() if item['status'] != 'found'],
        'acceptance': 'not_performed',
        'scope': 'local_inventory_and_bounded_version_queries_only',
    }


def human_report(report):
    platform_info = report['platform']
    name = (platform_info['distribution'] or {}).get('PRETTY_NAME', platform_info['os'])
    version = f" {platform_info['version']}" if platform_info['version'] and not platform_info['distribution'] else ''
    lines = [f"Окружение: {name}{version}, {platform_info['architecture']}; ядро {platform_info['kernel_release']}"]
    labels = {'found': 'найден', 'missing': 'не найден', 'not_executable': 'нет права запуска',
              'partial': 'найдены не все компоненты'}
    for name, item in report['tools'].items():
        detail = f" — {item['path']}" if item['path'] else ''
        probe = item['version_probe']
        if probe['version']:
            detail += f"; версия {probe['version']}" + (' (манифест расширения)' if probe['status'] == 'manifest' else '')
        elif probe['status'] in ('failed', 'timeout'):
            detail += '; версия не получена' + (' (таймаут)' if probe['status'] == 'timeout' else '')
        lines.append(f"{name}: {labels[item['status']]}{detail}")
    delphi = report['delphi_10_3']
    if delphi['status'] == 'unsupported_host':
        lines.append('Delphi 10.3: локальные инструменты BDS 20.0 проверяются только в Windows.')
    else:
        lines.append(f"Delphi 10.3 / BDS 20.0: {labels[delphi['status']]}" +
                     (f" — {delphi['root']}" if delphi['root'] else ''))
        for name, item in delphi['files'].items():
            lines.append(f"  {name}: {labels[item['status']]}" + (f" — {item['path']}" if item['path'] else ''))
    lines.append('Это инвентаризация: сборка, отладка, версия Delphi и лицензия не проверялись.')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Диагностика локальных инструментов Zed Delphi без установки и запуска IDE.')
    parser.add_argument('command', nargs='?', choices=['doctor'], default='doctor')
    parser.add_argument('--json', action='store_true', help='Вывести машиночитаемый JSON вместо текста')
    for name in ('fpc', 'lazbuild', 'pasls', 'codelldb', 'delphi-root', 'msbuild'):
        parser.add_argument('--' + name, help='Явный путь; отсутствующий путь не заменяется другим автоматически')
    options = vars(parser.parse_args())
    report = doctor(options)
    print(json.dumps(report, ensure_ascii=False, indent=2) if options['json'] else human_report(report))


if __name__ == '__main__':
    main()
