import io
import subprocess
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
import lsp_remote


class LspTests(unittest.TestCase):
    def test_initialize_and_unicode_windows_uri_round_trip(self):
        message = {'params': {
            'rootUri': 'file:///source/My%20Project',
            'rootPath': '/source/My Project',
            'workspaceFolders': [{'uri': 'file:///source/My%20Project', 'name': 'My Project'}],
            'textDocument': {'uri': 'file:///source/My%20Project/%D0%9C%D0%B8%D1%80.pas'},
        }}
        mapped = lsp_remote.map_message(message, '/source/My Project', 'C:\\Projects\\Demo')
        self.assertEqual(mapped['params']['rootUri'], 'file:///C:/Projects/Demo')
        self.assertEqual(mapped['params']['rootPath'], 'C:\\Projects\\Demo')
        self.assertEqual(mapped['params']['workspaceFolders'][0]['name'], 'My Project')
        self.assertEqual(lsp_remote.map_message(mapped, 'C:\\Projects\\Demo', '/source/My Project', True), message)
        self.assertEqual(lsp_remote.map_uri('file:///c%3A/PROJECTS/demo/Unit.pas',
                         'C:\\Projects\\Demo', '/source', True), 'file:///source/Unit.pas')

    def test_workspace_edits_locations_and_configuration(self):
        message = {'result': {
            'changes': {'file:///C:/Demo/Main.pas': [{'newText': 'file:///C:/Demo/KEEP'}]},
            'documentChanges': [{'textDocument': {'uri': 'file:///C:/Demo/Main.pas'}}],
            'targetUri': 'file:///C:/Demo/Main.pas',
            'oldUri': 'file:///C:/Demo/Old.pas',
            'newUri': 'file:///C:/Demo/New.pas',
            'message': 'C:\\Demo\\KEEP',
            'settingsFile': 'file:///C:/Demo/App.delphilsp.json',
        }}
        result = lsp_remote.map_message(message, 'C:\\Demo', '/local', True)['result']
        self.assertIn('file:///local/Main.pas', result['changes'])
        self.assertEqual(result['changes']['file:///local/Main.pas'][0]['newText'], 'file:///C:/Demo/KEEP')
        self.assertEqual(result['documentChanges'][0]['textDocument']['uri'], 'file:///local/Main.pas')
        self.assertEqual(result['targetUri'], 'file:///local/Main.pas')
        self.assertEqual(result['settingsFile'], 'file:///local/App.delphilsp.json')
        self.assertEqual(result['message'], 'C:\\Demo\\KEEP')
        self.assertEqual(result['oldUri'], 'file:///local/Old.pas')
        self.assertEqual(result['newUri'], 'file:///local/New.pas')

    def test_siblings_other_schemes_and_traversal_are_not_rewritten(self):
        for uri in ['file:///source-other/A.pas', 'file:///source/../private/A.pas',
                    'https://example.com/source/A.pas', 'untitled:Untitled-1', 'file:///SOURCE/A.pas']:
            self.assertEqual(lsp_remote.map_uri(uri, '/source', 'C:\\Demo'), uri)
        self.assertEqual(lsp_remote.map_uri('file://localhost/source/A%20B.pas', '/source', 'C:\\Demo'),
                         'file:///C:/Demo/A%20B.pas')

    def test_unc_uri_mapping(self):
        self.assertEqual(lsp_remote.map_uri('file://server/share/Project/A.pas',
                         '\\\\server\\share\\Project', '/source', True), 'file:///source/A.pas')
        self.assertEqual(lsp_remote.map_uri('file:///source/A.pas', '/source', '\\\\server\\share\\Project'),
                         'file://server/share/Project/A.pas')

    def test_framing_counts_utf8_bytes_and_rejects_truncation(self):
        message = {'method': 'textDocument/didOpen', 'params': {'text': 'Привет'}}
        stream = io.BytesIO()
        lsp_remote.write_message(stream, message)
        stream.seek(0)
        self.assertEqual(lsp_remote.read_message(stream), message)
        for frame in [b'Content-Length: 10\r\n', b'Content-Length: 5\r\n\r\n{}']:
            with self.assertRaises(ValueError):
                lsp_remote.read_message(io.BytesIO(frame))

    def test_subprocess_relay_and_exit_code(self):
        request = {'jsonrpc': '2.0', 'id': 1, 'params': {'uri': 'file:///source/A.pas'}}
        incoming, outgoing = io.BytesIO(), io.BytesIO()
        lsp_remote.write_message(incoming, request)
        incoming.seek(0)
        script = ('import sys; sys.path.insert(0, sys.argv[1]); '
                  'from dap_remote import read_message, write_message; '
                  'm=read_message(sys.stdin.buffer); '
                  'assert m["params"]["uri"]=="file:///C:/Demo/A.pas"; '
                  'write_message(sys.stdout.buffer,m)')
        command = [sys.executable, '-c', script, str(Path(__file__).parents[1])]
        self.assertEqual(lsp_remote.forward(command, '/source', 'C:\\Demo', incoming, outgoing), 0)
        outgoing.seek(0)
        self.assertEqual(lsp_remote.read_message(outgoing), request)
        self.assertEqual(lsp_remote.forward([sys.executable, '-c', 'raise SystemExit(7)'],
                         '/source', 'C:\\Demo', io.BytesIO(), io.BytesIO()), 7)

    def test_early_server_exit_with_pending_input_keeps_exit_status(self):
        incoming = io.BytesIO()
        lsp_remote.write_message(incoming, {'params': {'text': 'x' * 1024 * 1024}})
        incoming.seek(0)
        code = lsp_remote.forward([sys.executable, '-c', 'raise SystemExit(7)'],
                                 '/source', 'C:\\Demo', incoming, io.BytesIO())
        self.assertEqual(code, 7)

    def test_cli_rejects_relative_root_before_starting_ssh(self):
        result = subprocess.run([sys.executable, str(Path(lsp_remote.__file__)), '--host', 'builder',
                                 '--server', 'C:\\DelphiLSP.exe', '--local-root', 'relative',
                                 '--remote-root', 'C:\\Demo'], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'absolute local path', result.stderr)


if __name__ == '__main__':
    unittest.main()
