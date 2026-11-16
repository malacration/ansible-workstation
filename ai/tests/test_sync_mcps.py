"""Configuration isolation and lifecycle tests; no provider login or API calls."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import frontmatter


SCRIPT = Path(__file__).parents[1] / 'roles/cao/files/sync_mcps.py'
SPEC = importlib.util.spec_from_file_location('sync_mcps', SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)
sync_original_profile_definition = sync.profile_definition


class SyncMcpsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.store = self.home / '.aws/cli-agent-orchestrator/agent-store'
        self.codex = self.home / '.codex/config.toml'
        self.claude = self.home / '.claude.json'
        self.codex.parent.mkdir()
        self.codex.write_text(
            'model = "keep-this-setting"\n'
            '[mcp_servers.chrome-devtools]\ncommand = "codex-command"\n'
            'args = ["--headless"]\n'
            '[mcp_servers.clickup]\nurl = "https://codex.example/mcp"\n'
            '[mcp_servers.disabled]\ncommand = "disabled"\nenabled = false\n'
            '[mcp_servers.cao-mcp-server]\ncommand = "must-not-replace-coordinator"\n'
        )
        self.claude.write_text(json.dumps({
            'theme': 'preserve-this-preference',
            'mcpServers': {
                'chrome-devtools': {'command': 'claude-command', 'args': []},
                'clickup': {'type': 'http', 'url': 'https://claude.example/mcp',
                            'headers': {'Authorization': 'Bearer test-secret'}},
            },
        }))
        self.originals = {path: path.read_bytes() for path in (self.codex, self.claude)}
        self.base = frontmatter.Post(
            'Delegate to (agent_name: developer) and (agent_name: reviewer).',
            name='code_supervisor', description='Test supervisor', role='supervisor',
            allowedTools=['fs_read', '@cao-mcp-server'],
            mcpServers={'cao-mcp-server': {'command': 'cao-mcp-server', 'args': []}},
        )
        patcher = patch.object(sync, 'profile_definition', side_effect=lambda *_: deepcopy(self.base))
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_sync(self, **kwargs):
        return sync.synchronize(self.home, ['codex', 'claude_code'], ['code_supervisor', 'developer', 'reviewer'], **kwargs)

    def profile(self, client, base='code_supervisor'):
        return frontmatter.load(self.store / f'mala_{base}_{client}.md')

    def test_provider_isolation_originals_and_coordinator_are_preserved(self):
        result = self.run_sync()
        self.assertTrue(result['changed'])
        self.assertEqual(len(result['profiles']), 6)
        self.assertNotIn('test-secret', json.dumps(result))
        for path, original in self.originals.items():
            self.assertEqual(path.read_bytes(), original)
        codex = self.profile('codex')
        claude = self.profile('claude')
        self.assertEqual(codex['provider'], 'codex')
        self.assertEqual(claude['provider'], 'claude_code')
        self.assertEqual(codex['mcpServers']['chrome-devtools']['command'], 'codex-command')
        self.assertEqual(claude['mcpServers']['chrome-devtools']['command'], 'claude-command')
        self.assertNotIn('clickup', codex['mcpServers'])
        self.assertIn('@clickup', codex['allowedTools'])
        self.assertEqual(claude['mcpServers']['clickup']['headers']['Authorization'], 'Bearer test-secret')
        self.assertEqual(codex['mcpServers']['cao-mcp-server']['command'], 'cao-mcp-server')
        self.assertNotIn('disabled', codex['mcpServers'])
        self.assertIn('@clickup', claude['allowedTools'])
        self.assertIn('fs_read', claude['allowedTools'])
        self.assertNotIn('*', claude['allowedTools'])
        self.assertIn('mala_developer_codex', codex.content)
        self.assertIn('mala_reviewer_claude', claude.content)
        for path in self.store.glob('*.md'):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_idempotence_and_removal_after_client_configuration_changes(self):
        self.run_sync()
        before = {path: path.stat().st_mtime_ns for path in self.store.glob('*.md')}
        self.assertFalse(self.run_sync()['changed'])
        self.assertEqual(before, {path: path.stat().st_mtime_ns for path in self.store.glob('*.md')})
        self.claude.write_text(json.dumps({'mcpServers': {}}))
        self.assertTrue(self.run_sync()['changed'])
        self.assertEqual(set(self.profile('claude')['mcpServers']), {'cao-mcp-server'})
        self.assertIn('@clickup', self.profile('codex')['allowedTools'])

    def test_codex_http_inherits_global_config_and_preserves_role_grants(self):
        del self.base.metadata['allowedTools']
        expected = ['fs_read', 'fs_list', '@cao-mcp-server', '@clickup', '@chrome-devtools']
        with patch.object(sync, 'role_allowed_tools', return_value=expected) as resolver:
            self.run_sync()
        codex = self.profile('codex')
        self.assertEqual(codex['allowedTools'], expected)
        self.assertNotIn('clickup', codex['mcpServers'])
        self.assertIn('chrome-devtools', codex['mcpServers'])
        self.assertEqual(codex['role'], 'supervisor')
        self.assertEqual(resolver.call_count, 3)
        for path, original in self.originals.items():
            self.assertEqual(path.read_bytes(), original)

    def test_codex_http_grants_are_preserved_for_explicit_delegation(self):
        self.base.metadata['delegateTools'] = ['fs_read']
        self.run_sync()
        codex = self.profile('codex')
        self.assertIn('@clickup', codex['allowedTools'])
        self.assertIn('@clickup', codex['delegateTools'])
        self.assertNotIn('*', codex['delegateTools'])

    def test_codex_profile_http_missing_from_global_config_is_rejected(self):
        self.base.metadata['mcpServers']['profile-only-http'] = {'url': 'https://example.invalid/mcp'}
        with self.assertRaisesRegex(ValueError, 'Codex global'):
            self.run_sync()
        self.assertFalse(self.store.exists())

    def test_check_mode_writes_nothing(self):
        self.assertTrue(self.run_sync(check=True)['changed'])
        self.assertFalse(self.store.exists())
        self.run_sync()
        self.assertFalse(self.run_sync(check=True)['changed'])

    def test_invalid_source_fails_before_any_profile_is_written(self):
        self.claude.write_text('{ invalid-json test-secret')
        with self.assertRaises(ValueError) as failure:
            self.run_sync()
        self.assertNotIn('test-secret', str(failure.exception))
        self.assertFalse(self.store.exists())

    def test_existing_custom_profile_is_not_overwritten(self):
        self.store.mkdir(parents=True)
        custom = self.store / 'mala_reviewer_claude.md'
        custom.write_text('User-owned content')
        with self.assertRaisesRegex(ValueError, 'não pertence à stack'):
            self.run_sync()
        self.assertEqual(list(self.store.glob('*.md')), [custom])
        self.assertEqual(custom.read_text(), 'User-owned content')

    def test_missing_configs_still_provide_internal_coordination(self):
        self.codex.unlink()
        self.claude.unlink()
        self.run_sync()
        self.assertEqual(set(self.profile('codex')['mcpServers']), {'cao-mcp-server'})
        self.assertEqual(set(self.profile('claude')['mcpServers']), {'cao-mcp-server'})

    def test_provider_specific_configuration(self):
        self.base.metadata['codexConfig'] = {'model_reasoning_effort': 'high'}
        self.base.metadata['claudeConfig'] = {'effort': 'low'}
        self.run_sync()
        self.assertEqual(self.profile('codex')['codexConfig']['model_reasoning_effort'], 'high')
        self.assertNotIn('claudeConfig', self.profile('codex').metadata)
        self.assertEqual(self.profile('claude')['claudeConfig']['effort'], 'low')
        self.assertNotIn('codexConfig', self.profile('claude').metadata)

    def test_prune_only_managed_and_check_is_non_destructive(self):
        self.run_sync()
        old = self.store / 'mala_old_codex.md'
        custom = self.store / 'mala_custom_codex.md'
        other = self.store / 'another_old_codex.md'
        old.write_text(sync.MARKER)
        custom.write_text('user owned')
        other.write_text(sync.MARKER)
        preview = self.run_sync(check=True, prune=True)
        self.assertTrue(preview['changed'])
        self.assertEqual(preview['removed'], [str(old)])
        self.assertTrue(old.exists())
        self.assertTrue(self.run_sync(prune=True)['changed'])
        self.assertFalse(old.exists())
        self.assertTrue(custom.exists())
        self.assertTrue(other.exists())
        self.assertFalse(self.run_sync(prune=True)['changed'])

    def test_base_dir_precedes_local_and_builtin(self):
        # Use the real lookup instead of the fixture's mocked profile definition.
        with patch.object(sync, 'profile_definition', sync_original_profile_definition):
            base_dir = self.home / 'bases'
            base_dir.mkdir()
            self.store.mkdir(parents=True)
            (self.store / 'developer.md').write_text('---\ndescription: local\n---\nlocal')
            preferred = base_dir / 'developer.md'
            preferred.write_text('---\ndescription: preferred\n---\npreferred')
            self.assertEqual(sync.profile_definition(self.home, 'developer', base_dir)['description'], 'preferred')
            preferred.unlink()
            self.assertEqual(sync.profile_definition(self.home, 'developer', base_dir)['description'], 'local')
            (self.store / 'developer.md').unlink()
            self.assertTrue(sync.profile_definition(self.home, 'developer', base_dir)['description'])

    def test_disabled_claude_servers_are_not_imported(self):
        config = json.loads(self.claude.read_text())
        config['disabledMcpServers'] = ['clickup']
        self.claude.write_text(json.dumps(config))
        self.run_sync()
        self.assertNotIn('clickup', self.profile('claude')['mcpServers'])

    def test_prune_symlink_other_clients_legacy_and_binary(self):
        self.store.mkdir(parents=True)
        target = self.home / 'target'
        target.write_text(sync.MARKER)
        link = self.store / 'mala_old_codex.md'
        link.symlink_to(target)
        unselected = self.store / 'mala_old_claude.md'
        unselected.write_text(sync.MARKER)
        old = self.store / 'ai_stack_codex_developer.md'
        old.write_bytes(b'\xff' + sync.MARKER.encode())
        with patch.object(sync, 'client_servers', return_value={}):
            result = sync.synchronize(self.home, ['codex'], ['developer'], prune=True,
                                      prune_prefixes=['ai_stack'])
        self.assertEqual(result['removed'], sorted([str(old), str(unselected)]))
        self.assertTrue(link.is_symlink())
        self.assertTrue(target.exists())
        self.assertFalse(unselected.exists())
        self.assertNotIn('_claude', self.profile('codex', 'developer').content)

    def test_stale_definition_prune_preserves_unmanaged_and_symlink(self):
        definitions = self.home / 'definitions'
        definitions.mkdir()
        stale = definitions / 'old.md'
        stale.write_text(sync.MARKER)
        custom = definitions / 'custom.md'
        custom.write_text('custom')
        target = self.home / 'target'
        target.write_text(sync.MARKER)
        link = definitions / 'link.md'
        link.symlink_to(target)
        result = self.run_sync(base_dir=definitions, prune=True)
        self.assertEqual(result['removed'], [str(stale)])
        self.assertFalse(stale.exists())
        self.assertTrue(custom.exists())
        self.assertTrue(link.is_symlink())
        self.assertTrue(target.exists())

    def test_models_validation_and_single_marker(self):
        self.base.metadata['aiStackModels'] = None
        self.base.content = sync.MARKER + '\n\nTest'
        self.run_sync()
        self.assertEqual(self.profile('codex').content.count(sync.MARKER), 1)
        for invalid in ([], {'codex': ''}, {'invalid': 'model'}, {'claude': 3}):
            self.base.metadata['aiStackModels'] = invalid
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'aiStackModels'):
                self.run_sync()

    def test_cli_options(self):
        definitions = self.home / 'definitions'
        definitions.mkdir()
        (definitions / 'custom.md').write_text('---\ndescription: Test\n---\nPrompt')
        self.store.mkdir(parents=True)
        old = self.store / 'ai_stack_codex_developer.md'
        old.write_text(sync.MARKER)
        result = subprocess.run([sys.executable, str(SCRIPT), '--home', str(self.home),
            '--base-dir', str(definitions), '--clients', 'claude_code', '--profiles', 'custom',
            '--prune', '--prune-prefix', 'ai_stack', '--definitions-only', '--check'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['removed'], [str(old)])
        self.assertTrue(old.exists())

    def test_extra_claude_account_profiles(self):
        account_dir = self.home / '.claude-b'
        result = self.run_sync(claude_accounts=[('b', account_dir)])
        self.assertEqual(len(result['profiles']), 9)
        self.assertEqual({p['account'] for p in result['profiles'] if 'account' in p}, {'b'})
        for path, original in self.originals.items():
            self.assertEqual(path.read_bytes(), original)
        self.assertFalse(account_dir.exists())
        default = self.profile('claude')
        extra = self.profile('claude_b')
        self.assertEqual(extra['provider'], 'claude_code')
        self.assertEqual(extra['env'], {'CLAUDE_CONFIG_DIR': str(account_dir)})
        self.assertNotIn('env', default.metadata)
        self.assertNotIn('env', self.profile('codex').metadata)
        # Same global Claude MCPs, policies and coordinator as the default account.
        self.assertEqual(extra['mcpServers'], default['mcpServers'])
        self.assertEqual(extra['allowedTools'], default['allowedTools'])
        self.assertIn('Claude account `b`', extra.content)
        for profile in (default, extra, self.profile('codex')):
            self.assertIn('### claude_b', profile.content)
            self.assertIn('mala_developer_claude_b', profile.content)
            self.assertIn('separate usage limits', profile.content)
        self.assertFalse(self.run_sync(claude_accounts=[('b', account_dir)])['changed'])

    def test_extra_claude_account_tags_and_model(self):
        self.base.metadata.update(tags=['coding'], aiStackModels={'codex': None, 'claude': 'opus'},
                                  claudeConfig={'effort': 'high'})
        self.run_sync(claude_accounts=[('b', self.home / '.claude-b')])
        extra = self.profile('claude_b')
        self.assertEqual(extra['model'], 'opus')
        self.assertEqual(extra['tags'], ['coding', 'effort-high', 'claude', 'account-b'])
        self.assertEqual(self.profile('claude')['tags'], ['coding', 'effort-high', 'claude'])

    def test_removed_claude_account_profiles_are_pruned(self):
        self.run_sync(claude_accounts=[('b', self.home / '.claude-b')])
        stale = self.store / 'mala_developer_claude_b.md'
        self.assertTrue(stale.exists())
        result = self.run_sync(prune=True)
        self.assertIn(str(stale), result['removed'])
        self.assertFalse(stale.exists())
        self.assertNotIn('claude_b', self.profile('claude').content)

    def test_invalid_claude_accounts_are_rejected_before_writing(self):
        absolute = self.home / '.claude-b'
        for accounts in ([('b', absolute), ('b', absolute)],):
            with self.assertRaises(ValueError):
                self.run_sync(claude_accounts=accounts)
        with self.assertRaises(ValueError):
            sync.synchronize(self.home, ['codex'], ['developer'], claude_accounts=[('b', absolute)])
        for value in ('b', 'B=/x', 'b_2=/x', 'b=relative', 'b=~/.claude-b', 'b=/x/../y', 'b=/x/'):
            with self.assertRaises(ValueError, msg=value):
                sync.parse_claude_account(value)
        self.assertEqual(sync.parse_claude_account('b2=/home/u/.claude-b'), ('b2', Path('/home/u/.claude-b')))
        self.assertFalse(self.store.exists())

    def test_cli_claude_account_option(self):
        definitions = self.home / 'definitions'
        definitions.mkdir()
        (definitions / 'custom.md').write_text('---\ndescription: Test\n---\nPrompt')
        args = [sys.executable, str(SCRIPT), '--home', str(self.home), '--base-dir', str(definitions),
                '--clients', 'claude_code', '--profiles', 'custom', '--definitions-only']
        result = subprocess.run(args + ['--claude-account', f'b={self.home}/.claude-b'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(frontmatter.load(self.store / 'mala_custom_claude_b.md')['env'],
                         {'CLAUDE_CONFIG_DIR': f'{self.home}/.claude-b'})
        result = subprocess.run(args + ['--claude-account', 'b=relative'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('caminho absoluto', result.stderr)


class RenderedProfilesTests(unittest.TestCase):
    def test_all_definitions_render_and_validate(self):
        import yaml
        from jinja2 import Environment, FileSystemLoader
        from cli_agent_orchestrator.models.agent_profile import AgentProfile
        role = SCRIPT.parents[1]
        defaults = yaml.safe_load((role / 'defaults/main.yml').read_text())
        env = Environment(loader=FileSystemLoader(role / 'templates'))
        env.filters['to_json'] = json.dumps
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            definitions = home / 'definitions'
            definitions.mkdir()
            defaults['cao_profile_models']['developer_high']['codex'] = 'test-model-id'
            accounts = [{'name': 'b', 'config_dir': str(home / '.claude-b')}]
            for item in defaults['cao_profile_definitions']:
                template = env.get_template('profiles/' + item['template'] + '.md.j2')
                (definitions / (item['name'] + '.md')).write_text(template.render(
                    item=item, cao_profile_efforts=defaults['cao_profile_efforts'],
                    cao_profile_models=defaults['cao_profile_models'], cao_claude_accounts=accounts))
            claude_accounts = [(a['name'], Path(a['config_dir'])) for a in accounts]
            legacy = home / sync.RELATIVE_STORE / 'ai_stack_codex_developer.md'
            legacy.parent.mkdir(parents=True)
            legacy.write_text(sync.MARKER)
            result = sync.synchronize(home, list(sync.CLIENT_LABELS), sync.DEFAULT_PROFILES,
                                      base_dir=definitions, prune=True, prune_prefixes=['ai_stack'],
                                      claude_accounts=claude_accounts)
            self.assertEqual(result['removed'], [str(legacy)])
            paths = sorted(legacy.parent.glob('*.md'))
            self.assertEqual(len(paths), 18)
            for path in paths:
                profile = frontmatter.load(path)
                AgentProfile.model_validate(profile.metadata)
                self.assertEqual(sum(name in profile.metadata for name in ('codexConfig', 'claudeConfig')), 1)
                if 'supervisor' in path.name:
                    self.assertIn('fs_write', profile['allowedTools'])
                if 'reviewer' in path.name:
                    self.assertIn('execute_bash', profile['allowedTools'])
                    self.assertIn('fs_write', profile['allowedTools'])
                if path.name == 'mala_developer_high_codex.md':
                    self.assertEqual(profile['codexConfig']['model'], 'test-model-id')
                    self.assertNotIn('model', profile.metadata)
                if 'developer' in path.name and path.stem.endswith(('_claude', '_claude_b')):
                    self.assertEqual(profile['model'], 'opus')
                if path.stem.endswith('_claude_b'):
                    loaded = AgentProfile.model_validate(profile.metadata)
                    self.assertEqual(loaded.env, {'CLAUDE_CONFIG_DIR': str(home / '.claude-b')})
                if path.name == 'mala_supervisor_claude.md':
                    self.assertIn('## Claude accounts', profile.content)
                    self.assertIn('`claude_b`', profile.content)
                self.assertIn('mala_supervisor_claude', profile.content)
                self.assertIn('mala_supervisor_codex', profile.content)
            self.assertFalse(sync.synchronize(home, list(sync.CLIENT_LABELS), sync.DEFAULT_PROFILES,
                base_dir=definitions, prune=True, prune_prefixes=['ai_stack'],
                claude_accounts=claude_accounts)['changed'])



class CaoCompatibilityTests(unittest.TestCase):
    def test_real_profile_loader_and_provider_delivery(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name('check_cao_providers.py'))],
            check=False, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
