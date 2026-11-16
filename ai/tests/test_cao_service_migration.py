"""Exercise the service migration preflight with isolated files and a fake systemctl."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from jinja2 import Environment, FileSystemLoader


ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / 'ai/roles/cao'


class ServiceMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.units = self.root / 'units'
        self.units.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        systemctl = self.bin / 'systemctl'
        systemctl.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$FAKE_AUDIT"\nprintf "%s\\n" "$FAKE_STATE"\n')
        systemctl.chmod(0o755)
        self.audit = self.root / 'systemctl.log'
        tasks = (ROLE / 'tasks/service.yml').read_text().replace(
            '/etc/systemd/system/', str(self.units) + '/').replace('  become: true', '  become: false')
        (self.root / 'service.yml').write_text(tasks)
        preflight = (ROLE / 'tasks/service-preflight.yml').read_text().replace(
            '/etc/systemd/system/', str(self.units) + '/').replace('  become: true', '  become: false')
        (self.root / 'service-preflight.yml').write_text(preflight)
        (self.root / 'templates').symlink_to(ROLE / 'templates', target_is_directory=True)
        self.variables = {
            'ansible_facts': {'service_mgr': 'systemd'}, 'cao_service_enabled': True,
            'cao_service_name': 'cao-server', 'cao_service_legacy_names': ['cao-server-testuser'],
            'cao_restart_on_change': False, 'cao_terminal_backend': 'tmux', 'ai_stack_user': 'testuser',
            'ai_stack_home': '/home/testuser', 'ai_stack_bin_dir': '/home/testuser/.local/bin',
            'ai_stack_environment': {'PATH': '/usr/bin', 'XDG_CONFIG_HOME': '/home/testuser/.config',
                                     'XDG_DATA_HOME': '/home/testuser/.local/share',
                                     'XDG_CACHE_HOME': '/home/testuser/.cache'},
        }
        (self.root / 'vars.json').write_text(json.dumps(self.variables))
        (self.root / 'play.yml').write_text('''---
- hosts: localhost
  connection: local
  gather_facts: false
  vars_files: [vars.json]
  tasks:
    - ansible.builtin.include_tasks: service.yml
  handlers:
    - name: Reiniciar servidor CAO
      ansible.builtin.debug:
        msg: handler
''')
        template = Environment(loader=FileSystemLoader(ROLE / 'templates')).get_template('cao-server.service.j2')
        self.legacy = self.units / 'cao-server-testuser.service'
        self.legacy.write_text(template.render(**self.variables))

    def run_play(self, state='inactive', override=None, remove=(), check=True):
        variables = dict(self.variables, **(override or {}))
        for name in remove:
            variables.pop(name, None)
        (self.root / 'vars.json').write_text(json.dumps(variables))
        env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                   FAKE_STATE=state, FAKE_AUDIT=str(self.audit), HOME=str(self.root))
        return subprocess.run(['ansible-playbook', '-i', 'localhost,', str(self.root / 'play.yml')] + (['--check'] if check else []),
                              env=env, text=True, capture_output=True, timeout=45)

    def test_service_and_preflight_allow_undefined_backend(self):
        result = self.run_play(remove=['cao_terminal_backend'])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_preflight_ignores_backend_and_herdr_availability(self):
        result = self.run_play(override={'cao_terminal_backend': 'invalid', 'herdr_enabled': False})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.audit.exists())

    def test_cao_session_cannot_stop_or_restart_itself(self):
        facts = {'service_mgr': 'systemd', 'env': {'CAO_TERMINAL_ID': 'test-session'}}
        for state, restart in [('active', False), ('active', True), ('inactive', True)]:
            with self.subTest(state=state, restart=restart):
                result = self.run_play(state, {'cao_restart_on_change': restart, 'ansible_facts': facts})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('execute fora de uma sessão CAO', result.stdout)
                self.assertTrue(self.legacy.exists())

    def test_real_migration_operation_order(self):
        library = self.root / 'library'
        library.mkdir()
        module = library / 'fake_systemd.py'
        module.write_text("""#!/usr/bin/python
from ansible.module_utils.basic import AnsibleModule
import os
m = AnsibleModule(argument_spec=dict(name=dict(type='str'), daemon_reload=dict(type='bool'), enabled=dict(type='bool'), state=dict(type='str')), supports_check_mode=True)
p = m.params
with open(os.environ['FAKE_AUDIT'], 'a') as out:
    out.write('module %s %s enabled=%s legacy=%s new=%s\\n' % (p.get('state') or 'reload', p.get('name') or '-', p.get('enabled'), os.path.exists(os.environ['OLD_UNIT']), os.path.exists(os.environ['NEW_UNIT'])))
m.exit_json(changed=True)
""")
        tasks = (self.root / 'service.yml').read_text().replace('ansible.builtin.systemd_service:', 'fake_systemd:')
        tasks = tasks.replace('        owner: root\n', '').replace('        group: root\n', '')
        (self.root / 'service.yml').write_text(tasks)
        variables = dict(self.variables, cao_restart_on_change=True)
        (self.root / 'vars.json').write_text(json.dumps(variables))
        env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                   FAKE_STATE='active', FAKE_AUDIT=str(self.audit), HOME=str(self.root),
                   OLD_UNIT=str(self.legacy), NEW_UNIT=str(self.units / 'cao-server.service'),
                   ANSIBLE_LIBRARY=str(library))
        result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(self.root / 'play.yml')],
                                env=env, text=True, capture_output=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        lines = [line for line in self.audit.read_text().splitlines() if line.startswith('module ')]
        self.assertEqual(lines, ['module stopped cao-server-testuser.service enabled=False legacy=True new=False',
                                 'module reload - enabled=None legacy=False new=False',
                                 'module started cao-server enabled=True legacy=False new=True'])

    def test_restart_handler_rejects_cao_session(self):
        unit = self.units / 'cao-server.service'
        unit.write_text('fixture')
        tasks = (ROLE / 'tasks/restart-service.yml').read_text().replace(
            '/etc/systemd/system/', str(self.units) + '/').replace('  become: true', '  become: false')
        (self.root / 'restart.yml').write_text(tasks)
        (self.root / 'play.yml').write_text(
            '---\n- hosts: localhost\n  connection: local\n  gather_facts: false\n'
            '  vars_files: [vars.json]\n  tasks:\n    - ansible.builtin.include_tasks: restart.yml\n')
        facts = {'service_mgr': 'systemd', 'env': {'CAO_TERMINAL_ID': 'test-session'}}
        result = self.run_play(override={'cao_restart_on_change': True, 'ansible_facts': facts}, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('execute fora de uma sessão CAO', result.stdout)
        self.assertTrue(unit.exists())
        self.assertFalse(self.audit.exists())

    def test_active_unit_refused_before_changes(self):
        before = self.legacy.read_bytes()
        result = self.run_play('active')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('cao_restart_on_change=true', result.stdout)
        self.assertEqual(self.legacy.read_bytes(), before)
        self.assertFalse((self.units / 'cao-server.service').exists())

    def test_early_play_prevents_later_changes(self):
        # Exercise the real early play with paths redirected into the fixture.
        preflight = (ROLE / 'tasks/service-preflight.yml').read_text().replace(
            '/etc/systemd/system/', str(self.units) + '/').replace('  become: true', '  become: false')
        preflight = preflight.replace("ansible_facts['service_mgr'] == 'systemd'", 'true')
        (self.root / 'service-preflight.yml').write_text(preflight)
        early = (ROOT / 'ai/cao-service-preflight.yml').read_text().replace(
            'roles/cao/tasks/service-preflight.yml', 'service-preflight.yml')
        (self.root / 'early.yml').write_text(early)
        sentinel = self.root / 'later-change'
        (self.root / 'sequence.yml').write_text(
            '---\n- import_playbook: early.yml\n- hosts: localhost\n  gather_facts: false\n'
            '  tasks:\n    - ansible.builtin.file:\n        path: ' + str(sentinel) +
            '\n        state: touch\n')
        user = os.environ.get('USER', 'nobody')
        self.legacy.write_text(self.legacy.read_text().replace('User=testuser', 'User=' + user))
        (self.root / 'vars.json').write_text(json.dumps(dict(self.variables, ai_stack_user=user)))
        env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                   FAKE_STATE='active', FAKE_AUDIT=str(self.audit), HOME=str(self.root),
                   ANSIBLE_ROLES_PATH=str(ROOT / 'ai/roles'))
        result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(self.root / 'sequence.yml'),
                                 '-e', '@' + str(self.root / 'vars.json')], env=env,
                                text=True, capture_output=True, timeout=45)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('cao_restart_on_change=true', result.stdout)
        self.assertFalse(sentinel.exists())
        self.assertTrue(self.legacy.exists())

    def test_active_approved_previews_without_mutating(self):
        before = self.legacy.read_bytes()
        result = self.run_play('active', {'cao_restart_on_change': True})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Seria parada', result.stdout)
        self.assertEqual(self.legacy.read_bytes(), before)
        self.assertFalse((self.units / 'cao-server.service').exists())

    def test_inactive_unit_previews_without_approval(self):
        result = self.run_play('inactive')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Seria parada', result.stdout)
        self.assertTrue(self.legacy.exists())

    def test_foreign_unit_fails_before_state_query(self):
        self.legacy.write_text('[Service]\nUser=someone-else\nExecStart=/usr/bin/false\n')
        result = self.run_play()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('não corresponde', result.stdout)
        self.assertFalse(self.audit.exists())
        self.assertTrue(self.legacy.exists())

    def test_symlink_is_refused_without_following(self):
        target = self.root / 'target'
        target.write_text('do not modify')
        self.legacy.unlink()
        self.legacy.symlink_to(target)
        result = self.run_play()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('não é um arquivo regular', result.stdout)
        self.assertEqual(target.read_text(), 'do not modify')
        self.assertTrue(self.legacy.is_symlink())
        self.assertFalse(self.audit.exists())

    def test_disabled_service_does_not_inspect_units(self):
        result = self.run_play('active', {'cao_service_enabled': False})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.legacy.exists())
        self.assertFalse(self.audit.exists())


if __name__ == '__main__':
    unittest.main()
