#!/usr/bin/env python3
"""Forward DAP over Windows OpenSSH, mapping one synchronized source root."""

import argparse
import base64
import json
import subprocess
import sys
import threading

from build import checked_text, remote_command


def map_path(value, source, destination, windows=False):
    """Map only the configured root or its descendants, never matching sibling prefixes."""
    if not isinstance(value, str):
        return value
    normalized = value.replace('\\', '/')
    root = source.replace('\\', '/').rstrip('/')
    compared = normalized.casefold() if windows else normalized
    compared_root = root.casefold() if windows else root
    if compared == compared_root or compared.startswith(compared_root + '/'):
        suffix = normalized[len(root):]
        mapped = destination.rstrip('/\\') + suffix
        return mapped.replace('/', '\\') if '\\' in destination else mapped
    return value


def map_message(value, source, destination, windows=False):
    """Translate DAP source paths and explicit launch paths, leaving values/expressions intact."""
    if isinstance(value, list):
        return [map_message(item, source, destination, windows) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in ('path', 'program', 'cwd', 'sourceRoot', 'mapFile', 'rsmFile', 'delphiProjectFile'):
            result[key] = map_path(item, source, destination, windows)
        elif key == 'sourceSearchPaths' and isinstance(item, list):
            result[key] = [map_path(path, source, destination, windows) for path in item]
        else:
            result[key] = map_message(item, source, destination, windows)
    return result


def read_message(stream):
    """Read one byte-counted DAP frame, including fragmented reads and Unicode bodies."""
    length = None
    saw_header = False
    while True:
        line = stream.readline(8193)
        if not line:
            if not saw_header:
                return None
            raise ValueError('Unexpected EOF in DAP headers')
        if len(line) > 8192:
            raise ValueError('DAP header too long')
        if line in (b'\r\n', b'\n'):
            break
        key, separator, value = line.partition(b':')
        if not separator:
            raise ValueError('Non-DAP output received on adapter stdout')
        saw_header = True
        if key.lower() == b'content-length':
            if length is not None:
                raise ValueError('Duplicate DAP Content-Length')
            length = int(value.strip())
    if length is None or not 0 <= length <= 16 * 1024 * 1024:
        raise ValueError('Invalid DAP Content-Length')
    body = bytearray()
    while len(body) < length:
        chunk = stream.read(length - len(body))
        if not chunk:
            raise ValueError('Unexpected EOF in DAP body')
        body.extend(chunk)
    return json.loads(body)


def write_message(stream, message):
    body = json.dumps(message, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    stream.write(f'Content-Length: {len(body)}\r\n\r\n'.encode('ascii') + body)
    stream.flush()


def adapter_command(host, adapter):
    checked_text(adapter, 'adapter')
    # Reuse host validation; Start-Process inherits raw stdio instead of PowerShell's text pipeline.
    command = remote_command(host, 'unused', 'unused')
    literal = "'" + adapter.replace("'", "''") + "'"
    script = (f"$ErrorActionPreference = 'Stop'; $p = Start-Process -FilePath {literal} -NoNewWindow -PassThru -Wait; "
              "if ($null -eq $p) { exit 1 }; exit $p.ExitCode")
    command[-1] = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    return command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--adapter', required=True)
    parser.add_argument('--local-root', required=True)
    parser.add_argument('--remote-root', required=True)
    options = parser.parse_args()
    process = None
    errors = []
    try:
        process = subprocess.Popen(adapter_command(options.host, options.adapter),
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        def forward_requests():
            try:
                while (message := read_message(sys.stdin.buffer)) is not None:
                    write_message(process.stdin, map_message(message, options.local_root,
                                                            options.remote_root))
                process.stdin.close()
            except (OSError, ValueError) as error:
                errors.append(error)
                process.terminate()

        threading.Thread(target=forward_requests, daemon=True).start()
        while (message := read_message(process.stdout)) is not None:
            write_message(sys.stdout.buffer, map_message(message, options.remote_root,
                                                         options.local_root, windows=True))
        code = process.wait()
        if errors:
            raise ValueError(str(errors[0]))
        return code
    except (OSError, ValueError) as error:
        print(f'Delphi DAP transport: {error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    sys.exit(main())
