#!/usr/bin/env python3
"""Build Delphi/FPC/Lazarus projects, locally or in an existing Windows SSH checkout."""

import argparse
import base64
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--tool', choices=['fpc', 'lazarus', 'delphi'])
    result.add_argument('--project')
    result.add_argument('--config', default='Debug')
    result.add_argument('--platform', default='Win64')
    result.add_argument('--msbuild-target', choices=['Build', 'Clean', 'Rebuild', 'Deploy'],
                        help='Delphi MSBuild target (default: Build); Clean/Deploy cannot use --run')
    result.add_argument('--rsvars', help='Path to the selected Delphi installation rsvars.bat')
    result.add_argument('--compiler', help='Explicit fpc, lazbuild or MSBuild executable')
    result.add_argument('--widgetset', help='Lazarus widgetset, e.g. cocoa, gtk2 or qt5')
    result.add_argument('--output', help='FPC executable output path')
    result.add_argument('--target-os', help='FPC target operating system (-T), e.g. linux, darwin, win64')
    result.add_argument('--target-cpu', help='FPC target processor (-P), e.g. x86_64, aarch64, i386')
    result.add_argument('--run', action='store_true', help='Run only after successful compilation')
    result.add_argument('--program', help='Executable to run (required for Delphi/Lazarus)')
    result.add_argument('--arg', action='append', default=[], help='Program argument; repeat as needed')
    result.add_argument('--ssh-host', help='OpenSSH config alias for a Windows build host')
    result.add_argument('--remote-helper', help='Absolute path to this script on the Windows host')
    result.add_argument('--remote-python', default='python')
    result.add_argument('--request-stdin', action='store_true', help=argparse.SUPPRESS)
    return result


def checked_text(value, name):
    if not isinstance(value, str) or not value or any(c in value for c in '\x00\r\n'):
        raise ValueError(f'{name} must be a nonempty single-line string')
    return value


def command_for(request, project, windows):
    """Create argv without shell interpretation; preserve paths and program arguments."""
    tool = request['tool']
    target = request.get('msbuild_target')
    if target is not None:
        if tool != 'delphi':
            raise ValueError('--msbuild-target applies only to Delphi MSBuild')
        if target not in ('Build', 'Clean', 'Rebuild', 'Deploy'):
            raise ValueError('msbuild_target must be Build, Clean, Rebuild or Deploy')
    target = target or 'Build'
    if tool == 'delphi' and request.get('run') and target in ('Clean', 'Deploy'):
        raise ValueError('--run requires the Delphi Build or Rebuild target')
    config = checked_text(request['config'], 'config')
    # MSBuild separates multiple property values with ; and , even in argv.
    if not re.fullmatch(r'[\w .-]+', config):
        raise ValueError('config contains unsupported property separators')
    compiler = request.get('compiler')
    widgetset = request.get('widgetset')
    if widgetset is not None:
        if tool != 'lazarus' or not isinstance(widgetset, str) or not re.fullmatch(r'[a-z][a-z0-9]*', widgetset):
            raise ValueError('--widgetset requires a lowercase Lazarus widgetset identifier')
    targets = []
    for key, flag in (('target_os', '-T'), ('target_cpu', '-P')):
        value = request.get(key)
        if value is not None:
            if tool != 'fpc':
                raise ValueError('--target-os and --target-cpu apply only to Free Pascal')
            if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', value):
                raise ValueError(f'{key} must be a lowercase FPC target identifier')
            targets.append(flag + value)
    if tool == 'fpc':
        if project.suffix.lower() not in ('.pas', '.dpr', '.lpr'):
            raise ValueError('Free Pascal requires a .pas, .dpr or .lpr entry point')
        if config not in ('Debug', 'Release'):
            raise ValueError('FPC config must be Debug or Release')
        target_os = request.get('target_os')
        windows_output = target_os in ('win32', 'win64', 'wince') if target_os else windows
        output = Path(request.get('output') or project.with_suffix('.exe' if windows_output else ''))
        if not output.is_absolute():
            output = project.parent / output
        flags = ['-g', '-gl', '-gw3', '-O-'] if config == 'Debug' else ['-O2']
        return [compiler or 'fpc', '-Mdelphi', *targets, *flags, '-o' + str(output), str(project)], output
    if tool == 'lazarus':
        if project.suffix.lower() != '.lpi':
            raise ValueError('Lazarus requires a .lpi project')
        command = [compiler or 'lazbuild', '--build-mode=' + config, str(project)]
        if widgetset:
            command.insert(1, '--widgetset=' + widgetset)
    elif tool == 'delphi':
        if not windows:
            raise ValueError('Embarcadero builds require Windows; use --ssh-host for a Windows host')
        if project.suffix.lower() not in ('.dproj', '.groupproj'):
            raise ValueError('Embarcadero MSBuild requires .dproj or .groupproj')
        platform = checked_text(request['platform'], 'platform')
        if not re.fullmatch(r'[A-Za-z0-9_]+', platform):
            raise ValueError('platform contains unsupported property separators')
        command = [compiler or 'MSBuild.exe', str(project), '/nologo', '/t:' + target,
                   '/p:Config=' + config, '/p:Platform=' + platform, '/nodeReuse:false']
    else:
        raise ValueError('Unknown compiler tool')
    program = request.get('program')
    output = Path(program) if program else None
    if output and not output.is_absolute():
        output = project.parent / output
    return command, output


def rsvars_command(path):
    """Use cmd's own quoting, not the C-runtime quoting used for subprocess argv lists."""
    checked_text(path, 'rsvars')
    if any(character in path for character in '"%!&|<>^'):
        raise ValueError('rsvars path contains cmd metacharacters; use a safe installation path')
    return f'cmd.exe /u /d /v:off /s /c "call "{path}" >nul && set"'


def delphi_environment(rsvars):
    """Import the selected rsvars environment; never interpolate build arguments in cmd."""
    path = str(Path(checked_text(rsvars, 'rsvars')).resolve(strict=True))
    result = subprocess.run(
        rsvars_command(path),
        stdout=subprocess.PIPE, stderr=None, encoding='utf-16le', check=True,
    )
    environment = dict(os.environ)
    for line in result.stdout.splitlines():
        key, separator, value = line.partition('=')
        if separator and key:
            environment[key.upper()] = value
    return environment


def native_target():
    """Describe the running host using FPC's target identifiers."""
    machine = platform.machine().lower()
    cpu = {'amd64': 'x86_64', 'arm64': 'aarch64', 'i686': 'i386',
           'i586': 'i386', 'armv7l': 'arm', 'armv6l': 'arm'}.get(machine, machine)
    system = platform.system().lower()
    operating_system = ('win64' if cpu in ('x86_64', 'aarch64') else 'win32') if system == 'windows' else system
    return operating_system, cpu


def ensure_native_run(request, host_target=None):
    """Do not launch explicitly cross-compiled output on the build host."""
    if not request.get('run') or request['tool'] not in ('fpc', 'delphi'):
        return
    host_os, host_cpu = host_target or native_target()
    if request['tool'] == 'delphi':
        if request.get('platform', 'Win64') not in ('Win32', 'Win64') or host_os not in ('win32', 'win64'):
            raise ValueError('--run for Delphi requires a Win32/Win64 target on a Windows host; build foreign targets without --run and deploy separately')
        return
    if ((request.get('target_os') and request['target_os'] != host_os)
            or (request.get('target_cpu') and request['target_cpu'] != host_cpu)):
        raise ValueError('--run cannot execute a foreign FPC target; build first, then run on its target host')


def artifact_stamp(path):
    """Exclude access time: reading an old executable does not make it a new build."""
    try:
        info = path.stat()
    except FileNotFoundError:
        return None
    return info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def execute(request):
    project = Path(checked_text(request.get('project'), 'project')).resolve(strict=True)
    if not project.is_file():
        raise ValueError('project must be a file')
    ensure_native_run(request)
    command, output = command_for(request, project, os.name == 'nt')
    if request.get('run') and output is None:
        raise ValueError('--run requires --program for Delphi and Lazarus projects')
    previous_output = artifact_stamp(output) if request['tool'] == 'fpc' and request.get('run') else None
    environment = None
    if request['tool'] == 'delphi' and request.get('rsvars'):
        environment = delphi_environment(request['rsvars'])
    result = subprocess.run(command, cwd=project.parent, env=environment)
    if result.returncode != 0 or not request.get('run'):
        return result.returncode
    if not output.is_file():
        raise ValueError(f'Build succeeded but executable does not exist: {output}')
    if previous_output is not None and artifact_stamp(output) == previous_output:
        raise ValueError(f'FPC succeeded but did not create or update executable: {output}; compile a program entry point before using --run')
    return subprocess.run([str(output), *request.get('arg', [])],
                          cwd=project.parent, env=environment).returncode


def remote_command(host, helper, python):
    """Encode the Windows launcher so neither local nor remote shells reparse paths."""
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.@-]*', host):
        raise ValueError('ssh-host must be an OpenSSH host alias (configure ports in ~/.ssh/config)')
    helper = checked_text(helper, 'remote-helper')
    python = checked_text(python, 'remote-python')
    literal = lambda value: "'" + value.replace("'", "''") + "'"
    script = f"& {literal(python)} {literal(helper)} --request-stdin; exit $LASTEXITCODE"
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    return ['ssh', '-T', '-o', 'BatchMode=yes', '--', host, 'powershell.exe',
            '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded]


def main():
    options = vars(parser().parse_args())
    try:
        if options.pop('request_stdin'):
            request = json.load(sys.stdin)
            if not isinstance(request, dict):
                raise ValueError('Expected a JSON build request')
            return execute(request)
        if not options.get('tool') or not options.get('project'):
            raise ValueError('--tool and --project are required')
        host = options.pop('ssh_host')
        helper = options.pop('remote_helper')
        python = options.pop('remote_python')
        if host:
            command = remote_command(host, helper, python)
            return subprocess.run(command, input=json.dumps(options).encode('utf-8')).returncode
        return execute(options)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f'Delphi build: {error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    sys.exit(main())
