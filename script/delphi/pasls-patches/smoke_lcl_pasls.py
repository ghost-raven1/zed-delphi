#!/usr/bin/env python3
"""Check a real pasls against LCL symbols and Pascal/form resource diagnostics."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from smoke_pasls import Session


def initialization_options(lazarus, project):
    paths = ('lcl', 'lcl/widgetset', 'components/lazutils', 'components/freetype',
             'packager/registration', 'lcl/interfaces', 'lcl/interfaces/cocoa')
    return {
        'checkSyntax': True, 'publishDiagnostics': True,
        'program': str(project / 'LclDemo.lpr'),
        'fpcOptions': ['-Mobjfpc', '-dLCL', '-dLCLcocoa', '-Fi' + str(lazarus / 'lcl/include')]
                      + ['-Fu' + str(lazarus / path) for path in paths],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('pasls', 'compiler', 'fpc-source', 'lazarus-source', 'fixture', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    options = parser.parse_args()
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    project = output / 'Проект LCL с пробелами'
    shutil.copytree(options.fixture.resolve(), project,
                    ignore=shutil.ignore_patterns('lib', '*.app', 'LclDemo', '*.lps'))
    source = project / 'MainForm.pas'
    resource = project / 'MainForm.lfm'
    original = source.read_text()
    original_resource = resource.read_text()
    uri = source.as_uri()
    environment = dict(os.environ, PP=str(options.compiler.resolve()),
                       FPCDIR=str(options.fpc_source.resolve()),
                       LAZARUSDIR=str(options.lazarus_source.resolve()))
    for flag, name in [('-iTO', 'FPCTARGET'), ('-iTP', 'FPCTARGETCPU')]:
        environment[name] = subprocess.check_output([str(options.compiler), flag], text=True, timeout=5).strip()
    settings = initialization_options(options.lazarus_source.resolve(), project)
    result = {'status': 'running', 'checks': [], 'initialization_options': settings}
    session = Session([str(options.pasls.resolve())], environment, 30)
    version = 1

    def position(fragment, token):
        lines = original.splitlines()
        line = next(index for index, value in enumerate(lines) if fragment in value)
        return {'line': line, 'character': lines[line].index(token) + 2}

    def request(method, location):
        return session.request(method, {'textDocument': {'uri': uri}, 'position': location})

    def diagnostics_since(start):
        return [message['params'] for message in session.notifications[start:]
                if message.get('method') == 'textDocument/publishDiagnostics']

    def save_and_check(text, expects_error):
        nonlocal version
        version += 1
        source.write_text(text)
        start = len(session.notifications)
        session.notify('textDocument/didChange', {
            'textDocument': {'uri': uri, 'version': version}, 'contentChanges': [{'text': text}],
        })
        session.notify('textDocument/didSave', {'textDocument': {'uri': uri}, 'text': text})
        # A response after didSave drains that save's diagnostic notifications.
        request('textDocument/definition', position('class(TForm)', 'TForm'))
        messages = diagnostics_since(start)
        own = [item for item in messages if item['uri'] == uri]
        assert own, messages
        assert bool(own[-1]['diagnostics']) == expects_error, messages
        if not expects_error:
            assert all(not item['diagnostics'] for item in messages), messages
        return messages

    try:
        session.request('initialize', {
            'clientInfo': {'name': 'Zed Delphi LCL acceptance', 'version': '1'},
            'processId': os.getpid(), 'rootUri': project.as_uri(),
            'workspaceFolders': [{'uri': project.as_uri(), 'name': 'LCL'}],
            'capabilities': {}, 'initializationOptions': settings,
        })
        session.notify('initialized', {})
        session.notify('textDocument/didOpen', {'textDocument': {
            'uri': uri, 'languageId': 'pascal', 'version': version, 'text': original,
        }})
        definition = request('textDocument/definition', position('class(TForm)', 'TForm'))
        assert definition and definition['uri'].endswith('/lcl/forms.pp'), definition
        handler = request('textDocument/definition',
                          position('procedure TDemoForm.CalculateButtonClick', 'CalculateButtonClick'))
        assert handler and handler['uri'] == uri and handler['range']['start']['line'] == 15, handler
        completion = request('textDocument/completion', position('CalculateButton.Click', 'CalculateButton'))
        items = completion if isinstance(completion, list) else completion['items']
        assert any('calculatebutton' in item['label'].casefold() for item in items), items
        initial = diagnostics_since(0)
        assert initial and all(not message['diagnostics'] for message in initial), initial
        result['checks'].extend(['tform-definition', 'handler-definition', 'completion', 'valid-lfm-clean'])
        result['pascal_error'] = save_and_check(original.replace('TotalValue := LeftValue + RightValue;',
                                                               'TotalValue := ;'), True)
        save_and_check(original, False)
        result['checks'].append('pascal-error-and-recovery')
        resource.write_text('object DemoForm: TDemoForm\n Invalid ???\nend\n')
        result['lfm_error'] = save_and_check(original, True)
        resource.write_text(original_resource)
        save_and_check(original, False)
        result['checks'].append('invalid-lfm-and-recovery')
        resource.unlink()
        result['missing_lfm'] = save_and_check(original, True)
        resource.write_text(original_resource)
        save_and_check(original, False)
        result['checks'].append('missing-lfm-and-recovery')
        session.request('shutdown', None)
        session.notify('exit', None)
        session.process.wait(timeout=3)
        assert session.process.returncode == 0, session.process.returncode
        result.update(status='passed', shutdown_exit_code=0, definition=definition,
                      handler=handler, completion_labels=[item['label'] for item in items])
        print('PASS: LCL definitions, completion, Pascal/LFM/missing resource diagnostics and recovery')
    except Exception as error:
        result.update(status='failed', error=str(error))
        raise
    finally:
        source.write_text(original)
        resource.write_text(original_resource)
        session.close()
        (output / 'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
        (output / 'notifications.json').write_text(json.dumps(session.notifications, indent=2) + '\n')
        (output / 'server-stderr.log').write_text('\n'.join(session.errors))


if __name__ == '__main__':
    main()
