"""Real FPC regression tests; skipped when the compiler is not installed."""

from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


class FpcArtifactTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('fpc'), 'Free Pascal compiler is not installed')
    def test_successful_unit_compile_does_not_run_existing_executable(self):
        helper = Path(__file__).parents[1] / 'build.py'
        with tempfile.TemporaryDirectory(prefix='Delphi stale artifact ') as folder:
            root = Path(folder)
            output = root / ('App.exe' if os.name == 'nt' else 'App')
            marker = root / 'stale-was-run'
            program = root / 'OldProgram.dpr'
            marker_literal = str(marker).replace("'", "''")
            program.write_text(
                "program OldProgram; var Marker: Text; begin "
                f"Assign(Marker, '{marker_literal}'); Rewrite(Marker); "
                "WriteLn(Marker, 'stale'); Close(Marker); end."
            )
            command = [sys.executable, str(helper), '--tool', 'fpc', '--compiler',
                       shutil.which('fpc'), '--output', str(output)]
            built = subprocess.run([*command, '--project', str(program)],
                                   capture_output=True, timeout=30)
            self.assertEqual(built.returncode, 0, built.stdout.decode(errors='replace')
                             + built.stderr.decode(errors='replace'))
            rebuilt = subprocess.run([*command, '--project', str(program), '--run'],
                                     capture_output=True, timeout=30)
            self.assertEqual(rebuilt.returncode, 0, rebuilt.stderr.decode(errors='replace'))
            self.assertTrue(marker.exists(), 'A successfully rebuilt program must still run')
            marker.unlink()
            original = output.read_bytes()
            unit = root / 'AUnit.pas'
            unit.write_text('unit AUnit; interface implementation end.')
            compiled = subprocess.run([*command, '--project', str(unit), '--run'],
                                      capture_output=True, timeout=30)
            self.assertEqual(compiled.returncode, 1,
                             compiled.stdout.decode(errors='replace') + compiled.stderr.decode(errors='replace'))
            self.assertIn(b'did not create or update', compiled.stderr)
            self.assertFalse(marker.exists(), 'The stale executable was launched')
            self.assertEqual(output.read_bytes(), original, 'The original executable must be preserved')


if __name__ == '__main__':
    unittest.main()
