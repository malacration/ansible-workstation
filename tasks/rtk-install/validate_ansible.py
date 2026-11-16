#!/usr/bin/env python3
"""Exercise only tasks/rtk-install/ansible-home; downloads official OSS releases."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

TASK = Path(__file__).resolve().parent
PLAY = TASK / 'isolated.yml'
HOME = TASK / 'ansible-home'
BINARY = HOME / '.local/share/ai-stack/rtk/bin/rtk'
RESULTS = []


def run(name, variables=None, options=(), fail=False, unchanged=False):
    command = ['ansible-playbook', str(PLAY), *options]
    if variables:
        command += ['-e', json.dumps(variables)]
    process = subprocess.run(command, text=True, capture_output=True, cwd=TASK.parents[1])
    (TASK / (name + '.log')).write_text(process.stdout + process.stderr)
    recap = re.search(r'localhost\s+: ok=.*', process.stdout)
    print(name + ': ' + (recap.group() if recap else 'no recap'), flush=True)
    assert (process.returncode != 0) == fail, name + ' unexpected exit status'
    if unchanged:
        assert 'changed=0 ' in recap.group(), name + ' was not idempotent'
    RESULTS.append({'case': name, 'returncode': process.returncode,
                    'recap': recap.group() if recap else None})


def version():
    process = subprocess.run([str(BINARY), '--version'], capture_output=True,
                             text=True, check=True, env={'HOME': str(HOME)})
    return process.stdout.strip()


def main():
    run('ansible-syntax', options=['--syntax-check'])
    run('ansible-reconcile')
    run('ansible-second', unchanged=True)
    run('ansible-check', options=['--check', '--diff'], unchanged=True)
    run('ansible-pin-1.1.0', {'rtk_version': '1.1.0', 'rtk_clients': []})
    assert version() == 'rtk 1.1.0'
    run('ansible-latest-offline', {'rtk_version': 'latest', 'rtk_clients': [],
                                 'rtk_release_api': 'http://127.0.0.1:9'}, unchanged=True)
    assert version() == 'rtk 1.1.0'
    run('ansible-explicit-upgrade', {'rtk_version': 'latest', 'rtk_upgrade': True})
    assert version() == 'rtk 1.2.0'
    before = hashlib.sha256(BINARY.read_bytes()).hexdigest()
    run('ansible-bad-checksum', {'rtk_checksum': 'sha256:' + '0' * 64}, fail=True)
    assert hashlib.sha256(BINARY.read_bytes()).hexdigest() == before
    run('ansible-final-idempotence', unchanged=True)
    # The wrapper, not a raw --version call, enforces the telemetry environment.
    environment = {'HOME': str(HOME), 'XDG_CONFIG_HOME': str(HOME / '.config'),
                   'XDG_DATA_HOME': str(HOME / '.local/share'), 'PATH': '/usr/bin:/bin'}
    status = subprocess.run([str(HOME / '.local/bin/rtk'), 'telemetry', 'status'],
                            capture_output=True, text=True, check=True, env=environment)
    assert 'RTK_TELEMETRY_DISABLED=1 (blocked)' in status.stdout
    (TASK / 'telemetry-status.txt').write_text(status.stdout)
    # Native shell filter and bypass both execute only a disposable local Git repo.
    repo = HOME / 'smoke-repo'
    repo.mkdir(exist_ok=True)
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    (repo / 'example.txt').write_text('local fixture\n')
    for args in [['git', 'status'], ['bypass', 'git', 'status']]:
        result = subprocess.run([str(HOME / '.local/bin/rtk'), *args], cwd=repo,
                                env=environment, capture_output=True, text=True, check=True)
        (TASK / ('smoke-' + args[0] + '.txt')).write_text(result.stdout + result.stderr)
        assert 'example.txt' in result.stdout
    receipt = json.loads((HOME / '.local/share/ai-stack/rtk/release.json').read_text())
    assert receipt['binary_sha256'] == before
    assert not list(HOME.rglob('pipeline.toml'))
    (TASK / 'VALIDATION_RESULTS.json').write_text(json.dumps(RESULTS, indent=2) + '\n')
    print('All isolated Ansible checks passed.', flush=True)


if __name__ == '__main__':
    main()
