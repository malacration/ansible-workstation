"""Offline regressions for receipt/hash gates, including the actual Ansible tasks."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / 'ai/roles/rtk'
SPEC = importlib.util.spec_from_file_location('installed_state', ROLE / 'files/installed_state.py')
STATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATE)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='rtk-state-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.install = self.root / 'install'
        self.binary = self.install / 'bin/rtk'
        self.binary.parent.mkdir(parents=True)
        self.marker = self.root / 'unexpected-execution'
        self.binary.write_text('#!/bin/sh\nprintf executed > ' + shlex.quote(str(self.marker))
                               + '\nprintf "rtk 1.2.0\\n"\n')
        self.binary.chmod(0o755)
        self.receipt = {'edition': 'oss', 'version': '1.2.0',
                        'asset': 'rtk-oss-x86_64-unknown-linux-musl.tar.gz',
                        'sha256': '1' * 64, 'source': 'https://example.invalid/v1.2.0',
                        'binary_sha256': hashlib.sha256(self.binary.read_bytes()).hexdigest()}
        self.receipt_path = self.install / 'release.json'
        self.receipt_path.write_text(json.dumps(self.receipt))

    def inspect(self):
        result = STATE.inspect(self.install, 'x86_64')
        self.assertFalse(self.marker.exists(), 'The inspection must never execute the binary')
        return result

    def test_matching_supported_receipt_is_valid_without_executing(self):
        self.assertEqual(self.inspect(), {'valid': True, 'receipt': self.receipt, 'reason': 'verified'})

    def test_mismatch_is_invalid_without_executing(self):
        self.binary.write_text(self.binary.read_text() + '# changed\n')
        self.assertFalse(self.inspect()['valid'])
        self.assertEqual(self.inspect()['reason'], 'binary_hash_mismatch')

    def test_malformed_and_unsupported_receipts_are_reconciliation_states(self):
        for data in [b'not json', b'\xff', b'[]', b'{}', b'x' * 65537,
                     json.dumps(dict(self.receipt, edition='full')).encode(),
                     json.dumps(dict(self.receipt, binary_sha256='bad')).encode(),
                     json.dumps(dict(self.receipt, version='latest')).encode(),
                     json.dumps(dict(self.receipt, asset='rtk-oss-aarch64-unknown-linux-musl.tar.gz')).encode()]:
            with self.subTest(data=data[:30]):
                self.receipt_path.write_bytes(data)
                self.assertFalse(self.inspect()['valid'])

    def test_symlink_binary_is_rejected_even_when_target_hash_matches(self):
        target = self.root / 'original'
        self.binary.rename(target)
        self.binary.symlink_to(target)
        self.assertFalse(self.inspect()['valid'])
        self.assertEqual(target.read_bytes(), self.binary.read_bytes())

    def test_symlink_receipt_is_rejected(self):
        target = self.root / 'original-receipt'
        self.receipt_path.rename(target)
        self.receipt_path.symlink_to(target)
        self.assertFalse(self.inspect()['valid'])

    def test_nonexecutable_or_missing_binary_is_invalid(self):
        self.binary.chmod(0o644)
        self.assertFalse(self.inspect()['valid'])
        self.binary.unlink()
        self.assertFalse(self.inspect()['valid'])

    def test_directory_and_fifo_are_not_read(self):
        for path in [self.binary, self.receipt_path]:
            old = path.read_bytes()
            path.unlink()
            path.mkdir()
            self.assertFalse(self.inspect()['valid'])
            path.rmdir()
            os.mkfifo(path)
            self.assertFalse(self.inspect()['valid'])
            path.unlink()
            path.write_bytes(old)
            path.chmod(0o755 if path == self.binary else 0o600)

    def test_publication_preserves_nonregular_objects_without_following_targets(self):
        self.binary.unlink()
        self.binary.symlink_to(self.root / 'missing-target')
        self.receipt_path.unlink()
        self.receipt_path.mkdir()
        (self.receipt_path / 'keep.txt').write_text('retained')
        result = STATE.prepare_publication(self.install)
        self.assertTrue(result['changed'])
        self.assertEqual(len(result['preserved']), 2)
        self.assertTrue(any(Path(p).is_symlink() for p in result['preserved']))
        self.assertTrue(any((Path(p) / 'keep.txt').is_file() for p in result['preserved'] if Path(p).is_dir()))
        self.assertFalse(self.binary.exists())
        self.assertFalse(STATE.prepare_publication(self.install)['changed'])

    def test_linked_parent_is_refused_before_read_or_publication(self):
        old = self.root / 'moved-bin'
        self.binary.parent.rename(old)
        (self.install / 'bin').symlink_to(old, target_is_directory=True)
        self.assertEqual(self.inspect()['reason'], 'unsafe_parent')
        with self.assertRaises(ValueError):
            STATE.prepare_publication(self.install)
        self.assertTrue((old / 'rtk').is_file())


@unittest.skipUnless(shutil.which('ansible-playbook'), 'ansible-playbook is required')
class AnsibleExecutionGateTests(unittest.TestCase):
    def test_actual_role_tasks_skip_invalid_binary_in_normal_and_check_modes(self):
        source = yaml.safe_load((ROLE / 'tasks/main.yml').read_text())
        block = next(task['block'] for task in source if 'block' in task)
        # Use the exact product tasks through the release decision; no downloads,
        # publication or client configuration is included in this offline probe.
        tasks = block[:next(i for i, task in enumerate(block) if task['name'] == 'Preparar diretórios RTK')]
        evidence = []
        for mode in ['normal', 'check']:
            for kind in ['hash_mismatch', 'missing_receipt', 'malformed_receipt', 'unsupported_receipt',
                         'symlink_receipt', 'symlink_binary', 'fifo_binary', 'nonexecutable_binary',
                         'missing_binary', 'valid']:
                with self.subTest(mode=mode, state=kind), tempfile.TemporaryDirectory(prefix='rtk-gate-') as temporary:
                    root = Path(temporary)
                    install = root / 'install'
                    (install / 'bin').mkdir(parents=True)
                    binary = install / 'bin/rtk'
                    marker = root / 'executed'
                    binary.write_text('#!/bin/sh\nprintf executed > ' + shlex.quote(str(marker))
                                      + '\nprintf "rtk 1.2.0\\n"\n')
                    binary.chmod(0o755)
                    receipt = {'edition': 'oss', 'version': '1.2.0',
                               'asset': 'rtk-oss-x86_64-unknown-linux-musl.tar.gz',
                               'sha256': '1' * 64, 'source': 'https://example.invalid/v1.2.0',
                               'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}
                    receipt_path = install / 'release.json'
                    receipt_path.write_text(json.dumps(receipt))
                    if kind == 'hash_mismatch':
                        receipt['binary_sha256'] = '0' * 64
                        receipt_path.write_text(json.dumps(receipt))
                    elif kind == 'missing_receipt':
                        receipt_path.unlink()
                    elif kind == 'malformed_receipt':
                        receipt_path.write_text('not json')
                    elif kind == 'unsupported_receipt':
                        receipt_path.write_text('[]')
                    elif kind in ['symlink_receipt', 'symlink_binary']:
                        path = receipt_path if kind == 'symlink_receipt' else binary
                        target = root / 'original-target'
                        path.rename(target)
                        path.symlink_to(target)
                    elif kind in ['fifo_binary', 'missing_binary']:
                        binary.unlink()
                        if kind == 'fifo_binary':
                            os.mkfifo(binary)
                    elif kind == 'nonexecutable_binary':
                        binary.chmod(0o644)
                    play = [{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
                             'vars': {'role_path': str(ROLE), 'rtk_install_dir': str(install),
                                      'rtk_binary': str(root / 'bin/rtk'),
                                      'rtk_version': 'latest', 'rtk_upgrade': False, 'rtk_checksum': '',
                                      'ansible_facts': {'architecture': 'x86_64'}},
                             'tasks': copy.deepcopy(tasks) + [{'name': 'Verify release decision',
                                 'ansible.builtin.assert': {'that': [
                                     'rtk_verified_state.valid == ' + str(kind == 'valid'),
                                     'rtk_needs_release == ' + str(kind != 'valid')]}}]}]
                    # yaml.safe_dump retains the actual role's Jinja expressions.
                    play_path = root / 'probe.yml'
                    play_path.write_text(yaml.safe_dump(play, sort_keys=False))
                    command = ['ansible-playbook', '-i', 'localhost,', str(play_path)]
                    if mode == 'check':
                        command.append('--check')
                    result = subprocess.run(command, capture_output=True, text=True, cwd=root,
                                            env=dict(os.environ, ANSIBLE_NOCOLOR='1'), timeout=30)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(marker.exists(), kind == 'valid', result.stdout + result.stderr)
                    evidence.append({'mode': mode, 'state': kind, 'marker_written': marker.exists(),
                                     'returncode': result.returncode})
        (Path(__file__).parent / 'EXECUTION_GATE_RESULTS.json').write_text(json.dumps(evidence, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
