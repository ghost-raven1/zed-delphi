#!/usr/bin/env python3
"""Exercise a packaged Zed through X11, preserving screenshots and OCR assertions."""

import argparse
import csv
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


def run(*arguments, **options):
    return subprocess.run(arguments, check=True, text=True, capture_output=True, **options)


def main():
    os.environ.setdefault('OMP_THREAD_LIMIT', '1')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zed', type=Path, required=True)
    parser.add_argument('--codelldb', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    project = output / 'Delphi Space Project'
    shutil.copytree(options.fixture, project)
    # This acceptance covers native language/build/debug; the LSP has a separate smoke test.
    (project / '.zed/settings.json').write_text(json.dumps({'languages': {'Delphi': {'language_servers': []}}}))
    home = output / 'home'
    config = home / '.config/zed'
    config.mkdir(parents=True)
    (config / 'settings.json').write_text(json.dumps({
        'theme': 'One Dark', 'buffer_font_size': 16, 'ui_font_size': 14,
        'telemetry': {'metrics': True, 'diagnostics': True}, 'auto_update': True,
        'dap': {'CodeLLDB': {'binary': str(options.codelldb.resolve())}},
    }))
    runtime = output / 'runtime'
    runtime.mkdir(mode=0o700)
    environment = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'),
                       XDG_DATA_HOME=str(home / '.local/share'), XDG_CACHE_HOME=str(home / '.cache'),
                       XDG_RUNTIME_DIR=str(runtime), ZED_ALLOW_EMULATED_GPU='1')
    result = {'status': 'running', 'platform': os.uname().machine,
              'binary': str(options.zed.resolve()), 'checks': []}

    def key(value):
        run('xdotool', 'key', '--clearmodifiers', value)
        time.sleep(0.5)

    def type_text(value):
        run('xdotool', 'type', '--clearmodifiers', '--delay', '40', value)

    def capture(stage):
        picture = output / f'{stage}.png'
        run('import', '-window', 'root', str(picture))
        text = run('tesseract', str(picture), 'stdout', '--psm', '11').stdout
        (output / f'{stage}.txt').write_text(text)
        return text

    def wait_text(stage, patterns, timeout=90):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f'Editor exited during {stage}; see packaged-launch.log')
            text = capture(stage)
            if all(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
                result['checks'].append(stage)
                print(f'PASS: {stage}', flush=True)
                return text
            time.sleep(1)
        raise RuntimeError(f'UI assertion timed out: {stage}; see {stage}.png and {stage}.txt')

    def click_label(label, stage):
        data = run('tesseract', str(output / f'{stage}.png'), 'stdout', '--psm', '11', 'tsv').stdout
        words = csv.DictReader(io.StringIO(data), delimiter='\t')
        for word in words:
            if word['text'].casefold() == label.casefold():
                x = int(word['left']) + int(word['width']) // 2
                y = int(word['top']) + int(word['height']) // 2
                run('xdotool', 'mousemove', '--sync', str(x), str(y))
                time.sleep(0.3)
                run('xdotool', 'click', '1')
                time.sleep(0.3)
                run('xdotool', 'mousemove', '1040', '500')
                return
        raise RuntimeError(f'Cannot locate visible label {label!r} in {stage}')

    with (output / 'packaged-launch.log').open('w') as log:
        process = subprocess.Popen(['dbus-run-session', '--', str(options.zed.resolve()),
                                    '--foreground', str(project)], env=environment,
                                   stdout=log, stderr=subprocess.STDOUT)
        try:
            wait_text('trust-project', ['Unrecognized Project', 'Trust and Continue'])
            windows = run('xdotool', 'search', '--onlyvisible', '--class', 'zed').stdout.splitlines()
            run('xdotool', 'windowfocus', windows[0])
            key('Return')
            time.sleep(1)
            key('ctrl+p')
            type_text('Arithmetic.pas')
            key('Return')
            wait_text('native-delphi', ['Arithmetic.pas', 'Delphi', 'AddValues'])
            key('ctrl+g')
            type_text('20')
            key('Return')
            key('F9')
            key('F4')
            wait_text('debug-picker', [r'debug multi.unit', 'Spawn'])
            key('Return')
            wait_text('breakpoint', ['Frames', 'Breakpoints', 'AddValues', 'Calculate', 'Variables'])
            click_label('Variables', 'breakpoint')
            wait_text('variables', [r'LeftValue\s*=\s*20', r'RightValue\s*=\s*22'])
            key('F10')
            wait_text('step-result', [r'RESULT\s*=\s*42'])
            key('F5')
            time.sleep(1)
            capture('after-continue')
            click_label('Console', 'after-continue')
            wait_text('exit-zero', [r'Process exited with code\s*0'])
            executable = project / 'MultiUnit'
            executed = run(str(executable))
            if executed.stdout.strip() != '42':
                raise RuntimeError(f'Unexpected output from UI-built program: {executed.stdout!r}')
            (output / 'program-output.txt').write_text(executed.stdout)
            result['status'] = 'passed'
            result['checks'].append('ui-built-program-output-42')
        except Exception as error:
            result.update(status='failed', error=str(error))
            raise
        finally:
            (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
            key('ctrl+q')
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=10)


if __name__ == '__main__':
    main()
