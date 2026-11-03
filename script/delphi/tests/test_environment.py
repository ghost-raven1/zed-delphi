"""Exercise discovery boundaries, bounded probes, and Windows installation metadata."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('delphi_environment', Path(__file__).parents[1] / 'environment.py')
environment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(environment)


class EnvironmentTests(unittest.TestCase):
    def test_explicit_empty_path_does_not_select_an_installed_tool_or_delphi_root(self):
        result = environment.locate('python', '', [Path(sys.executable)], ['--version'])
        self.assertEqual(result['status'], 'missing')
        self.assertEqual(result['path'], '')
        self.assertEqual(result['source'], 'explicit')
        with patch.object(environment, 'windows_delphi_registry_roots', side_effect=AssertionError('fallback')):
            delphi = environment.inspect_delphi('Windows', {'delphi_root': ''})
        self.assertEqual(delphi['status'], 'missing')
        self.assertEqual(delphi['source'], 'explicit')

    def test_explicit_missing_path_does_not_fall_back_to_path_or_known_install(self):
        with tempfile.TemporaryDirectory() as folder:
            installed = Path(folder) / 'installed'
            installed.write_text('exists')
            missing = Path(folder) / 'not installed'
            result = environment.locate('fpc', str(missing), [installed], ['-iV'])
            self.assertEqual(result['status'], 'missing')
            self.assertEqual(result['source'], 'explicit')
            self.assertEqual(result['path'], str(missing))

    @unittest.skipIf(os.name == 'nt', 'POSIX executable permission contract')
    def test_non_executable_file_is_reported_without_launch(self):
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder) / 'fpc'
            binary.write_text('not executable')
            result = environment.locate('fpc', str(binary), version_arguments=['-iV'])
            self.assertEqual(result['status'], 'not_executable')
            self.assertEqual(result['version_probe']['status'], 'not_probed')

    def test_real_version_query_keeps_arguments_literal_and_does_not_echo_output(self):
        with tempfile.TemporaryDirectory(prefix='Delphi doctor spaces ') as folder:
            script = Path(folder) / 'version.py'
            marker = Path(folder) / 'arguments.json'
            script.write_text('import json,sys\n'
                              + 'open(' + repr(str(marker)) + ',"w").write(json.dumps(sys.argv[1:]))\n'
                              + 'print("PRIVATE_TEST_VALUE compiler 3.2.2")\n')
            literal = 'space $(not-a-command) & literal'
            result = environment.version_probe(sys.executable, [str(script), literal])
            self.assertEqual(result['version'], '3.2.2')
            self.assertEqual(json.loads(marker.read_text()), [literal])
            self.assertNotIn('PRIVATE_TEST_VALUE', json.dumps(result))

    def test_real_timeout_and_failure_are_inventory_results_not_tracebacks(self):
        timeout = environment.version_probe(sys.executable, ['-c', 'import time; time.sleep(10)'], timeout=0.1)
        self.assertEqual(timeout['status'], 'timeout')
        failed = environment.version_probe(sys.executable, ['-c', 'print("SECRET"); raise SystemExit(17)'])
        self.assertEqual(failed, {'status': 'failed', 'version': None, 'exit_code': 17})

    def test_protocol_servers_are_not_started_to_discover_versions(self):
        with patch.object(environment.subprocess, 'run', side_effect=AssertionError('unexpected process')):
            self.assertEqual(environment.version_probe('pasls', None)['status'], 'not_probed')
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder) / 'extension'
                (root / 'adapter').mkdir(parents=True)
                binary = root / 'adapter/codelldb'
                binary.touch()
                manifest = root / 'package.json'
                manifest.write_text(json.dumps({'name': 'vscode-lldb', 'publisher': 'vadimcn', 'version': '1.12.3'}))
                result = environment.codelldb_version(binary)
                self.assertEqual(result['status'], 'manifest')
                self.assertEqual(result['version'], '1.12.3')
                manifest.write_text('{broken json')
                self.assertEqual(environment.codelldb_version(binary)['status'], 'not_probed')

    def test_windows_bds20_inventory_never_executes_license_or_gui_programs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'Studio 20.0'
            binaries = root / 'bin'
            binaries.mkdir(parents=True)
            for filename in ('bds.exe', 'dcc32.exe', 'dcc64.exe', 'rsvars.bat',
                             'CodeGear.Delphi.Targets', 'MSBuild.exe'):
                path = binaries / filename
                path.write_text('must not be executed')
                path.chmod(0o755)
            with patch.object(environment.subprocess, 'run', side_effect=AssertionError('unexpected process')):
                result = environment.inspect_delphi('Windows', {'delphi_root': str(root),
                                                                'msbuild': str(binaries / 'MSBuild.exe')})
            self.assertEqual(result['status'], 'found')
            self.assertFalse(result['version_verified'])
            self.assertFalse(result['license_checked'])
            self.assertEqual(result['acceptance'], 'not_performed')
            self.assertTrue(all(item['status'] == 'found' for item in result['files'].values()))
            (binaries / 'dcc64.exe').unlink()
            partial = environment.inspect_delphi('Windows', {'delphi_root': str(root),
                                                              'msbuild': str(binaries / 'MSBuild.exe')})
            self.assertEqual(partial['status'], 'partial')

    def test_registry_candidate_and_bds20_directory_are_distinct_from_other_versions(self):
        with tempfile.TemporaryDirectory() as folder:
            custom = Path(folder) / 'Custom Delphi'
            custom.mkdir()
            newer = Path(folder) / '23.0'
            newer.mkdir()
            with patch.dict(os.environ, {'BDS': str(newer)}, clear=True), \
                    patch.object(environment, 'windows_delphi_registry_roots', return_value=[custom]):
                result = environment.inspect_delphi('Windows', {})
            self.assertEqual(result['root'], str(custom))
            self.assertEqual(result['source'], 'registry_bds_20')
            with patch.dict(os.environ, {'BDS': str(newer)}, clear=True), \
                    patch.object(environment, 'windows_delphi_registry_roots', return_value=[]):
                self.assertEqual(environment.inspect_delphi('Windows', {})['status'], 'missing')

    def test_cli_json_reports_missing_tools_without_claiming_acceptance_or_dumping_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            missing = str(Path(folder) / 'missing tool')
            command = [sys.executable, str(Path(environment.__file__)), 'doctor', '--json']
            for tool in ('fpc', 'lazbuild', 'pasls', 'codelldb'):
                command.extend(['--' + tool, missing])
            result = subprocess.run(command, check=True, capture_output=True, text=True,
                                    env=dict(os.environ, DOCTOR_TEST_SECRET='NOT_FOR_OUTPUT'), timeout=10)
            report = json.loads(result.stdout)
            self.assertEqual(report['schema_version'], 1)
            self.assertEqual(report['missing_tools'], ['fpc', 'lazbuild', 'pasls', 'codelldb'])
            self.assertEqual(report['acceptance'], 'not_performed')
            self.assertNotIn('NOT_FOR_OUTPUT', result.stdout + result.stderr)
            self.assertIn('не проверялись', environment.human_report(report))


if __name__ == '__main__':
    unittest.main()
