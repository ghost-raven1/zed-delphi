"""Exercise process boundaries without requiring commercial compilers."""
import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('build', Path(__file__).parents[1] / 'build.py')
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class BuildTests(unittest.TestCase):
    def request(self, **overrides):
        return dict(tool='fpc', config='Debug', platform='Win64', **overrides)

    def test_fpc_debug_has_symbols_and_literal_paths(self):
        project = Path(tempfile.gettempdir()) / 'project with spaces' / 'App.dpr'
        argv, output = build.command_for(self.request(), project, False)
        self.assertEqual(argv[-1], str(project))
        self.assertIn('-gw3', argv)
        self.assertIn('-O-', argv)
        self.assertEqual(output, project.with_suffix(''))

    def test_fpc_cross_target_flags_and_executable_suffix(self):
        request = self.request(target_os='win64', target_cpu='x86_64')
        project = Path(tempfile.gettempdir()) / 'source' / 'App.dpr'
        argv, output = build.command_for(request, project, False)
        self.assertIn('-Twin64', argv)
        self.assertIn('-Px86_64', argv)
        self.assertEqual(output, project.with_suffix('.exe'))
        request['target_os'] = 'linux'
        _, output = build.command_for(request, project, True)
        self.assertEqual(output, project.with_suffix(''))

    def test_cross_target_identifiers_are_validated(self):
        for target in ('win64 -O2', '-X', 'win64;other', ''):
            with self.assertRaises(ValueError):
                build.command_for(self.request(target_os=target), Path('/source/App.dpr'), False)
        with self.assertRaises(ValueError):
            build.command_for(dict(tool='lazarus', config='Debug', target_cpu='aarch64'),
                              Path('/source/App.lpi'), False)

    def test_widgetset_rejects_other_compilers_and_option_injection(self):
        with self.assertRaises(ValueError):
            build.command_for(self.request(widgetset='cocoa'), Path('/source/App.dpr'), False)
        for widgetset in ('gtk2 --build-all', '-gtk2', '', 'Cocoa'):
            with self.subTest(widgetset=widgetset), self.assertRaises(ValueError):
                build.command_for(dict(tool='lazarus', config='Debug', widgetset=widgetset),
                                  Path('/source/App.lpi'), False)

    @unittest.skipIf(os.name == 'nt', 'POSIX executable fixture')
    def test_lazarus_cli_passes_widgetset_and_literal_project_to_child(self):
        with tempfile.TemporaryDirectory(prefix='Lazarus пробелы ') as folder:
            project = Path(folder) / 'Demo.lpi'
            project.touch()
            marker = Path(folder) / 'argv.json'
            compiler = Path(folder) / 'lazbuild'
            compiler.write_text('#!' + sys.executable + '\nimport json,sys\n'
                                + 'open(' + repr(str(marker)) + ',"w").write(json.dumps(sys.argv[1:]))\n')
            compiler.chmod(0o755)
            result = subprocess.run([sys.executable, str(Path(build.__file__)), '--tool', 'lazarus',
                                     '--project', str(project), '--compiler', str(compiler),
                                     '--widgetset', 'cocoa'], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(marker.read_text()),
                             ['--widgetset=cocoa', '--build-mode=Debug', str(project.resolve())])

    def test_cross_target_run_is_rejected_before_compilation(self):
        request = self.request(run=True, target_os='win64', target_cpu='x86_64')
        with self.assertRaises(ValueError):
            build.ensure_native_run(request, ('darwin', 'aarch64'))
        build.ensure_native_run(request, ('win64', 'x86_64'))
        request['run'] = False
        build.ensure_native_run(request, ('darwin', 'aarch64'))

    def test_cli_rejects_foreign_run_before_starting_compiler(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / 'App.dpr'
            project.write_text('program App; begin end.')
            target = 'win64' if build.native_target()[0] != 'win64' else 'linux'
            result = subprocess.run([sys.executable, str(Path(build.__file__)), '--tool', 'fpc',
                                     '--project', str(project), '--compiler', '/no/such/compiler',
                                     '--target-os', target, '--run'], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertIn(b'foreign FPC target', result.stderr)

    def test_delphi_properties_and_paths_remain_separate(self):
        request = dict(tool='delphi', config='Debug', platform='Win64')
        project = Path(tempfile.gettempdir()) / 'space dir' / 'App.dproj'
        argv, _ = build.command_for(request, project, True)
        self.assertEqual(argv[1], str(project))
        self.assertIn('/p:Platform=Win64', argv)
        request['config'] = 'Debug;RunSomething=true'
        with self.assertRaises(ValueError):
            build.command_for(request, Path('App.dproj'), True)

    def test_delphi_msbuild_targets_and_default(self):
        request = dict(tool='delphi', config='Debug', platform='Win64')
        for suffix in ('.dproj', '.groupproj'):
            for target in (None, 'Build', 'Clean', 'Rebuild', 'Deploy'):
                with self.subTest(suffix=suffix, target=target):
                    request['msbuild_target'] = target
                    argv, _ = build.command_for(request, Path('App' + suffix), True)
                    self.assertEqual([arg for arg in argv if arg.startswith('/t:')],
                                     ['/t:' + (target or 'Build')])

    def test_msbuild_target_rejects_invalid_json_values_and_other_tools(self):
        for target in ('', 'build', 'Build;Deploy', '/t:Clean', [], 1):
            with self.subTest(target=target), self.assertRaises(ValueError):
                build.command_for(dict(tool='delphi', config='Debug', platform='Win64',
                                       msbuild_target=target), Path('App.dproj'), True)
        for tool, suffix in (('fpc', '.dpr'), ('lazarus', '.lpi')):
            for target in ('Build', 'Clean', 'Rebuild', 'Deploy'):
                with self.subTest(tool=tool, target=target), self.assertRaises(ValueError):
                    build.command_for(dict(tool=tool, config='Debug', msbuild_target=target),
                                      Path('App' + suffix), True)

    def test_run_requires_a_compiling_msbuild_target(self):
        for target in ('Clean', 'Deploy'):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'Build or Rebuild'):
                build.command_for(dict(tool='delphi', config='Debug', platform='Win64',
                                       msbuild_target=target, run=True), Path('App.dproj'), True)
        for target in ('Build', 'Rebuild'):
            build.command_for(dict(tool='delphi', config='Debug', platform='Win64',
                                   msbuild_target=target, run=True), Path('App.dproj'), True)

    def test_cli_and_json_reject_msbuild_target_before_starting_non_delphi_compiler(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / 'App.dpr'
            project.touch()
            for use_json in (False, True):
                with self.subTest(use_json=use_json):
                    request = self.request(project=str(project), compiler='/no/such/compiler',
                                           msbuild_target='Clean')
                    args = ['--request-stdin'] if use_json else [
                        '--tool', 'fpc', '--project', str(project), '--compiler', '/no/such/compiler',
                        '--msbuild-target', 'Clean']
                    result = subprocess.run([sys.executable, str(Path(build.__file__)), *args],
                                            input=json.dumps(request).encode() if use_json else None,
                                            capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(b'applies only to Delphi MSBuild', result.stderr)

    def test_delphi_run_requires_windows_host_and_windows_target(self):
        for target in ('Linux64', 'OSX64', 'OSXARM64', 'Android64', 'iOSDevice64'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                build.ensure_native_run(dict(tool='delphi', run=True, platform=target),
                                        ('win64', 'x86_64'))
        for target in ('Win32', 'Win64'):
            request = dict(tool='delphi', run=True, platform=target)
            build.ensure_native_run(request, ('win64', 'x86_64'))
            with self.assertRaises(ValueError):
                build.ensure_native_run(request, ('darwin', 'aarch64'))
        build.ensure_native_run(dict(tool='delphi', run=False, platform='Linux64'),
                                ('win64', 'x86_64'))

    def test_cli_rejects_delphi_foreign_run_before_compiler_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / 'App.dproj'
            project.write_text('<Project />')
            for target in ('Linux64', 'OSX64', 'Android64'):
                with self.subTest(target=target):
                    result = subprocess.run([
                        sys.executable, str(Path(build.__file__)), '--tool', 'delphi',
                        '--project', str(project), '--platform', target,
                        '--compiler', '/no/such/compiler', '--program', 'App', '--run',
                    ], capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(b'Win32/Win64 target on a Windows host', result.stderr)

    def test_remote_launcher_quotes_apostrophes_and_keeps_json_out_of_shell(self):
        argv = build.remote_command('build-host', "C:\\John's Work\\build.py", 'python')
        decoded = base64.b64decode(argv[-1]).decode('utf-16le')
        self.assertEqual(decoded, "& 'python' 'C:\\John''s Work\\build.py' --request-stdin; exit $LASTEXITCODE")
        self.assertIn('-T', argv)
        with self.assertRaises(ValueError):
            build.remote_command('-oProxyCommand=bad', 'build.py', 'python')

    def test_cmd_uses_raw_outer_quotes_not_c_runtime_backslash_escaping(self):
        path = r'C:\Program Files (x86)\Embarcadero\bin\rsvars.bat'
        command = build.rsvars_command(path)
        self.assertEqual(command, f'cmd.exe /u /d /v:off /s /c "call "{path}" >nul && set"')
        self.assertNotIn('\\"', command)
        with self.assertRaises(ValueError):
            build.rsvars_command(r'C:\%EXPAND%\rsvars.bat')

    @unittest.skipUnless(os.name == 'nt', 'Windows cmd environment import')
    def test_rsvars_environment_on_real_windows_cmd(self):
        with tempfile.TemporaryDirectory(prefix='Delphi env spaces ') as folder:
            script = Path(folder) / 'rsvars.bat'
            script.write_text('@set "ZED_DELPHI_BUILD_TEST=value with spaces"\n', encoding='ascii')
            environment = build.delphi_environment(str(script))
            self.assertEqual(environment['ZED_DELPHI_BUILD_TEST'], 'value with spaces')

    def test_native_child_compiler_failure_is_returned(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / 'App.dpr'
            project.write_text('program App; begin end.')
            # Python rejects FPC flags on every host, providing a real failing child process.
            result = subprocess.run([sys.executable, str(Path(build.__file__)), '--tool', 'fpc',
                                     '--project', str(project), '--compiler', sys.executable],
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 2)

    @unittest.skipIf(os.name == 'nt', 'POSIX executable fixture')
    def test_real_child_failure_propagates_and_prevents_run(self):
        with tempfile.TemporaryDirectory(prefix='Delphi spaces ') as folder:
            root = Path(folder)
            project = root / 'App.dpr'
            project.write_text('program App; begin end.')
            marker = root / 'ran'
            output = root / 'App'
            output.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n')
            output.chmod(0o755)
            compiler = root / 'compiler'
            compiler.write_text('#!/bin/sh\nexit 17\n')
            compiler.chmod(0o755)
            request = self.request(project=str(project), compiler=str(compiler), run=True)
            self.assertEqual(build.execute(request), 17)
            self.assertFalse(marker.exists())

    @unittest.skipIf(os.name == 'nt', 'POSIX executable fixture')
    def test_success_runs_program_preserving_argument(self):
        with tempfile.TemporaryDirectory(prefix='Delphi spaces ') as folder:
            root = Path(folder)
            project = root / 'App.dpr'
            project.touch()
            marker = root / 'argv.json'
            output = root / 'App'
            program = ('#!' + sys.executable + '\nimport json,sys\n'
                       + 'open(' + repr(str(marker)) + ',"w").write(json.dumps(sys.argv[1:]))\n')
            compiler = root / 'compiler'
            compiler.write_text('#!' + sys.executable + '\nfrom pathlib import Path\n'
                                + 'output = Path(' + repr(str(output)) + ')\n'
                                + 'output.write_text(' + repr(program) + ')\noutput.chmod(0o755)\n')
            compiler.chmod(0o755)
            request = self.request(project=str(project), compiler=str(compiler),
                                   run=True, arg=['a b', '$(do-not-run)', 'quote"'])
            self.assertEqual(build.execute(request), 0)
            self.assertEqual(json.loads(marker.read_text()), request['arg'])

    def test_missing_project_is_reported_without_traceback(self):
        result = subprocess.run([sys.executable, str(Path(build.__file__)), '--tool', 'fpc',
                                 '--project', '/does/not/exist.dpr'], capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'Delphi build:', result.stderr)
        self.assertNotIn(b'Traceback', result.stderr)

    @unittest.skipIf(os.name == 'nt', 'POSIX executable fixture')
    def test_lazarus_incremental_build_can_run_existing_executable(self):
        with tempfile.TemporaryDirectory(prefix='Delphi incremental ') as folder:
            project = Path(folder) / 'App.lpi'
            project.touch()
            output = Path(folder) / 'App'
            output.write_text('#!/bin/sh\nexit 0\n')
            output.chmod(0o755)
            request = dict(tool='lazarus', config='Debug', project=str(project),
                           compiler='/usr/bin/true', program=str(output), run=True)
            self.assertEqual(build.execute(request), 0)


if __name__ == '__main__':
    unittest.main()
