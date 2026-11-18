"""The check-mode preview must never execute an outdated installed synchronizer."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROLE = Path(__file__).resolve().parents[1] / 'roles/cao'


class McpCheckModeTests(unittest.TestCase):
    def test_fresh_home_without_uv_skips_preview(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / 'home'
            binary = home / 'bin'
            binary.mkdir(parents=True)
            (root / 'templates').symlink_to(ROLE / 'templates', target_is_directory=True)
            (root / 'files').symlink_to(ROLE / 'files', target_is_directory=True)
            (root / 'mcp.yml').write_text((ROLE / 'tasks/mcp.yml').read_text())
            (root / 'claude_accounts.yml').write_text((ROLE / 'tasks/claude_accounts.yml').read_text())
            (root / 'defaults.yml').write_text((ROLE / 'defaults/main.yml').read_text())
            (root / 'vars.json').write_text(json.dumps({
                'ai_stack_home': str(home), 'ai_stack_bin_dir': str(binary),
                'ai_stack_user': 'test', 'ansible_facts': {'user_id': 'test'},
                'ai_stack_environment': {'HOME': str(home)},
            }))
            (root / 'play.yml').write_text('---\n- hosts: localhost\n  connection: local\n  gather_facts: false\n  vars_files: [defaults.yml, vars.json]\n  tasks:\n    - ansible.builtin.include_tasks: mcp.yml\n')
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(root / 'play.yml'), '--check'],
                                    env=dict(os.environ, HOME=str(home)), capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('preview unavailable: synchronizer will be updated on a real run', result.stdout)
            self.assertFalse((binary / 'uv').exists())

    def test_stale_script_is_not_executed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / 'home'
            binary = home / 'bin'
            binary.mkdir(parents=True)
            # Return the parent directory of the CAO interpreter's tool directory.
            uv = binary / 'uv'
            uv.write_text(f'#!/bin/sh\nprintf "%s\\n" {sys.executable.rsplit("/", 3)[0]}\n')
            uv.chmod(0o755)
            (root / 'templates').symlink_to(ROLE / 'templates', target_is_directory=True)
            (root / 'files').symlink_to(ROLE / 'files', target_is_directory=True)
            (root / 'play.yml').write_text('''---
- hosts: localhost
  connection: local
  gather_facts: false
  vars_files: [defaults.yml, vars.json]
  tasks:
    - ansible.builtin.include_tasks: mcp.yml
''')
            (root / 'mcp.yml').write_text((ROLE / 'tasks/mcp.yml').read_text())
            (root / 'claude_accounts.yml').write_text((ROLE / 'tasks/claude_accounts.yml').read_text())
            (root / 'defaults.yml').write_text((ROLE / 'defaults/main.yml').read_text())
            (root / 'vars.json').write_text(json.dumps({
                'ai_stack_home': str(home), 'ai_stack_bin_dir': str(binary),
                'ai_stack_user': 'test', 'ansible_facts': {'user_id': 'test'},
                'ai_stack_environment': {'HOME': str(home)},
            }))
            env = dict(os.environ, HOME=str(home))
            command = ['ansible-playbook', '-i', 'localhost,', str(root / 'play.yml')]
            first = subprocess.run(command, env=env, text=True, capture_output=True, timeout=60)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            script = home / '.local/share/ai-stack/sync_mcps.py'
            # Any invocation would fail and create evidence; no --prune support.
            audit = root / 'stale-executed'
            script.write_text(f'from pathlib import Path\nPath({str(audit)!r}).touch()\nraise SystemExit(2)\n')
            before = script.read_bytes()
            result = subprocess.run([*command, '--check'], env=env, text=True, capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('preview unavailable: synchronizer will be updated on a real run', result.stdout)
            self.assertFalse(audit.exists())
            self.assertEqual(script.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
