#!/usr/bin/env python3
"""Build a real LCL form, run its event loop and debug its button handler over DAP."""

import argparse
import json
import os
from pathlib import Path
import platform
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dap_remote import read_message, write_message


def stop_group(process):
    """Clean up only the session created by this test, including compiler/GUI children."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
    # A stopped child cannot handle SIGTERM even after the session leader exits.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def verify(adapter, binary, source, output):
    """Exercise source mapping, handler locals, step and graceful GUI shutdown."""
    lines = source.read_text().splitlines()
    breakpoint_line = next(index + 1 for index, line in enumerate(lines) if '// LCL_BREAKPOINT' in line)
    next_line = next(index + 1 for index, line in enumerate(lines) if '// LCL_AFTER_STEP' in line)
    messages = queue.Queue()
    pending = []
    sequence = 0
    debug_output = []
    with (output / 'adapter-stderr.log').open('w') as errors, (output / 'dap.jsonl').open('w') as transcript:
        process = subprocess.Popen([str(adapter)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=errors, start_new_session=True)
        disconnected = False

        def reader():
            try:
                while (message := read_message(process.stdout)) is not None:
                    messages.put(message)
                messages.put(EOFError('DAP adapter closed before the expected response'))
            except Exception as error:
                messages.put(error)

        threading.Thread(target=reader, daemon=True).start()

        def send(command, arguments):
            nonlocal sequence
            sequence += 1
            message = dict(seq=sequence, type='request', command=command, arguments=arguments)
            transcript.write(json.dumps({'sent': message}) + '\n')
            transcript.flush()
            write_message(process.stdin, message)
            return sequence

        def wait(predicate):
            for index, message in enumerate(pending):
                if predicate(message):
                    return pending.pop(index)
            deadline = time.monotonic() + 60
            while True:
                message = messages.get(timeout=max(0.01, deadline - time.monotonic()))
                if not isinstance(message, dict):
                    raise message
                transcript.write(json.dumps({'received': message}) + '\n')
                transcript.flush()
                if message.get('event') == 'output':
                    debug_output.append(message.get('body', {}).get('output', ''))
                if predicate(message):
                    return message
                if message.get('type') == 'response' and message.get('success') is False:
                    raise AssertionError(f'DAP request failed: {message}')
                pending.append(message)
                if time.monotonic() >= deadline:
                    raise TimeoutError('DAP expected event did not arrive within 60 seconds')

        def response(request):
            message = wait(lambda item: item.get('type') == 'response' and item.get('request_seq') == request)
            assert message.get('success'), message
            return message.get('body', {})

        def frame_and_values(thread_id):
            frames = response(send('stackTrace', dict(threadId=thread_id)))['stackFrames']
            assert len(frames) >= 2, frames
            frame = frames[0]
            assert Path(frame['source']['path']).resolve() == source, frame
            scopes = response(send('scopes', dict(frameId=frame['id'])))['scopes']
            values = {}
            for scope in scopes:
                if scope.get('expensive'):
                    continue
                variables = response(send('variables', dict(variablesReference=scope['variablesReference'])))
                values.update({value['name'].casefold(): value['value'] for value in variables['variables']})
            return frame, values

        try:
            response(send('initialize', dict(adapterID='lldb', linesStartAt1=True, columnsStartAt1=True,
                                            pathFormat='path', supportsRunInTerminalRequest=False)))
            launch = send('launch', dict(program=str(binary), cwd=str(binary.parent),
                                         args=['--smoke-test'], terminal='console'))
            wait(lambda item: item.get('event') == 'initialized')
            breakpoints = response(send('setBreakpoints', dict(source=dict(path=str(source)),
                                                               breakpoints=[dict(line=breakpoint_line)])))
            assert breakpoints['breakpoints'][0]['verified'], breakpoints
            response(send('configurationDone', {}))
            response(launch)
            stopped = wait(lambda item: item.get('event') == 'stopped')['body']
            assert stopped['reason'] == 'breakpoint', stopped
            thread_id = stopped['threadId']
            frame, before = frame_and_values(thread_id)
            assert frame['line'] == breakpoint_line, frame
            assert before.get('leftvalue') == '20' and before.get('rightvalue') == '22', before
            response(send('next', dict(threadId=thread_id)))
            stopped = wait(lambda item: item.get('event') == 'stopped')['body']
            assert stopped['reason'] == 'step', stopped
            frame, after = frame_and_values(stopped['threadId'])
            assert frame['line'] == next_line, frame
            assert after.get('totalvalue') == '42', after
            response(send('continue', dict(threadId=stopped['threadId'])))
            exited = wait(lambda item: item.get('event') == 'exited')['body']
            assert exited['exitCode'] == 0, exited
            wait(lambda item: item.get('event') == 'terminated')
            response(send('disconnect', dict(terminateDebuggee=True)))
            disconnected = True
            actual_output = ''.join(debug_output)
            assert 'LCL_SHOWN' in actual_output and 'LCL_RESULT=42' in actual_output, actual_output
            (output / 'debug-output.log').write_text(actual_output)
            return dict(breakpoint_line=breakpoint_line, step_line=next_line,
                        before=before, after=after, exit_code=exited['exitCode'])
        finally:
            if not disconnected and process.poll() is None:
                try:
                    send('disconnect', dict(terminateDebuggee=True))
                    process.wait(timeout=5)
                except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
                    # Preserve the original assertion; group cleanup below is the fallback.
                    pass
            stop_group(process)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--lazbuild', type=Path, required=True)
    parser.add_argument('--codelldb', type=Path, required=True)
    parser.add_argument('--widgetset', choices=['gtk2', 'cocoa', 'qt5', 'qt6'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    project = output / 'Проект Lazarus с пробелами'
    shutil.copytree(options.fixture.resolve(), project, ignore=shutil.ignore_patterns('lib', 'LclDemo', '*.app', '*.lps'))
    binary = project / ('LclDemo.exe' if os.name == 'nt' else 'LclDemo')
    result = dict(status='running', platform=platform.platform(), architecture=platform.machine(),
                  widgetset=options.widgetset, project=str(project), checks=[])
    build = Path(__file__).resolve().parents[1] / 'build.py'
    command = [sys.executable, str(build), '--tool', 'lazarus', '--project', str(project / 'LclDemo.lpi'),
               '--compiler', str(options.lazbuild.resolve()), '--widgetset', options.widgetset,
               '--config', 'Debug', '--run', '--program', str(binary), '--arg=--smoke-test']
    try:
        # This checks build.py's actual build-and-run path, including the LCL event loop.
        with (output / 'build-run.log').open('w') as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                status = process.wait(timeout=900)
                if status:
                    raise subprocess.CalledProcessError(status, command)
            finally:
                stop_group(process)
        log = (output / 'build-run.log').read_text()
        assert binary.is_file(), binary
        assert 'LCL_SHOWN' in log and 'LCL_RESULT=42' in log, log[-4000:]
        result['checks'].extend(['lazbuild-debug', 'standalone-form-shown', 'standalone-button-handler', 'standalone-exit-zero'])
        result['debug'] = verify(options.codelldb.resolve(), binary, project / 'MainForm.pas', output)
        result['checks'].extend(['source-breakpoint', 'handler-stack', 'locals-20-22', 'step-result-42',
                                 'continue-handler', 'debug-exit-zero'])
        result['status'] = 'passed'
        print('PASS: real Lazarus LCL build, form event loop, handler breakpoint, locals, step 42 and exit 0')
    except Exception as error:
        result.update(status='failed', error=str(error))
        raise
    finally:
        (output / 'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
