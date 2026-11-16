#!/usr/bin/env python3
"""Install CAO with uv without losing declared extras or --with requirements.

uv tool install replaces the receipt on source changes. Read that receipt first
and merge its explicit requirements; do not freeze transitive dependencies.
Unknown receipt formats fail before modifying the tool environment.
"""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit


PACKAGE = 'cli-agent-orchestrator'


def requirement_text(requirement):
    """Render uv's receipt requirement as PEP 508, rejecting lossy conversions."""
    known = {'name', 'extras', 'specifier', 'url', 'git', 'path', 'marker'}
    unknown = set(requirement) - known
    if unknown:
        raise ValueError(f'Unsupported uv receipt fields: {sorted(unknown)}')
    name = requirement['name']
    if requirement.get('extras'):
        name += '[' + ','.join(sorted(requirement['extras'])) + ']'
    sources = [key for key in ('url', 'git', 'path') if key in requirement]
    if len(sources) > 1 or (sources and requirement.get('specifier')):
        raise ValueError('Ambiguous requirement in uv receipt')
    if sources:
        key = sources[0]
        source = requirement[key]
        if not isinstance(source, str):
            raise ValueError('Unsupported uv receipt source format')
        if key == 'path':
            source = Path(source).as_uri()
        elif key == 'git':
            # Receipts encode a Git ref as ?rev=..., unlike PEP 508's @ref.
            parts = urlsplit(source.removeprefix('git+'))
            query = parse_qs(parts.query)
            if set(query) - {'rev', 'branch', 'tag', 'subdirectory'}:
                raise ValueError('Unsupported Git query in uv receipt')
            refs = [query[key][0] for key in ('rev', 'branch', 'tag') if key in query]
            if len(refs) > 1:
                raise ValueError('Ambiguous Git ref in uv receipt')
            source = 'git+' + urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))
            if refs:
                source += '@' + refs[0]
            fragment = parts.fragment
            if 'subdirectory' in query:
                fragment = urlencode({'subdirectory': query['subdirectory'][0]})
            if fragment:
                source += '#' + fragment
        name += ' @ ' + source
    else:
        name += requirement.get('specifier', '')
    if requirement.get('marker'):
        name += '; ' + requirement['marker']
    return name


def install(uv, config):
    directory = subprocess.run([uv, 'tool', 'dir'], check=True, text=True,
                               capture_output=True).stdout.strip()
    receipt_path = Path(directory) / PACKAGE / 'uv-receipt.toml'
    requirements = []
    tool = {}
    previous_receipt = receipt_path.read_bytes() if receipt_path.exists() else None
    if receipt_path.exists():
        with receipt_path.open('rb') as receipt:
            tool = tomllib.load(receipt)['tool']
            requirements = tool['requirements']
    extras = set(config['extras'])
    packages = list(config['with_packages'])
    for requirement in requirements:
        if requirement['name'].replace('_', '-').lower() == PACKAGE:
            extras.update(requirement.get('extras', []))
        else:
            packages.append(requirement_text(requirement))

    # Preserve extras in custom cao_install_spec as well as the old uv receipt.
    match = re.match(r'^cli[-_]agent[-_]orchestrator(?:\[([^]]+)\])?(.*)$',
                     config['spec'], re.IGNORECASE)
    if not match:
        raise ValueError('cao_install_spec must name cli-agent-orchestrator explicitly')
    extras.update(match.group(1).split(',') if match.group(1) else [])
    if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', extra) for extra in extras):
        raise ValueError('Invalid CAO extra name')
    spec = PACKAGE + ('[' + ','.join(sorted(extras)) + ']' if extras else '') + match.group(2)
    # uv resolves a mutable Git branch even without --upgrade. A matching receipt
    # is therefore the no-update boundary. Source/ref/Python/requirements changes
    # still reconcile immediately, and an explicit upgrade always calls uv.
    requested = {spec, *packages}
    installed = {requirement_text(requirement) for requirement in requirements}
    entrypoints = tool.get('entrypoints', [])
    if (not config['upgrade'] and requested == installed
            and tool.get('python') == config['python'] and entrypoints
            and all(Path(entry['install-path']).exists() for entry in entrypoints)
            and (receipt_path.parent / 'bin/python').exists()):
        return {'changed': False, 'extras': sorted(extras), 'with_count': len(set(packages))}
    command = [uv, 'tool', 'install', '--python', config['python'], spec]
    for package in dict.fromkeys(packages):
        command.extend(['--with', package])
    if config['upgrade']:
        command.append('--upgrade')
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    # uv reports package changes on stderr, including same-version Git revisions.
    changed = bool(re.search(r'^(?:Installed|Uninstalled) \d+ packages?\b',
                             result.stderr, re.MULTILINE))
    changed = changed or receipt_path.read_bytes() != previous_receipt
    return {'changed': changed, 'extras': sorted(extras), 'with_count': len(set(packages))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uv', required=True)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.uv, json.loads(args.config))))
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        # Preserve uv's actionable error output, without dumping the receipt.
        print(getattr(error, 'stderr', None) or str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
