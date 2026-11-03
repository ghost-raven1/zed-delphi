"""Run shared task/debug build commands from example projects in spaced paths."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


@unittest.skipUnless(shutil.which('fpc') and os.name != 'nt', 'requires native FPC and POSIX shell')
class ExampleBuildCommands(unittest.TestCase):
    def test_task_commands_also_work_as_debug_builds_with_spaces(self):
        for fixture, program in ((EXAMPLES, 'HelloDelphi'), (EXAMPLES / 'multi_unit', 'MultiUnit')):
            with self.subTest(program=program), tempfile.TemporaryDirectory(prefix='delphi task space ') as temporary:
                project = Path(temporary) / 'project with spaces'
                project.mkdir()
                for source in fixture.iterdir():
                    if source.suffix.lower() in ('.pas', '.dpr'):
                        shutil.copy2(source, project)
                tasks = json.loads((fixture / '.zed/tasks.json').read_text())
                debug = json.loads((fixture / '.zed/debug.json').read_text())
                task = next(task for task in tasks if task['label'] == debug[0]['build'])
                # Both Zed shell builders preserve a whole command when there are no args.
                self.assertFalse(task.get('args'))
                command = task['command'].replace('$ZED_WORKTREE_ROOT', str(project))
                result = subprocess.run(['/bin/sh', '-c', command], cwd=project, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                result = subprocess.run([str(project / program)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('42', result.stdout)


if __name__ == '__main__':
    unittest.main()
