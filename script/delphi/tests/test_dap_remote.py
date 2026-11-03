import base64
import io
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
import dap_remote


class DapTests(unittest.TestCase):
    def test_unicode_frame_roundtrip(self):
        message = {'body': {'source': {'path': '/source/Привет.pas'}}}
        stream = io.BytesIO()
        dap_remote.write_message(stream, message)
        stream.seek(0)
        self.assertEqual(dap_remote.read_message(stream), message)
        self.assertIsNone(dap_remote.read_message(stream))

    def test_both_directions_and_sibling_boundary(self):
        request = {'arguments': {'source': {'path': '/source/My Unit.pas'}, 'expression': '/source/A'}}
        mapped = dap_remote.map_message(request, '/source', 'C:\\Project')
        self.assertEqual(mapped['arguments']['source']['path'], 'C:\\Project\\My Unit.pas')
        self.assertEqual(mapped['arguments']['expression'], '/source/A')
        self.assertEqual(dap_remote.map_path('/source-other/A', '/source', 'C:\\Project'), '/source-other/A')
        self.assertEqual(dap_remote.map_path('c:\\PROJECT\\My Unit.pas', 'C:\\Project', '/source', True), '/source/My Unit.pas')

    def test_truncated_body_and_non_protocol_output_are_errors(self):
        for data in (b'Content-Length: 30\r\n\r\n{}', b'Welcome to Windows\r\n',
                     b'Content-Type: application/json\r\n',
                     b'Content-Length: 2\r\nContent-Length: 2\r\n\r\n{}'):
            with self.assertRaises(ValueError):
                dap_remote.read_message(io.BytesIO(data))

    def test_adapter_path_is_a_powershell_literal(self):
        command = dap_remote.adapter_command('builder', "C:\\John's Tools\\adapter.exe")
        script = base64.b64decode(command[-1]).decode('utf-16le')
        self.assertIn("'C:\\John''s Tools\\adapter.exe'", script)
        self.assertIn('-NoNewWindow', script)
        self.assertNotIn('Invoke-Expression', script)


if __name__ == '__main__':
    unittest.main()
