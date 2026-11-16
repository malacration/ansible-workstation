#!/usr/bin/env python3
"""Inspect managed herdr state without executing it or following file symlinks.

Modes:
  default                 Print {"valid": bool, "receipt": {...}, "reason": str}.
                          A receipt is reported as valid only when the managed
                          executable is a regular, executable, nonsymlink file
                          whose SHA256 matches the receipt.
  --prepare-publication   Rename nonregular destinations (symlinks, FIFOs,
                          directories) out of the way before Ansible publishes
                          regular files there. Targets are never followed.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid


HASH = re.compile(r'^[a-f0-9]{64}$')
VERSION = re.compile(r'^[0-9]+\.[0-9]+\.[0-9]+$')
# Receipts contain metadata only; anything larger is not ours.
MAX_RECEIPT_BYTES = 65536


def check_parents(paths):
    """Refuse linked or non-directory ancestors, including dangling links."""
    for path in paths:
        for parent in path.parents:
            try:
                mode = parent.lstat().st_mode
            except FileNotFoundError:
                continue
            if not stat.S_ISDIR(mode):
                raise ValueError('herdr managed paths require nonsymlink directory ancestors')


def regular_reader(path):
    """Open only a regular nonsymlink file, avoiding FIFO reads and link targets."""
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode):
        raise ValueError('Managed herdr file is not a regular nonsymlink file')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError('Managed herdr file changed type during inspection')
    return os.fdopen(descriptor, 'rb')


def inspect(install_dir, architecture, wrapper=None):
    """Return the receipt as valid only after the executable hash has matched."""
    receipt_path = install_dir / 'release.json'
    binary_path = install_dir / 'bin/herdr'
    invalid = {'valid': False, 'receipt': {}}
    try:
        check_parents([receipt_path, binary_path] + ([wrapper] if wrapper is not None else []))
    except ValueError:
        return dict(invalid, reason='unsafe_parent', unsafe_parent=True)
    try:
        with regular_reader(receipt_path) as source:
            data = source.read(MAX_RECEIPT_BYTES + 1)
        if len(data) > MAX_RECEIPT_BYTES:
            return dict(invalid, reason='unsupported_receipt')
        receipt = json.loads(data)
        required = {'version', 'asset', 'sha256', 'source', 'manifest'}
        if (not isinstance(receipt, dict) or not required.issubset(receipt)
                or any(not isinstance(receipt[key], str) for key in required)
                or not VERSION.fullmatch(receipt['version'])
                or receipt['asset'] != 'herdr-linux-' + architecture
                or not HASH.fullmatch(receipt['sha256'])
                or not receipt['source'].startswith('https://')
                or not receipt['manifest'].startswith('https://')):
            return dict(invalid, reason='unsupported_receipt')
        digest = hashlib.sha256()
        with regular_reader(binary_path) as binary:
            if not os.fstat(binary.fileno()).st_mode & 0o111 or not os.access(binary_path, os.X_OK):
                return dict(invalid, reason='nonexecutable_binary')
            for chunk in iter(lambda: binary.read(1024 * 1024), b''):
                digest.update(chunk)
        # The release asset is the raw executable, so one hash covers both.
        if digest.hexdigest() != receipt['sha256']:
            return dict(invalid, reason='binary_hash_mismatch')
        return {'valid': True, 'receipt': receipt, 'reason': 'verified'}
    except (OSError, ValueError):
        # Do not expose receipt contents or open any symlink/nonregular target.
        return dict(invalid, reason='missing_unreadable_or_invalid_file')


def prepare_publication(install_dir, wrapper=None):
    """Preserve nonregular destinations by renaming them, never following them.

    Regular files are backed up by Ansible's copy/template modules instead.
    """
    paths = [install_dir / 'bin/herdr', install_dir / 'release.json']
    if wrapper is not None:
        paths.append(wrapper)
    check_parents(paths)
    preserved = []
    for path in paths:
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(mode):
            backup = path.with_name(path.name + '.herdr-invalid-' + uuid.uuid4().hex)
            path.rename(backup)
            preserved.append(str(backup))
    return {'changed': bool(preserved), 'preserved': preserved}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--install-dir', required=True, type=Path)
    parser.add_argument('--architecture', choices=['x86_64', 'aarch64'], required=True)
    parser.add_argument('--prepare-publication', action='store_true')
    parser.add_argument('--wrapper', type=Path)
    args = parser.parse_args()
    try:
        result = (prepare_publication(args.install_dir, args.wrapper)
                  if args.prepare_publication
                  else inspect(args.install_dir, args.architecture, args.wrapper))
        print(json.dumps(result))
    except (OSError, ValueError):
        print('herdr managed paths cannot be prepared safely; review filesystem paths/permissions.',
              file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
