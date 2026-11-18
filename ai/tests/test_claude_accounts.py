"""Tests for the per-account shell helpers of the cao role (gateway key helper, claude-list)."""

import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

from jinja2 import Environment, FileSystemLoader

ROLE = Path(__file__).resolve().parents[1] / 'roles/cao'
HELPER = ROLE / 'files/ai-stack-gateway-key'
SECRET = 'sk-test-0123456789abcdef'


def render_claude_list(home, accounts):
    env = Environment(loader=FileSystemLoader(ROLE / 'templates'), trim_blocks=True)
    # Minimal stand-ins for the Ansible filters used by the template.
    env.filters['quote'] = lambda value: shlex.quote(str(value))
    env.filters['regex_escape'] = re.escape
    env.filters['regex_replace'] = lambda value, pattern, repl: re.sub(pattern, repl, value)
    return env.get_template('claude-list.j2').render(cao_claude_accounts=accounts, ai_stack_home=str(home))


class ShellHelpersTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.env_file = self.home / '.aws/cli-agent-orchestrator/.env'
        self.env_file.parent.mkdir(parents=True)
        self.environ = {'HOME': str(self.home), 'PATH': os.environ['PATH']}

    def tearDown(self):
        self.temp.cleanup()

    def run_script(self, path, *args):
        return subprocess.run(['sh', str(path), *args], capture_output=True, text=True, env=self.environ)


class GatewayKeyHelperTests(ShellHelpersTestCase):
    def test_prints_plain_and_quoted_values(self):
        for line in (f'IA_GATEWAY_KEY={SECRET}', f'IA_GATEWAY_KEY="{SECRET}"', f"IA_GATEWAY_KEY='{SECRET}'"):
            self.env_file.write_text(f'OTHER=x\n{line}\n')
            result = self.run_script(HELPER, 'IA_GATEWAY_KEY')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, SECRET + '\n')

    def test_missing_key_fails_without_leaking_other_values(self):
        self.env_file.write_text(f'OTHER={SECRET}\n')
        result = self.run_script(HELPER, 'IA_GATEWAY_KEY')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertNotIn(SECRET, result.stderr)
        self.assertIn('cao env set IA_GATEWAY_KEY', result.stderr)

    def test_missing_env_file_fails(self):
        result = self.run_script(HELPER, 'IA_GATEWAY_KEY')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')

    def test_invalid_variable_names_are_rejected(self):
        self.env_file.write_text(f'IA_GATEWAY_KEY={SECRET}\n')
        for name in ('ia_gateway_key', '1KEY', 'KEY=', '.*', 'A;B'):
            result = self.run_script(HELPER, name)
            self.assertEqual(result.returncode, 2, name)
            self.assertEqual(result.stdout, '')


class ClaudeListTests(ShellHelpersTestCase):
    def setUp(self):
        super().setUp()
        self.accounts = [
            {'name': 'b', 'config_dir': str(self.home / '.claude-b')},
            {'name': 'gw', 'config_dir': str(self.home / '.claude-gw'),
             'gateway': {'base_url': 'https://gateway.example', 'key_env': 'IA_GATEWAY_KEY',
                         'models': {'opus': 'claude-opus-x', 'haiku': 'claude-haiku-x'}}},
        ]
        self.script = self.home / 'claude-list'
        self.script.write_text(render_claude_list(self.home, self.accounts))

    def lines(self):
        result = self.run_script(self.script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(SECRET, result.stdout + result.stderr)
        return result.stdout.splitlines()

    def test_lists_every_account_with_status(self):
        (self.home / '.claude').mkdir()
        (self.home / '.claude/.credentials.json').write_text('{"token": "%s"}' % SECRET)
        self.env_file.write_text(f'IA_GATEWAY_KEY={SECRET}\n')
        lines = self.lines()
        self.assertEqual(lines[0].split(), ['CONTA', 'COMANDO', 'PASTA', 'ACESSO'])
        self.assertTrue(lines[1].startswith('home'))
        self.assertIn('login ok', lines[1])
        self.assertIn('claude-b', lines[2])
        self.assertIn('~/.claude-b', lines[2])
        self.assertIn('sem login', lines[2])
        self.assertIn('claude-gw', lines[3])
        self.assertIn('gateway https://gateway.example', lines[3])
        self.assertIn('chave IA_GATEWAY_KEY ok', lines[3])
        self.assertIn('modelos: opus=claude-opus-x, haiku=claude-haiku-x', lines[4])
        self.assertEqual(len(lines), 5)

    def test_reports_missing_gateway_key(self):
        self.assertIn('chave IA_GATEWAY_KEY ausente', self.lines()[3])

    def test_no_extra_accounts_lists_only_home(self):
        self.script.write_text(render_claude_list(self.home, []))
        self.assertEqual(len(self.lines()), 2)


MCP_SYNC = ROLE / 'files/sync_claude_account_mcps.py'
# Stand-in for `claude mcp add-json/remove --scope user`: logs argv, edits $CLAUDE_CONFIG_DIR/.claude.json.
FAKE_CLAUDE = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
with open(os.environ['FAKE_CLAUDE_LOG'], 'a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\\n')
path = Path(os.environ['CLAUDE_CONFIG_DIR']) / '.claude.json'
config = json.loads(path.read_text()) if path.exists() else {}
servers = config.setdefault('mcpServers', {})
if sys.argv[2] == 'remove':
    del servers[sys.argv[3]]
else:
    servers[sys.argv[3]] = json.loads(sys.stdin.read() if sys.argv[4] == '-' else sys.argv[4])
path.write_text(json.dumps(config))
'''


class AccountMcpSyncTests(ShellHelpersTestCase):
    def setUp(self):
        super().setUp()
        self.account = self.home / '.claude-gw'
        self.account.mkdir()
        (self.account / '.claude.json').write_text(json.dumps({
            'hasCompletedOnboarding': True,
            'mcpServers': {'own': {'command': 'own-mcp'},
                           'playwright': {'command': 'old-playwright'}}}))
        self.source = {
            'playwright': {'type': 'stdio', 'command': '/bin/playwright-mcp', 'args': ['--browser', 'chrome']},
            'secretive': {'type': 'http', 'url': 'https://mcp.example', 'headers': {'Authorization': SECRET}},
            'disabled': {'command': 'disabled-mcp'},
            'cao-mcp-server': {'command': 'cao-mcp-server'},
        }
        (self.home / '.claude.json').write_text(json.dumps({
            'mcpServers': self.source, 'disabledMcpServers': ['disabled']}))
        self.claude = self.home / 'claude'
        self.claude.write_text(FAKE_CLAUDE)
        self.claude.chmod(0o755)
        self.log = self.home / 'claude.log'
        self.environ['FAKE_CLAUDE_LOG'] = str(self.log)

    def sync(self, *extra):
        result = subprocess.run(
            [sys.executable, '-I', str(MCP_SYNC), '--home', str(self.home), '--claude', str(self.claude),
             '--account-dir', str(self.account), *extra],
            capture_output=True, text=True, env=self.environ)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(SECRET, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def account_servers(self):
        return json.loads((self.account / '.claude.json').read_text())['mcpServers']

    def test_check_mode_reports_without_calling_claude(self):
        result = self.sync('--check')
        self.assertTrue(result['changed'])
        self.assertEqual(result['accounts'][str(self.account)], ['playwright', 'secretive'])
        self.assertFalse(self.log.exists())

    def test_mirrors_enabled_servers_keeps_account_ones_and_is_idempotent(self):
        result = self.sync()
        self.assertTrue(result['changed'])
        servers = self.account_servers()
        self.assertEqual(servers['playwright'], self.source['playwright'])
        self.assertEqual(servers['secretive'], self.source['secretive'])
        self.assertEqual(servers['own'], {'command': 'own-mcp'})
        self.assertNotIn('disabled', servers)
        self.assertNotIn('cao-mcp-server', servers)
        self.assertTrue(json.loads((self.account / '.claude.json').read_text())['hasCompletedOnboarding'])
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertIn(['mcp', 'remove', 'playwright', '--scope', 'user'], calls)
        self.assertIn(['mcp', 'add-json', 'secretive', '-', '--scope', 'user'], calls)
        # Servers without env values or headers go as an argument (stdin is refused inside Claude Code).
        self.assertIn(['mcp', 'add-json', 'playwright', json.dumps(self.source['playwright']), '--scope', 'user'], calls)
        # Secret-bearing JSON goes through stdin, never argv.
        self.assertNotIn(SECRET, self.log.read_text())
        self.assertFalse(self.sync()['changed'])

    def test_failed_claude_call_does_not_leak_configuration(self):
        self.claude.write_text(f'#!/bin/sh\necho "{SECRET}" >&2\nexit 1\n')
        result = subprocess.run(
            [sys.executable, '-I', str(MCP_SYNC), '--home', str(self.home), '--claude', str(self.claude),
             '--account-dir', str(self.account)], capture_output=True, text=True, env=self.environ)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(SECRET, result.stdout + result.stderr)

    def test_relative_account_dir_is_rejected(self):
        result = subprocess.run([sys.executable, '-I', str(MCP_SYNC), '--account-dir', 'relative', '--check'],
                                capture_output=True, text=True, env=self.environ)
        self.assertEqual(result.returncode, 1)


if __name__ == '__main__':
    unittest.main()
