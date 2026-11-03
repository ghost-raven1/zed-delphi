"""Check installation boundaries using small native-package fixtures."""

import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("install", Path(__file__).parents[1] / "install.py")
install = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(install)


class InstallTests(unittest.TestCase):
    def make_archive(self, folder, name="zed-dev.app/bin/zed", kind=tarfile.REGTYPE):
        archive = folder / "package.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.mode = 0o755
            content = b"#!/bin/sh\nexit 0\n"
            info.size = len(content) if kind == tarfile.REGTYPE else 0
            info.linkname = "../../outside" if kind == tarfile.SYMTYPE else ""
            bundle.addfile(info, io.BytesIO(content))
        return archive

    def package(self, archive, digest=None):
        return (("Linux", "x86_64"), (archive.name, digest or install.sha256(archive), "zed-dev.app"))

    def test_install_offline_to_unicode_path_preserves_existing_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            archive = self.make_archive(base)
            destination = base / "Моя IDE"
            with patch.object(install, "host_package", return_value=self.package(archive)):
                result = install.install(destination, base)
                self.assertTrue((destination / "bin/zed").is_file())
                self.assertIn("--user-data-dir", result["launch"])
                with self.assertRaisesRegex(ValueError, "уже существует"):
                    install.install(destination, base)
                self.assertEqual((destination / "bin/zed").read_bytes(), b"#!/bin/sh\nexit 0\n")
            self.assertFalse(list(base.glob(".zed-delphi-install-*")))

    def test_corrupt_archive_never_installs(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            archive = self.make_archive(base)
            with patch.object(install, "host_package", return_value=self.package(archive, "0" * 64)):
                with self.assertRaisesRegex(ValueError, "SHA256"):
                    install.install(base / "app", base)
            self.assertFalse((base / "app").exists())
            self.assertFalse(list(base.glob(".zed-delphi-install-*")))

    def test_rejects_archive_escape_links_and_missing_executable(self):
        for name, kind in (("zed-dev.app/../../outside", tarfile.REGTYPE),
                           ("/tmp/outside", tarfile.REGTYPE),
                           ("zed-dev.app/link", tarfile.SYMTYPE),
                           ("zed-dev.app/readme", tarfile.REGTYPE)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                base = Path(folder)
                archive = self.make_archive(base, name, kind)
                with patch.object(install, "host_package", return_value=self.package(archive)):
                    with self.assertRaises(ValueError):
                        install.install(base / "app", base)
                self.assertFalse((base / "app").exists())
                self.assertFalse((base / "outside").exists())

    def test_platform_selection_and_unsupported_windows(self):
        with patch.object(install.platform, "system", return_value="Linux"), \
                patch.object(install.platform, "machine", return_value="aarch64"):
            self.assertEqual(install.host_package()[0], ("Linux", "arm64"))
        with patch.object(install.platform, "system", return_value="Windows"), \
                patch.object(install.platform, "machine", return_value="AMD64"):
            with self.assertRaisesRegex(ValueError, "нет проверенного пакета"):
                install.host_package()


if __name__ == "__main__":
    unittest.main()
