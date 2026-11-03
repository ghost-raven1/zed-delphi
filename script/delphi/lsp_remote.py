#!/usr/bin/env python3
"""Forward LSP to a Windows OpenSSH host with one explicitly synchronized source root."""

import argparse
import posixpath
import re
import subprocess
import sys
import threading
from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from dap_remote import adapter_command, read_message, write_message


URI_FIELDS = frozenset(('uri', 'rootUri', 'targetUri', 'oldUri', 'newUri',
                        'documentUri', 'scopeUri', 'settingsFile'))


def _mapped_path(value, source, destination, windows=False):
    """Match complete normalized roots, respecting the source filesystem's case rules."""
    if not isinstance(value, str):
        return None
    path = posixpath.normpath(value.replace('\\', '/'))
    root = posixpath.normpath(source.replace('\\', '/')).rstrip('/')
    compared = path.casefold() if windows else path
    compared_root = root.casefold() if windows else root
    if compared != compared_root and not compared.startswith(compared_root + '/'):
        return None
    return destination.replace('\\', '/').rstrip('/') + path[len(root):]


def map_uri(value, source, destination, windows=False):
    """Map file URIs only; preserve non-file schemes and URIs outside the source root."""
    if not isinstance(value, str):
        return value
    uri = urlsplit(value)
    if uri.scheme.lower() != 'file':
        return value
    path = unquote(uri.path)
    if uri.netloc and uri.netloc.lower() != 'localhost':
        path = '//' + unquote(uri.netloc) + path
    elif windows and re.match(r'^/[A-Za-z]:/', path):
        path = path[1:]
    mapped = _mapped_path(path, source, destination, windows)
    if mapped is None:
        return value
    if mapped.startswith('//'):
        authority, _, path = mapped[2:].partition('/')
        return urlunsplit(('file', authority, quote('/' + path, safe='/:'), uri.query, uri.fragment))
    if not mapped.startswith('/'):
        mapped = '/' + mapped
    return urlunsplit(('file', '', quote(mapped, safe='/:'), uri.query, uri.fragment))


def map_message(value, source, destination, windows=False):
    """Translate standard LSP locations without rewriting code, diagnostics, or edit text."""
    if isinstance(value, list):
        return [map_message(item, source, destination, windows) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in URI_FIELDS:
            result[key] = map_uri(item, source, destination, windows)
        elif key == 'rootPath':
            mapped = _mapped_path(item, source, destination, windows)
            result[key] = mapped.replace('/', '\\') if mapped and '\\' in destination else mapped or item
        elif key == 'changes' and isinstance(item, dict):
            result[key] = {
                map_uri(uri, source, destination, windows): map_message(edits, source, destination, windows)
                for uri, edits in item.items()
            }
        else:
            result[key] = map_message(item, source, destination, windows)
    return result


def forward(command, local_root, remote_root, input_stream, output_stream):
    """Relay byte-framed stdio and preserve the remote process exit status."""
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    errors = []

    def forward_requests():
        try:
            while (message := read_message(input_stream)) is not None:
                write_message(process.stdin, map_message(message, local_root, remote_root))
            process.stdin.close()
        except (OSError, ValueError) as error:
            errors.append(error)
            if process.poll() is None:
                process.terminate()

    threading.Thread(target=forward_requests, daemon=True).start()
    try:
        while (message := read_message(process.stdout)) is not None:
            write_message(output_stream, map_message(message, remote_root, local_root, windows=True))
        code = process.wait()
        if code:
            return code
        if errors:
            raise ValueError(str(errors[0]))
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        process.stdout.close()
        try:
            process.stdin.close()
        except BrokenPipeError:
            # The server may exit before consuming the final client frame.
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--server', required=True, help='Full Windows path to DelphiLSP.exe')
    parser.add_argument('--local-root', required=True)
    parser.add_argument('--remote-root', required=True)
    options = parser.parse_args()
    try:
        if not PurePosixPath(options.local_root).is_absolute():
            raise ValueError('--local-root must be an absolute local path')
        if not PureWindowsPath(options.remote_root).is_absolute():
            raise ValueError('--remote-root must be an absolute Windows path')
        command = adapter_command(options.host, options.server)
        return forward(command, options.local_root, options.remote_root,
                       sys.stdin.buffer, sys.stdout.buffer)
    except (OSError, ValueError) as error:
        print(f'Delphi LSP transport: {error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    sys.exit(main())
