#!/usr/bin/env python3
"""Exercise a real, locally installed pasls over stdio; no editor or mocked server is used."""

import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).parents[1]))
from dap_remote import read_message, write_message


SOURCE = '''program Smoke;

function DoubleValue(Value: Integer): Integer;
begin
  Result := Value * 2;
end;
var
  Answer: Integer;
begin
  Answer := DoubleValue(21);
  WriteLn(Answer);
end.
'''


class Session:
    """Bounded JSON-RPC exchange with a real child process and captured diagnostics."""

    def __init__(self, command, environment, timeout):
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, env=environment)
        self.timeout = timeout
        self.messages = queue.Queue()
        self.notifications = []
        self.errors = []
        self.next_id = 0

        def read_stdout():
            try:
                while (message := read_message(self.process.stdout)) is not None:
                    self.messages.put(message)
                self.messages.put(RuntimeError('pasls closed stdout'))
            except (OSError, ValueError) as error:
                self.messages.put(error)

        def read_stderr():
            for line in self.process.stderr:
                self.errors.append(line.decode('utf-8', errors='replace').rstrip())

        threading.Thread(target=read_stdout, daemon=True).start()
        threading.Thread(target=read_stderr, daemon=True).start()

    def notify(self, method, params):
        message = {'jsonrpc': '2.0', 'method': method}
        if params is not None:
            message['params'] = params
        write_message(self.process.stdin, message)

    def wait_for(self, predicate):
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('pasls response deadline exceeded')
            try:
                message = self.messages.get(timeout=remaining)
            except queue.Empty as error:
                raise TimeoutError('pasls response deadline exceeded') from error
            if isinstance(message, Exception):
                raise message
            if predicate(message):
                return message
            if 'method' in message and 'id' in message:
                raise RuntimeError(f'Unexpected server request: {message["method"]}')
            self.notifications.append(message)

    def request(self, method, params):
        self.next_id += 1
        request_id = self.next_id
        message = {'jsonrpc': '2.0', 'id': request_id, 'method': method}
        if params is not None:
            message['params'] = params
        write_message(self.process.stdin, message)
        reply = self.wait_for(lambda message: message.get('id') == request_id)
        if 'error' in reply:
            raise RuntimeError(f'{method}: {reply["error"]}')
        return reply.get('result')

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()


def smoke(binary, compiler, fpc_source, lazarus_source, timeout):
    environment = dict(os.environ, PP=str(compiler), FPCDIR=str(fpc_source),
                       LAZARUSDIR=str(lazarus_source))
    # Query the actual compiler target instead of inheriting a potentially unrelated host profile.
    for option, name in [('-iTO', 'FPCTARGET'), ('-iTP', 'FPCTARGETCPU')]:
        environment[name] = subprocess.check_output([str(compiler), option], text=True, timeout=5).strip()
    with tempfile.TemporaryDirectory(prefix='zed-delphi-lsp-smoke-') as directory:
        root = Path(directory).resolve()
        source = root / 'Smoke.dpr'
        source.write_text(SOURCE)
        uri = source.as_uri()
        session = Session([str(binary)], environment, timeout)
        try:
            result = session.request('initialize', {
                'processId': os.getpid(), 'rootUri': root.as_uri(),
                'clientInfo': {'name': 'Zed Delphi smoke', 'version': '1'},
                'workspaceFolders': [{'uri': root.as_uri(), 'name': 'Smoke'}],
                'capabilities': {'textDocument': {'completion': {'completionItem': {'snippetSupport': False}}}},
                'initializationOptions': {'fpcOptions': ['-Mdelphi'],
                                          'checkSyntax': True, 'publishDiagnostics': True},
            })
            capabilities = result['capabilities']
            assert capabilities.get('definitionProvider'), capabilities
            assert capabilities.get('completionProvider'), capabilities
            session.notify('initialized', {})
            session.notify('textDocument/didOpen', {'textDocument': {
                'uri': uri, 'languageId': 'pascal', 'version': 1, 'text': SOURCE,
            }})
            definition = session.request('textDocument/definition', {
                'textDocument': {'uri': uri}, 'position': {'line': 9, 'character': 15},
            })
            locations = definition if isinstance(definition, list) else [definition]
            assert any(location and location.get('uri') == uri
                       and location.get('range', {}).get('start', {}).get('line') == 2
                       for location in locations), definition
            completion = session.request('textDocument/completion', {
                'textDocument': {'uri': uri}, 'position': {'line': 9, 'character': 18},
            })
            items = completion if isinstance(completion, list) else completion.get('items', [])
            labels = [item['label'] for item in items]
            assert any('doublevalue' in label.casefold() for label in labels), labels
            clean_open = [message for message in session.notifications
                          if message.get('method') == 'textDocument/publishDiagnostics'
                          and message.get('params', {}).get('uri') == uri]
            assert clean_open and not clean_open[-1]['params']['diagnostics'], clean_open
            broken = SOURCE.replace('Answer := DoubleValue(21);', 'Answer := ;')
            source.write_text(broken)
            session.notify('textDocument/didChange', {
                'textDocument': {'uri': uri, 'version': 2}, 'contentChanges': [{'text': broken}],
            })
            session.notify('textDocument/didSave', {'textDocument': {'uri': uri}, 'text': broken})
            diagnostics = session.wait_for(lambda message:
                message.get('method') == 'textDocument/publishDiagnostics'
                and message.get('params', {}).get('uri') == uri
                and bool(message['params'].get('diagnostics')))['params']['diagnostics']
            source.write_text(SOURCE)
            session.notify('textDocument/didChange', {
                'textDocument': {'uri': uri, 'version': 3}, 'contentChanges': [{'text': SOURCE}],
            })
            session.notify('textDocument/didSave', {'textDocument': {'uri': uri}, 'text': SOURCE})
            session.wait_for(lambda message:
                message.get('method') == 'textDocument/publishDiagnostics'
                and message.get('params', {}).get('uri') == uri
                and message['params'].get('diagnostics') == [])
            session.request('shutdown', None)
            session.notify('exit', None)
            session.process.wait(timeout=3)
            assert session.process.returncode == 0, session.process.returncode
            return {'initialize': 'passed', 'definition': 'passed', 'completion': 'passed',
                    'diagnostics_and_recovery': 'passed', 'completion_count': len(items),
                    'diagnostic_count': len(diagnostics), 'shutdown_exit_code': 0}
        except Exception:
            print('\n'.join(session.errors[-30:]), file=sys.stderr)
            raise
        finally:
            session.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pasls', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--fpc-source', type=Path, required=True)
    parser.add_argument('--lazarus-source', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=20)
    options = parser.parse_args()
    print(json.dumps(smoke(options.pasls.resolve(), options.compiler.resolve(),
                           options.fpc_source.resolve(), options.lazarus_source.resolve(),
                           options.timeout), indent=2))


if __name__ == '__main__':
    main()
