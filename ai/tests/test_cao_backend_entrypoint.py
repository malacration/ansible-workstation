"""Validate the real backend entry point with an isolated HOME and no services."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ENTRY = Path(__file__).resolve().parents[1] / 'cao-terminal-backend.yml'


class BackendEntrypointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.binary = self.home / 'bin/herdr'
        self.binary.parent.mkdir()
        self.options = {
            'cao_service_enabled': True,
            'ai_stack_user': os.environ.get('USER', 'nobody'),
            'ai_stack_home': str(self.home),
            'ai_stack_bin_dir': str(self.binary.parent),
            'herdr_binary': str(self.binary),
            'herdr_core_binary': str(self.binary.parent / 'hc'),
        }

    def run_entry(self, extra=None, check=True):
        args = ['ansible-playbook', '-i', 'localhost,', str(ENTRY), '-e',
                json.dumps(dict(self.options, **(extra or {})))]
        if check:
            args.append('--check')
        return subprocess.run(args, env=dict(os.environ, HOME=str(self.home)), text=True,
                              capture_output=True, timeout=45)

    def test_undefined_backend_uses_tmux(self):
        result = self.run_entry()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_disabled_herdr_without_executable_is_rejected(self):
        result = self.run_entry({'cao_terminal_backend': 'herdr', 'herdr_enabled': False})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('herdr', result.stdout)

    def test_enabled_herdr_on_fresh_host_is_allowed_in_check_mode(self):
        result = self.run_entry({'cao_terminal_backend': 'herdr', 'herdr_enabled': True})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_invalid_backend_is_rejected(self):
        result = self.run_entry({'cao_terminal_backend': 'invalid'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('tmux ou herdr', result.stdout)

    def test_herdr_app_requires_core_even_with_legacy_herdr(self):
        self.binary.write_text('#!/bin/sh\nexit 0\n')
        self.binary.chmod(0o755)
        result = self.run_entry({'cao_terminal_backend': 'herdr-app'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('exige herdr-core', result.stdout)

    def test_herdr_app_checks_core_version_without_starting_it(self):
        core = Path(self.options['herdr_core_binary'])
        audit = self.home / 'core-arguments'
        for version, expected in [('0.1.20', False), ('0.1.21', True), ('0.2.0', True)]:
            core.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "' + str(audit) +
                            '"\nprintf "hc ' + version + '\\n"\n')
            core.chmod(0o755)
            result = self.run_entry({'cao_terminal_backend': 'herdr-app'})
            self.assertEqual(result.returncode == 0, expected, result.stdout + result.stderr)
        self.assertEqual(audit.read_text().splitlines(), ['--version'] * 3)

    def test_disabled_service_does_not_require_core(self):
        result = self.run_entry({'cao_terminal_backend': 'herdr-app',
                                 'cao_service_enabled': False})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_service_template_selects_herdr_app_and_preserves_tmux(self):
        from jinja2 import Environment, FileSystemLoader
        template = Environment(loader=FileSystemLoader(ENTRY.parent / 'roles/cao/templates')).get_template('cao-server.service.j2')
        variables = dict(self.options, ai_stack_environment={'PATH': '/usr/bin',
                         'XDG_CONFIG_HOME': '/tmp/config', 'XDG_DATA_HOME': '/tmp/data',
                         'XDG_CACHE_HOME': '/tmp/cache'})
        for backend in ['tmux', 'herdr', 'herdr-app']:
            unit = template.render(**dict(variables, cao_terminal_backend=backend))
            command = next(line for line in unit.splitlines() if line.startswith('ExecStart='))
            if backend == 'tmux':
                self.assertNotIn('--terminal', command)
            else:
                self.assertTrue(command.endswith('--terminal ' + backend), command)

    def test_real_standalone_service_rejects_backend_before_units(self):
        # Selecting the herdr tag runs the real entry point while ensuring a
        # regression cannot proceed to systemd tasks on the test host.
        fake_systemctl = self.binary.parent / 'systemctl'
        audit = self.home / 'systemctl-called'
        fake_systemctl.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "' + str(audit) + '"\nexit 1\n')
        fake_systemctl.chmod(0o755)
        env = dict(os.environ, HOME=str(self.home),
                   PATH=str(self.binary.parent) + os.pathsep + os.environ['PATH'])
        for backend, message in [('herdr', 'exige'), ('herdrr', 'tmux ou herdr')]:
            options = dict(self.options, cao_terminal_backend=backend)
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,',
                                     str(ENTRY.parent / 'cao-service.yml'), '--tags', 'herdr',
                                     '-e', json.dumps(options)], env=env, text=True,
                                    capture_output=True, timeout=45)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(message, result.stdout)
            calls = audit.read_text() if audit.exists() else ''
            for action in (' stop ', ' disable ', ' start ', ' enable ', ' restart ', 'daemon-reload'):
                self.assertNotIn(action, ' ' + calls + ' ')

    def test_real_mode_requires_executable(self):
        result = self.run_entry({'cao_terminal_backend': 'herdr', 'herdr_enabled': True}, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.binary.write_text('#!/bin/sh\nexit 0\n')
        self.binary.chmod(0o755)
        result = self.run_entry({'cao_terminal_backend': 'herdr'}, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
