"""Fast resource and missing-library boundary checks; never invoke Cargo."""
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('linux_build', Path(__file__).with_name('build.py'))
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class BuildBoundaries(unittest.TestCase):
    @patch.object(build.platform, 'system', return_value='Linux')
    @patch.object(build.platform, 'machine', return_value='x86_64')
    @patch.object(build.shutil, 'disk_usage', return_value=SimpleNamespace(free=5 * build.GIB))
    def test_low_disk_stops_before_memory_or_tools(self, *_):
        with patch.object(build, 'available_memory') as memory:
            with self.assertRaisesRegex(RuntimeError, 'require 30'):
                build.preflight(Path('/tmp/target'), Path('/tmp/output'), 30, 8)
            memory.assert_not_called()

    @patch.object(build.platform, 'system', return_value='Linux')
    @patch.object(build.platform, 'machine', return_value='x86_64')
    @patch.object(build.shutil, 'disk_usage', return_value=SimpleNamespace(free=100 * build.GIB))
    @patch.object(build, 'available_memory', return_value=3 * build.GIB)
    def test_container_memory_limit_stops_build(self, *_):
        with self.assertRaisesRegex(RuntimeError, 'require 8'):
            build.preflight(Path('/tmp/target'), Path('/tmp/output'), 30, 8)

    def test_reclaimable_cache_with_cgroup_and_host_ceiling(self):
        for version in (1, 2):
            for host_gib, inactive_gib, expected_gib in ((8, 4, 5), (3, 4, 3), (8, 7, 6)):
                with self.subTest(version=version, host_gib=host_gib, inactive_gib=inactive_gib):
                    files = {'/proc/meminfo': f'MemAvailable: {host_gib * build.GIB // 1024} kB\n'}
                    if version == 2:
                        files.update({'/sys/fs/cgroup/memory.max': str(6 * build.GIB),
                                      '/sys/fs/cgroup/memory.current': str(5 * build.GIB),
                                      '/sys/fs/cgroup/memory.stat': f'inactive_file {inactive_gib * build.GIB}\n'})
                    else:
                        files.update({'/sys/fs/cgroup/memory/memory.limit_in_bytes': str(6 * build.GIB),
                                      '/sys/fs/cgroup/memory/memory.usage_in_bytes': str(5 * build.GIB),
                                      '/sys/fs/cgroup/memory/memory.stat': f'total_inactive_file {inactive_gib * build.GIB}\n'})
                    def read(path, *args, **kwargs):
                        if str(path) not in files:
                            raise FileNotFoundError(str(path))
                        return files[str(path)]
                    with patch.object(Path, 'read_text', read):
                        self.assertEqual(build.available_memory(), expected_gib * build.GIB)

    def test_unresolved_library_fails_even_when_ldd_exits_zero(self):
        result = SimpleNamespace(returncode=0, stdout='libbad.so => not found\n', stderr='')
        with patch.object(build.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(RuntimeError, 'unresolved'):
                build.check_dynamic_libraries(Path('/bundle/libexec/zed-editor'), io.StringIO())

    def test_ldd_failure_is_not_accepted_as_empty_dependency_list(self):
        result = SimpleNamespace(returncode=1, stdout='', stderr='broken ELF')
        with patch.object(build.subprocess, 'run', return_value=result):
            with self.assertRaises(RuntimeError):
                build.check_dynamic_libraries(Path('/bundle/bin/zed'), io.StringIO())


if __name__ == '__main__':
    unittest.main()
