"""A failed bundle replacement must preserve the last working application."""
import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    'lcl_package', Path(__file__).resolve().parents[1] / 'examples/lcl_demo/package_macos.py')
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


class BundleRecoveryTests(unittest.TestCase):
    def test_promotion_and_rollback_failures_preserve_previous_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / 'LclDemo').write_bytes(b'new executable')
            output = project / 'LclDemo.app'
            contents = output / 'Contents'
            contents.mkdir(parents=True)
            (contents / 'Info.plist').write_bytes(plistlib.dumps({
                'CFBundleIdentifier': package.BUNDLE_ID}))
            (contents / 'previous-data').write_bytes(b'last working build')
            rename = Path.rename

            def fail_restore_and_promotion(source, target):
                if Path(target) == output:
                    raise OSError('injected filesystem failure')
                return rename(source, target)

            with patch.object(package.sys, 'platform', 'darwin'), \
                    patch.object(package.subprocess, 'check_output', return_value='Mach-O'), \
                    patch.object(package.subprocess, 'run'), \
                    patch.object(Path, 'rename', fail_restore_and_promotion):
                with self.assertRaisesRegex(OSError, 'предыдущая сборка сохранена'):
                    package.package(project)
            backup = project / '.LclDemo.previous.app'
            self.assertEqual((backup / 'Contents/previous-data').read_bytes(), b'last working build')
            self.assertFalse(output.exists())
            self.assertEqual(list(project.glob('.lcl-macos-*')), [])
            with patch.object(package.sys, 'platform', 'darwin'):
                with self.assertRaisesRegex(ValueError, 'Сохранена предыдущая сборка'):
                    package.package(project)
            self.assertTrue(backup.exists())


if __name__ == '__main__':
    unittest.main()
