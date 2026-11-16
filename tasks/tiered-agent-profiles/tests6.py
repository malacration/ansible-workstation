from pathlib import Path
p=Path('ai/tests/test_cao_service_migration.py');s=p.read_text().replace("WORK = ROOT / 'tasks/tiered-agent-profiles'\n",'').replace('        WORK.mkdir(parents=True, exist_ok=True)\n        self.temp = tempfile.TemporaryDirectory(dir=WORK)', '        self.temp = tempfile.TemporaryDirectory()');s=s.replace("FAKE_STATE='active', FAKE_AUDIT=str(self.audit), HOME=str(self.root))", "FAKE_STATE='active', FAKE_AUDIT=str(self.audit), HOME=str(self.root),\n                   ANSIBLE_ROLES_PATH=str(ROOT / 'ai/roles'))")
pos=s.index('    def test_active_unit_refused_before_changes');s=s[:pos]+'''    def test_cao_session_cannot_stop_or_restart_itself(self):
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
        module.write_text(\"\"\"#!/usr/bin/python
from ansible.module_utils.basic import AnsibleModule
import os
m = AnsibleModule(argument_spec=dict(name=dict(type='str'), daemon_reload=dict(type='bool'), enabled=dict(type='bool'), state=dict(type='str')), supports_check_mode=True)
p = m.params
with open(os.environ['FAKE_AUDIT'], 'a') as out:
    out.write('module %s %s legacy=%s new=%s\\\\n' % (p.get('state') or 'reload', p.get('name') or '-', os.path.exists(os.environ['OLD_UNIT']), os.path.exists(os.environ['NEW_UNIT'])))
m.exit_json(changed=True)
\"\"\")
        tasks = (self.root / 'service.yml').read_text().replace('ansible.builtin.systemd_service:', 'fake_systemd:')
        tasks = tasks.replace('        owner: root\\n', '').replace('        group: root\\n', '')
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
        self.assertEqual(lines, ['module stopped cao-server-testuser.service legacy=True new=False',
                                 'module reload - legacy=False new=False',
                                 'module started cao-server legacy=False new=True'])

'''+s[pos:];p.write_text(s)
p=Path('ai/tests/test_mcp_check_mode.py');s=p.read_text();pos=s.index('    def test_stale_script_is_not_executed');s=s[:pos]+'''    def test_fresh_home_without_uv_skips_preview(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / 'home'
            binary = home / 'bin'
            binary.mkdir(parents=True)
            (root / 'templates').symlink_to(ROLE / 'templates', target_is_directory=True)
            (root / 'files').symlink_to(ROLE / 'files', target_is_directory=True)
            (root / 'mcp.yml').write_text((ROLE / 'tasks/mcp.yml').read_text())
            (root / 'defaults.yml').write_text((ROLE / 'defaults/main.yml').read_text())
            (root / 'vars.json').write_text(json.dumps({
                'ai_stack_home': str(home), 'ai_stack_bin_dir': str(binary),
                'ai_stack_user': 'test', 'ansible_facts': {'user_id': 'test'},
                'ai_stack_environment': {'HOME': str(home)},
            }))
            (root / 'play.yml').write_text('---\\n- hosts: localhost\\n  connection: local\\n  gather_facts: false\\n  vars_files: [defaults.yml, vars.json]\\n  tasks:\\n    - ansible.builtin.include_tasks: mcp.yml\\n')
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(root / 'play.yml'), '--check'],
                                    env=dict(os.environ, HOME=str(home)), capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('preview unavailable: synchronizer will be updated on a real run', result.stdout)
            self.assertFalse((binary / 'uv').exists())

'''+s[pos:];p.write_text(s)
