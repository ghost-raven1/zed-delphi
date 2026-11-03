#!/usr/bin/env python3
"""Install a verified native Zed Delphi release without replacing existing apps."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile

VERSION = "1.0.1"
BASE_URL = f"https://github.com/ghost-raven1/zed-delphi/releases/download/v{VERSION}"
PACKAGES = {
    ("Darwin", "arm64"): (
        "zed-delphi-macos-arm64-1.0.1.zip",
        "ab62b84b86c08a3c96b56409dd2c6b3cb2def8c7279ea7c735a6917f89367f2b",
        "Zed Delphi.app",
    ),
    ("Linux", "x86_64"): (
        "zed-linux-x86_64.tar.gz",
        "468d1f0ac0b1ac61abf0982006703b97dd0483479c2b78f94c08d6c568dd715d",
        "zed-dev.app",
    ),
    ("Linux", "arm64"): (
        "zed-linux-aarch64.tar.gz",
        "d5fd4f4d9d122e03df9ff7e9967450a2fdeb27a4d339d344562e580039d95e80",
        "zed-dev.app",
    ),
}


def host_package():
    """Select only published native packages; never silently use emulation."""
    machine = platform.machine().lower()
    machine = {"aarch64": "arm64", "amd64": "x86_64"}.get(machine, machine)
    key = (platform.system(), machine)
    if key not in PACKAGES:
        raise ValueError(f"Для {key[0]} {key[1]} нет проверенного пакета {VERSION}.")
    return key, PACKAGES[key]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def checked_member(name, root):
    """Keep every archive entry inside its expected application directory."""
    path = PurePosixPath(name)
    if (path.is_absolute() or ".." in path.parts or "\\" in name
            or not path.parts or path.parts[0] != root):
        raise ValueError(f"Недопустимый путь в архиве: {name}")
    return path


def unpack(archive, temporary, root, system):
    if system == "Darwin":
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                # ditto stores resource-fork metadata alongside the app.
                if member.filename.startswith("__MACOSX/"):
                    checked_member(member.filename, "__MACOSX")
                else:
                    checked_member(member.filename, root)
                if stat.S_ISLNK(member.external_attr >> 16):
                    raise ValueError("Символические ссылки в ZIP не поддерживаются.")
        subprocess.run(["/usr/bin/ditto", "-x", "-k", str(archive), str(temporary)], check=True)
        subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict",
                        str(temporary / root)], check=True)
    else:
        with tarfile.open(archive, "r:gz") as bundle:
            members = bundle.getmembers()
            for member in members:
                checked_member(member.name, root)
                if not (member.isfile() or member.isdir()):
                    raise ValueError(f"Неподдерживаемый тип файла: {member.name}")
            for member in members:
                target = temporary.joinpath(*PurePosixPath(member.name).parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.extractfile(member) as source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)
                    target.chmod(member.mode & 0o777)


def install(destination, assets_dir=None):
    """Verify before extraction and publish the complete directory in one rename."""
    (system, machine), (filename, expected, root) = host_package()
    destination = destination.expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"Папка уже существует; выберите новую: {destination}")
    if system == "Darwin" and destination.suffix != ".app":
        raise ValueError("В macOS путь установки должен оканчиваться на .app.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".zed-delphi-install-", dir=destination.parent) as folder:
        temporary = Path(folder)
        archive = temporary / filename
        if assets_dir is not None:
            shutil.copyfile(assets_dir / filename, archive)
        else:
            with urllib.request.urlopen(f"{BASE_URL}/{filename}", timeout=60) as response:
                with archive.open("xb") as output:
                    shutil.copyfileobj(response, output)
        if sha256(archive) != expected:
            raise ValueError(f"SHA256 не совпадает: {filename}. Установка отменена.")
        unpack(archive, temporary, root, system)
        executable = temporary / root / ("Contents/MacOS/zed" if system == "Darwin" else "bin/zed")
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ValueError("В пакете отсутствует исполняемый файл редактора.")
        if destination.exists() or destination.is_symlink():
            raise ValueError(f"Путь установки появился во время распаковки: {destination}")
        (temporary / root).rename(destination)
    if system == "Darwin":
        launch = ["open", "-a", str(destination)]
    else:
        launch = [str(destination / "bin/zed"), "--user-data-dir",
                  str(Path.home() / ".local/share/zed-delphi/user-data")]
    return {"version": VERSION, "platform": f"{system}-{machine}",
            "destination": str(destination), "sha256": expected, "launch": launch,
            "toolchains": "Компиляторы, LSP и отладчики устанавливаются отдельно.",
            "acceptance": "Установка не подтверждает GUI, сборку или отладку на этой машине."}


def main():
    parser = argparse.ArgumentParser(description="Установка проверенного пакета Zed Delphi 1.0.1")
    parser.add_argument("--destination", type=Path, required=True, help="Новая папка установки; в macOS — .app")
    parser.add_argument("--assets-dir", type=Path, help="Папка скачанных релизных архивов (без сети)")
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.destination, args.assets_dir), ensure_ascii=False, indent=2))
    except (ValueError, OSError, tarfile.TarError, zipfile.BadZipFile,
            subprocess.CalledProcessError) as error:
        parser.exit(1, f"Ошибка установки: {error}\n")


if __name__ == "__main__":
    main()
