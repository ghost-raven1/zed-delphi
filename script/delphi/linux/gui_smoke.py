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
    parser.add_argument('--pasls', type=Path, help='Also verify definition lookup through this real LSP')
    parser.add_argument('--ui-language', choices=('ru', 'en'), default='ru')
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    russian = options.ui_language == 'ru'
    project = output / ('Проект Delphi с пробелами' if russian else 'Delphi Space Project')
    shutil.copytree(options.fixture, project)
    (project / '.zed/settings.json').write_text(json.dumps({
        'languages': {'Delphi': {'language_servers': ['pasls'] if options.pasls else []}},
    }))
    home = output / 'home'
    config = home / '.config/zed'
    config.mkdir(parents=True)
    settings = {
        'theme': 'One Dark', 'buffer_font_size': 16, 'ui_font_size': 14,
        'telemetry': {'metrics': True, 'diagnostics': True}, 'auto_update': True,
        'dap': {'CodeLLDB': {'binary': str(options.codelldb.resolve())}},
    }
    if options.pasls:
        settings['lsp'] = {'pasls': {'binary': {'path': str(options.pasls.resolve())}}}
    (config / 'settings.json').write_text(json.dumps(settings))
    runtime = output / 'runtime'
    runtime.mkdir(mode=0o700)
    environment = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'),
                       XDG_DATA_HOME=str(home / '.local/share'), XDG_CACHE_HOME=str(home / '.cache'),
                       XDG_RUNTIME_DIR=str(runtime), ZED_ALLOW_EMULATED_GPU='1')
    result = {'status': 'running', 'platform': os.uname().machine,
              'binary': str(options.zed.resolve()),
              'pasls': str(options.pasls.resolve()) if options.pasls else None,
              'ui_language': options.ui_language, 'checks': []}
    ocr_language = 'rus+eng' if russian else 'eng'

    def key(value):
        run('xdotool', 'key', '--clearmodifiers', value)
        time.sleep(0.5)

    def type_text(value):
        if value.isascii():
            run('xdotool', 'type', '--clearmodifiers', '--delay', '40', value)
        else:
            subprocess.run(['xclip', '-selection', 'clipboard'], input=value.encode(),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            key('ctrl+v')

    def capture(stage):
        picture = output / f'{stage}.png'
        run('import', '-window', 'root', str(picture))
        text = run('tesseract', str(picture), 'stdout', '-l', ocr_language, '--psm', '11').stdout
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
        data = run('tesseract', str(output / f'{stage}.png'), 'stdout', '-l', ocr_language, '--psm', '11', 'tsv').stdout
        words = csv.DictReader(io.StringIO(data), delimiter='\t', quoting=csv.QUOTE_NONE)
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

    def wait_cursor_line(stage, line, timeout=30, retry_definition=False):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            capture(stage)
            picture = output / f'{stage}.png'
            width, height = map(int, run('identify', '-format', '%w %h', str(picture)).stdout.split())
            status = output / f'{stage}-cursor.png'
            run('convert', str(picture), '-crop', f'500x26+{width - 500}+{height - 26}',
                '+repage', '-resize', '400%', str(status))
            text = run('tesseract', str(status), 'stdout', '--psm', '7').stdout
            (output / f'{stage}-cursor.txt').write_text(text)
            if re.search(rf'(?<!\d){line}\s*:\s*\d+', text):
                result['checks'].append(stage)
                print(f'PASS: {stage} (cursor line {line})', flush=True)
                return
            # Retry only while still on the original call; never navigate onward from another result.
            if retry_definition and re.search(r'(?<!\d)25\s*:\s*\d+', text):
                key('F12')
            time.sleep(1)
        raise RuntimeError(f'Cursor did not reach line {line}: {stage}; see screenshots and OCR')

    with (output / 'packaged-launch.log').open('w') as log:
        process = subprocess.Popen(['dbus-run-session', '--', str(options.zed.resolve()),
                                    '--foreground', str(project)], env=environment,
                                   stdout=log, stderr=subprocess.STDOUT)
        try:
            wait_text('trust-project', ['Неизвестный проект', 'Доверять и продолжить'] if russian
                      else ['Unrecognized Project', 'Trust and Continue'])
            windows = run('xdotool', 'search', '--onlyvisible', '--class', 'zed').stdout.splitlines()
            run('xdotool', 'windowfocus', windows[0])
            key('Return')
            time.sleep(1)
            key('ctrl+p')
            type_text('Arithmetic.pas')
            key('Return')
            wait_text('native-delphi', ['Arithmetic.pas', 'Delphi', 'AddValues'])
            if russian:
                key('ctrl+shift+p')
                type_text('перейти к определению')
                wait_text('russian-command-search', ['перейти к определению'])
                key('Escape')
                key('ctrl+shift+p')
                type_text('go to definition')
                wait_text('english-command-alias', ['перейти к определению'])
                key('Escape')
            if options.pasls:
                key('ctrl+g')
                type_text('25:18')
                key('Return')
                wait_cursor_line('lsp-call-site', 25)
                key('F12')
                wait_cursor_line('lsp-definition', 18, retry_definition=True)
            key('ctrl+g')
            type_text('20')
            key('Return')
            key('F9')
            key('F4')
            wait_text('debug-picker', [r'debug multi.unit', 'Запустить' if russian else 'Spawn'])
            key('Return')
            wait_text('breakpoint', ['Стек вызовов', 'Точки останова', 'AddValues', 'Calculate', 'Переменные'] if russian
                      else ['Frames', 'Breakpoints', 'AddValues', 'Calculate', 'Variables'])
            click_label('Переменные' if russian else 'Variables', 'breakpoint')
            wait_text('variables', [r'LeftValue\s*=\s*20', r'RightValue\s*=\s*22'])
            key('F10')
            wait_text('step-result', [r'RESULT\s*=\s*42'])
            key('F5')
            time.sleep(1)
            capture('after-continue')
            click_label('Консоль' if russian else 'Console', 'after-continue')
            wait_text('exit-zero', [r'Process exited with code\s*0'])
            executable = project / 'MultiUnit'
            executed = run(str(executable))
            if executed.stdout.strip() != '42':
                raise RuntimeError(f'Unexpected output from UI-built program: {executed.stdout!r}')
            (output / 'program-output.txt').write_text(executed.stdout)
            if russian:
                key('ctrl+comma')
                wait_text('russian-settings', ['Поиск настроек'])
                settings_windows = run('xdotool', 'search', '--onlyvisible', '--name',
                                       'Zed.*Настройки').stdout.splitlines()
                run('xdotool', 'windowfocus', settings_windows[-1])
                key('ctrl+f')
                type_text('шрифта')
                wait_text('russian-settings-search', ['Размер шрифта'])
                key('ctrl+a')
                type_text('font size')
                wait_text('english-settings-alias', ['Размер шрифта'])
                key('ctrl+w')
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
