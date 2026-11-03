#!/usr/bin/env python3
"""Verify a real GTK LCL window, mouse click, visible result and normal closure."""

import argparse
import csv
import io
import json
from pathlib import Path
import re
import subprocess
import time


def run(*arguments):
    return subprocess.run(arguments, check=True, text=True, capture_output=True).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    result = {'status': 'running', 'checks': [], 'binary': str(options.binary.resolve())}
    (output / 'binary-libraries.txt').write_text(run('ldd', str(options.binary)))
    with (output / 'application.log').open('w') as log:
        process = subprocess.Popen([str(options.binary.resolve())], stdout=log,
                                   stderr=subprocess.STDOUT, cwd=options.binary.parent)
        try:
            deadline = time.monotonic() + 30
            window = None
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f'LCL application exited before showing its form: {process.returncode}')
                found = subprocess.run(['xdotool', 'search', '--onlyvisible', '--name',
                                        'Zed Delphi.*Lazarus LCL'], text=True, capture_output=True)
                if found.returncode == 0 and found.stdout.strip():
                    window = found.stdout.splitlines()[0]
                    break
                time.sleep(0.2)
            if window is None:
                raise RuntimeError('LCL form did not become visible')
            run('xdotool', 'windowfocus', '--sync', window)
            result['checks'].append('visible-lcl-form')

            def capture(stage):
                picture = output / f'{stage}.png'
                run('import', '-window', 'root', str(picture))
                # Small GTK button text and its dotted focus outline confuse OCR
                # on a full virtual screen. Preserve that screenshot, but read
                # an enlarged capture of the actual client window.
                window_picture = output / f'{stage}-window.png'
                ocr_picture = output / f'{stage}-ocr.png'
                run('import', '-window', window, str(window_picture))
                run('convert', str(window_picture), '-resize', '300%', str(ocr_picture))
                text = run('tesseract', str(ocr_picture), 'stdout', '--psm', '11')
                (output / f'{stage}.txt').write_text(text)
                return text

            def click_word(stage, word):
                data = run('tesseract', str(output / f'{stage}-ocr.png'), 'stdout', '--psm', '11', 'tsv')
                geometry = dict(line.split('=', 1) for line in
                                run('xdotool', 'getwindowgeometry', '--shell', window).splitlines())
                for item in csv.DictReader(io.StringIO(data), delimiter='\t', quoting=csv.QUOTE_NONE):
                    if item['text'].casefold() == word.casefold():
                        x = int(geometry['X']) + (int(item['left']) + int(item['width']) // 2) // 3
                        y = int(geometry['Y']) + (int(item['top']) + int(item['height']) // 2) // 3
                        run('xdotool', 'mousemove', '--sync', str(x), str(y))
                        run('xdotool', 'click', '1')
                        return
                raise RuntimeError(f'Visible button {word!r} not found; see {stage}.png')

            time.sleep(0.5)
            initial = capture('form-ready')
            if not re.search(r'Ready', initial):
                raise RuntimeError(f'Initial form label not visible: {initial}')
            click_word('form-ready', 'Calculate')
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if re.search(r'Result\s*:\s*42', capture('form-result')):
                    result['checks'].append('mouse-click-visible-result-42')
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError('Clicking Calculate did not display Result: 42')
            click_word('form-result', 'Close')
            exit_code = process.wait(timeout=15)
            if exit_code != 0:
                raise RuntimeError(f'LCL application exited with {exit_code}')
            result['checks'].append('close-button-exit-zero')
            result['status'] = 'passed'
            print('PASS: real LCL window, mouse click, Result: 42, close button and exit 0')
        except Exception as error:
            result.update(status='failed', error=str(error))
            raise
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
