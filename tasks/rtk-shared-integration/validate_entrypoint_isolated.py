#!/usr/bin/env python3
"""Run only the actual RTK entrypoint against a disposable, offline-seeded HOME."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import yaml

ROOT = Path('/home/andrew/git/ansible-workstation')
OUTPUT = ROOT / 'tasks/rtk-shared-integration/ISOLATED_ENTRYPOINT.json'
architecture = os.uname().machine
defaults = yaml.safe_load((ROOT / 'ai/roles/rtk/defaults/main.yml').read_text())
asset = f'rtk-oss-{architecture}-unknown-linux-musl.tar.gz'
archive = ROOT / 'tasks/rtk-install' / asset
expected = defaults['rtk_audited_checksums']['1.2.0'][architecture]
actual = hashlib.sha256(archive.read_bytes()).hexdigest()
assert actual == expected, 'Existing fixture archive must match the audited official pin'
with tarfile.open(archive) as source:
    member = source.getmember('rtk')
    assert member.isfile() and not member.issym() and not member.islnk()
    binary = source.extractfile(member).read()

with tempfile.TemporaryDirectory(prefix='rtk-real-entrypoint-') as temporary:
    root = Path(temporary)
    home = root / 'home'
    home.mkdir()
    assert home != Path.home() and home.is_relative_to(root)
    installed = home / '.local/share/ai-stack/rtk'
    (installed / 'bin').mkdir(parents=True)
    (installed / 'bin/rtk').write_bytes(binary)
    (installed / 'bin/rtk').chmod(0o755)
    (installed / 'release.json').write_text(json.dumps({
        'edition': 'oss', 'version': '1.2.0', 'asset': asset, 'sha256': actual,
        'binary_sha256': hashlib.sha256(binary).hexdigest(),
        'source': 'https://github.com/rtk-ai/rtk/releases/download/v1.2.0',
    }))
    variables = root / 'variables.json'
    variables.write_text(json.dumps({
        # Override only HOME; user/bin/cache/environment still resolve from the
        # actual entrypoint's role defaults. No derived shared variables are injected.
        'ai_stack_home': str(home), 'rtk_clients': [],
        'rtk_release_api': 'http://127.0.0.1:9/unexpected-release-resolution',
    }))
    environment = dict(os.environ, HOME=str(home), ANSIBLE_LOCAL_TEMP=str(root / 'controller'),
                       ANSIBLE_REMOTE_TEMP=str(root / 'remote'), ANSIBLE_NOCOLOR='1',
                       ANSIBLE_CONFIG='/etc/ansible/ansible.cfg',
                       RTK_TELEMETRY_DISABLED='1', RTK_ONRAMP_DISABLED='1')
    command = ['ansible-playbook', '-i', 'localhost,', str(ROOT / 'ai/rtk.yml'),
               '--skip-tags', 'ai_common', '-e', '@' + str(variables)]
    results = []
    for label in ['initial_publication', 'repeat_idempotence']:
        result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True,
                                text=True, timeout=60)
        results.append({'label': label, 'argv': command, 'returncode': result.returncode,
                        'stdout': result.stdout, 'stderr': result.stderr})
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'Consultar metadados oficiais' not in result.stdout, 'Unexpected release lookup'
        if label == 'repeat_idempotence':
            assert re.search(r'changed=0\s', result.stdout), result.stdout
        print(label, 'passed', flush=True)
    assert (home / '.local/bin/rtk').is_file()
    assert (home / '.cache/ai-stack/rtk').is_dir()
    assert hashlib.sha256((installed / 'bin/rtk').read_bytes()).hexdigest() == hashlib.sha256(binary).hexdigest()
    OUTPUT.write_text(json.dumps({
        'entrypoint': str(ROOT / 'ai/rtk.yml'), 'temporary_home': str(home),
        'temporary_home_removed_after_test': True,
        'archive_path': str(archive), 'audited_archive_sha256': actual,
        'shared_prerequisite_tasks_skipped': 'ai_common',
        'role_defaults_exercised': ['ai_stack_user', 'ai_stack_bin_dir', 'ai_stack_cache_dir',
                                    'ai_stack_environment', 'ai_stack_upgrade'],
        'only_home_overridden': True, 'clients': [], 'release_lookup_required': False,
        'commands': results,
    }, indent=2) + '\n')
