#!/usr/bin/env python3
"""Package an existing ARM64 CI executable as a locally signed macOS app."""
import argparse
import hashlib
import json
import platform
import plistlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESOURCES = ROOT / "crates/zed/resources"
REQUIRED = ("zed", "provenance.json", "LICENSE-GPL", "LICENSE-APACHE", "licenses.md")
PERMISSIONS_RU = {
    "NSSystemAdministrationUsageDescription": "Программе в Zed Delphi требуются повышенные права для выполнения операции.",
    "NSAppleEventsUsageDescription": "Программе в Zed Delphi требуется доступ к AppleScript.",
    "NSBluetoothAlwaysUsageDescription": "Программе в Zed Delphi требуется доступ к Bluetooth.",
    "NSCalendarsUsageDescription": "Программе в Zed Delphi требуется доступ к календарям.",
    "NSCameraUsageDescription": "Программе в Zed Delphi требуется доступ к камере.",
    "NSContactsUsageDescription": "Программе в Zed Delphi требуется доступ к контактам.",
    "NSLocationAlwaysUsageDescription": "Программе в Zed Delphi требуется доступ к местоположению, в том числе в фоне.",
    "NSLocationUsageDescription": "Программе в Zed Delphi требуется доступ к местоположению.",
    "NSLocationWhenInUseUsageDescription": "Программе в Zed Delphi требуется доступ к местоположению во время работы.",
    "NSMicrophoneUsageDescription": "Программе в Zed Delphi требуется доступ к микрофону.",
    "NSSpeechRecognitionUsageDescription": "Программе в Zed Delphi требуется распознавание речи.",
    "NSRemindersUsageDescription": "Программе в Zed Delphi требуется доступ к напоминаниям.",
}


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def info_plist(minimum_os):
    info = {}
    for fragment in sorted((RESOURCES / "info").glob("*.plist")):
        xml = '<plist version="1.0"><dict>' + fragment.read_text() + "</dict></plist>"
        info.update(plistlib.loads(xml.encode()))
    info.update(PERMISSIONS_RU)
    info.update({
        "CFBundleIdentifier": "dev.zed.Zed-Delphi",
        "CFBundleName": "Zed Delphi",
        "CFBundleDisplayName": "Zed Delphi",
        "CFBundleExecutable": "zed",
        "CFBundlePackageType": "APPL",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleShortVersionString": "1.0.1",
        "CFBundleVersion": "1.0.1",
        "CFBundleIconFile": "AppIcon",
        "CFBundleDevelopmentRegion": "ru",
        "LSApplicationCategoryType": "public.app-category.developer-tools",
        "LSMinimumSystemVersion": minimum_os,
        "NSHighResolutionCapable": True,
    })
    # Advertise document support without claiming default ownership or zed:// URLs.
    info.pop("CFBundleURLTypes", None)
    for document in info.get("CFBundleDocumentTypes", []):
        document["LSHandlerRank"] = "Alternate"
        if "CFBundleTypeName" in document:
            document["CFBundleTypeName"] = "Текстовый документ Zed Delphi"
    return info


def package(source, output):
    if platform.system() != "Darwin":
        raise ValueError("Упаковка выполняется только в macOS.")
    if output.suffix != ".app" or output.exists() or output.is_symlink():
        raise ValueError("Укажите новый, ещё не существующий путь с расширением .app.")
    for name in REQUIRED + ("SHA256SUMS",):
        if not (source / name).is_file() or (source / name).is_symlink():
            raise ValueError(f"Отсутствует обычный файл артефакта: {name}")
    checksums = {}
    for line in (source / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        checksums[name] = digest
    for name in REQUIRED:
        if sha256(source / name) != checksums.get(name):
            raise ValueError(f"Не совпадает SHA256: {name}")
    provenance = json.loads((source / "provenance.json").read_text())
    if provenance.get("platform") != "macos-arm64":
        raise ValueError("Ожидался CI-артефакт macos-arm64.")
    binary = source / "zed"
    file_info = run("/usr/bin/file", "-b", str(binary))
    architectures = run("/usr/bin/lipo", "-archs", str(binary)).split()
    if "Mach-O" not in file_info or architectures != ["arm64"]:
        raise ValueError(f"Ожидался Mach-O arm64: {file_info}; {architectures}")
    libraries_output = run("/usr/bin/otool", "-L", str(binary))
    libraries = [line.strip().split(" (", 1)[0] for line in libraries_output.splitlines()[1:] if line.strip()]
    external = [name for name in libraries if not name.startswith(("/usr/lib/", "/System/Library/"))]
    if external:
        raise ValueError("Найдены неупакованные несистемные библиотеки; переносимость не подтверждена: " + ", ".join(external))
    load_commands = run("/usr/bin/otool", "-l", str(binary))
    versions = re.findall(r"\bminos\s+(\d+(?:\.\d+)*)", load_commands)
    if not versions:
        versions = re.findall(r"cmd LC_VERSION_MIN_MACOSX\s+cmdsize \d+\s+version (\d+(?:\.\d+)*)", load_commands)
    if not versions:
        raise ValueError("Не удалось определить минимальную версию macOS из Mach-O.")
    minimum_os = max(versions, key=lambda value: tuple(map(int, value.split("."))))
    # mkdir is exclusive: never overwrite an existing installation.
    output.mkdir(parents=False, exist_ok=False)
    try:
        contents = output / "Contents"
        macos = contents / "MacOS"
        resources = contents / "Resources"
        macos.mkdir(parents=True)
        resources.mkdir()
        executable = macos / "zed"
        shutil.copy2(binary, executable)
        executable.chmod(0o755)
        for name in REQUIRED[1:]:
            shutil.copy2(source / name, resources / name)
        shutil.copy2(source / "SHA256SUMS", resources / "SOURCE-SHA256SUMS")
        shutil.copy2(RESOURCES / "Document.icns", resources / "Document.icns")
        with tempfile.TemporaryDirectory(prefix="zed-delphi-icons-") as temporary:
            iconset = Path(temporary) / "AppIcon.iconset"
            iconset.mkdir()
            for size in (16, 32, 128, 256, 512):
                for scale in (1, 2):
                    suffix = "@2x" if scale == 2 else ""
                    run("/usr/bin/sips", "-z", str(size * scale), str(size * scale),
                        str(RESOURCES / "app-icon-dev@2x.png"), "--out",
                        str(iconset / f"icon_{size}x{size}{suffix}.png"))
            run("/usr/bin/iconutil", "-c", "icns", str(iconset), "-o", str(resources / "AppIcon.icns"))
        with (contents / "Info.plist").open("wb") as stream:
            plistlib.dump(info_plist(minimum_os), stream)
        entitlements = plistlib.loads((RESOURCES / "zed.entitlements").read_bytes())
        entitlements.pop("com.apple.developer.associated-domains", None)
        entitlement_path = resources / "zed.entitlements"
        entitlement_path.write_bytes(plistlib.dumps(entitlements))
        report = {
            "source_commit": provenance.get("commit"),
            "source_sha256": sha256(binary),
            "architectures": architectures,
            "file": file_info,
            "minimum_macos": minimum_os,
            "linked_libraries": libraries,
            "non_system_libraries": external,
            "signature": "ad-hoc; not Developer ID; not notarized",
            "gui_acceptance": "not performed by this script",
            "compiler_lsp_debugger": "external; not bundled",
        }
        (resources / "packaging.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        run("/usr/bin/codesign", "--force", "--sign", "-", "--entitlements", str(entitlement_path), str(output))
        run("/usr/bin/codesign", "--verify", "--deep", "--strict", str(output))
        print(json.dumps({"bundle": str(output), **report}, ensure_ascii=False, indent=2))
    except BaseException:
        shutil.rmtree(output)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True, help="Каталог zed-delphi из нативного CI-архива")
    parser.add_argument("--output", type=Path, required=True, help="Новый путь Zed Delphi.app (родительская папка должна существовать)")
    args = parser.parse_args()
    try:
        package(args.source_dir.absolute(), args.output.absolute())
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Ошибка упаковки: {error}\n")


if __name__ == "__main__":
    main()
