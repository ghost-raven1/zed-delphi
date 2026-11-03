#!/usr/bin/env python3
"""Compile the real sample and verify source breakpoints, locals and stepping over DAP."""

import argparse
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).parents[1]))
from dap_remote import read_message, write_message


def verify(adapter, binary, source, breakpoint_line=10, expected_values=None):
    expected_values = expected_values or {'Left': '20', 'Right': '22'}
    process = subprocess.Popen([adapter], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    messages = queue.Queue()
    pending = []
    sequence = 0

    def reader():
        try:
            while (message := read_message(process.stdout)) is not None:
                messages.put(message)
        except Exception as error:
            messages.put(error)

    threading.Thread(target=reader, daemon=True).start()

    def send(command, arguments):
        nonlocal sequence
        sequence += 1
        write_message(process.stdin, dict(seq=sequence, type='request', command=command,
                                         arguments=arguments))
        return sequence

    def wait(predicate):
        for index, message in enumerate(pending):
            if predicate(message):
                return pending.pop(index)
        while True:
            message = messages.get(timeout=30)
            if not isinstance(message, dict):
                raise message
            if predicate(message):
                return message
            pending.append(message)

    def response(request):
        message = wait(lambda item: item.get('type') == 'response'
                       and item.get('request_seq') == request)
        assert message.get('success'), message
        return message.get('body', {})

    try:
        response(send('initialize', dict(adapterID='lldb', linesStartAt1=True,
                                        columnsStartAt1=True, pathFormat='path',
                                        supportsRunInTerminalRequest=False)))
        launch = send('launch', dict(program=str(binary), cwd=str(binary.parent)))
        wait(lambda item: item.get('event') == 'initialized')
        breakpoints = response(send('setBreakpoints', dict(source=dict(path=str(source)),
                                                          breakpoints=[dict(line=breakpoint_line)])))
        assert breakpoints['breakpoints'][0]['verified'], breakpoints
        response(send('configurationDone', {}))
        response(launch)
        stopped = wait(lambda item: item.get('event') == 'stopped')['body']
        assert stopped['reason'] == 'breakpoint', stopped
        thread_id = stopped['threadId']
        stack = response(send('stackTrace', dict(threadId=thread_id)))['stackFrames']
        assert stack[0]['line'] == breakpoint_line and len(stack) >= 2, stack
        scopes = response(send('scopes', dict(frameId=stack[0]['id'])))['scopes']
        variables = response(send('variables', dict(variablesReference=scopes[0]['variablesReference'])))
        values = {value['name']: value['value'] for value in variables['variables']}
        assert all(values.get(name) == value for name, value in expected_values.items()), values
        response(send('next', dict(threadId=thread_id)))
        assert wait(lambda item: item.get('event') == 'stopped')['body']['reason'] == 'step'
        response(send('continue', dict(threadId=thread_id)))
        assert wait(lambda item: item.get('event') == 'exited')['body']['exitCode'] == 0
        response(send('disconnect', dict(terminateDebuggee=True)))
        print('PASS: real FPC build, DAP breakpoint, stack, integer locals, step and exit 0')
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fpc', required=True)
    parser.add_argument('--lldb-dap', required=True)
    parser.add_argument('--multi-unit', action='store_true', help='Debug the separate Arithmetic unit and its caller')
    options = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='zed-delphi-debug-') as folder:
        if options.multi_unit:
            project = Path(folder) / 'project'
            shutil.copytree(root / 'examples' / 'multi_unit', project)
            source = project / 'MultiUnit.dpr'
        else:
            source = root / 'examples' / 'HelloDelphi.dpr'
        binary = Path(folder) / ('HelloDelphi.exe' if os.name == 'nt' else 'HelloDelphi')
        subprocess.run([sys.executable, str(root / 'build.py'), '--tool', 'fpc', '--project',
                        str(source), '--compiler', options.fpc, '--output', str(binary)], check=True)
        if options.multi_unit:
            verify(options.lldb_dap, binary, project / 'Arithmetic.pas', 20,
                   {'LeftValue': '20', 'RightValue': '22'})
        else:
            verify(options.lldb_dap, binary, source)


if __name__ == '__main__':
    main()
