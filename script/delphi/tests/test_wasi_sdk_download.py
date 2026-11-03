"""Verify interrupted SDK downloads cannot replace an existing installation."""

import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / 'download-wasi-sdk'


@unittest.skipUnless(shutil.which('bash') and os.name != 'nt', 'requires POSIX shell tools')
class WasiSdkDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='wasi-sdk-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.installed = self.root / 'target/wasi-sdk'
        self.installed.mkdir(parents=True)
        (self.installed / 'VERSION').write_text('33.0\n')
        (self.installed / 'keep.txt').write_text('previous SDK')
        tools = self.root / 'tools'
        tools.mkdir()
        (tools / 'uname').write_text('#!/bin/sh\ncase "$1" in -s) echo Linux;; -m) echo x86_64;; esac\n')
        (tools / 'curl').write_text('''#!/bin/sh
printf '%s\\n' "$@" > "$TEST_CURL_ARGUMENTS"
while [ "$#" -gt 0 ]; do
    if [ "$1" = --output ]; then output=$2; shift 2; else shift; fi
done
cat "$TEST_ARCHIVE" > "$output"
exit "${TEST_CURL_STATUS:-0}"
''')
        for executable in tools.iterdir():
            executable.chmod(0o755)
        self.archive = self.root / 'archive.tar.gz'
        self.arguments = self.root / 'curl-arguments.txt'
        self.environment = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'],
                                TEST_ARCHIVE=str(self.archive), TEST_CURL_ARGUMENTS=str(self.arguments))

    def make_archive(self, version='34.0', compiler=True):
        prefix = 'wasi-sdk-34.0-x86_64-linux/'
        with tarfile.open(self.archive, 'w:gz') as archive:
            for name, content in [('VERSION', version.encode() + b'\n')]:
                entry = tarfile.TarInfo(prefix + name)
                entry.size = len(content)
                archive.addfile(entry, io.BytesIO(content))
            directory = tarfile.TarInfo(prefix + 'share/wasi-sysroot')
            directory.type = tarfile.DIRTYPE
            archive.addfile(directory)
            if compiler:
                entry = tarfile.TarInfo(prefix + 'bin/clang')
                entry.mode = 0o755
                archive.addfile(entry, io.BytesIO(b''))

    def invoke(self):
        return subprocess.run(['bash', str(SCRIPT)], cwd=self.root, env=self.environment,
                              capture_output=True, text=True)

    def assert_previous_preserved(self):
        self.assertEqual((self.installed / 'VERSION').read_text(), '33.0\n')
        self.assertEqual((self.installed / 'keep.txt').read_text(), 'previous SDK')
        self.assertEqual(list((self.root / 'target').glob('wasi-sdk-install.*')), [])

    def test_partial_transfer_preserves_previous_sdk(self):
        self.archive.write_bytes(b'partial download')
        self.environment['TEST_CURL_STATUS'] = '56'
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assert_previous_preserved()
        arguments = self.arguments.read_text().splitlines()
        self.assertIn('--retry-all-errors', arguments)
        self.assertEqual(arguments[arguments.index('--retry') + 1], '3')

    def test_truncated_archive_preserves_previous_sdk(self):
        self.make_archive()
        self.archive.write_bytes(self.archive.read_bytes()[:25])
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assert_previous_preserved()

    def test_invalid_candidate_preserves_previous_sdk(self):
        for version, compiler in [('33.0', True), ('34.0', False)]:
            with self.subTest(version=version, compiler=compiler):
                self.make_archive(version, compiler)
                self.assertNotEqual(self.invoke().returncode, 0)
                self.assert_previous_preserved()

    def test_complete_archive_replaces_previous_sdk(self):
        self.make_archive()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.installed / 'VERSION').read_text(), '34.0\n')
        self.assertTrue((self.installed / 'bin/clang').is_file())
        self.assertFalse((self.installed / 'keep.txt').exists())
        self.assertEqual(list((self.root / 'target').glob('wasi-sdk-install.*')), [])

    def test_current_sdk_does_not_download(self):
        (self.installed / 'VERSION').write_text('34.0\n')
        self.assertEqual(self.invoke().returncode, 0)
        self.assertFalse(self.arguments.exists())

    def test_failed_promotion_restores_previous_sdk(self):
        self.make_archive()
        move = self.root / 'tools/mv'
        move.write_text('''#!/bin/sh
case "$1" in */wasi-sdk-34.0-x86_64-linux) exit 1;; esac
exec /bin/mv "$@"
''')
        move.chmod(0o755)
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assert_previous_preserved()


if __name__ == '__main__':
    unittest.main()
