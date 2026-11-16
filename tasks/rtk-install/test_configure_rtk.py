"""Isolated tests; never read or modify the real user's client configuration."""
import importlib.util
import json
import os
import shlex
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('configure_rtk', ROOT / 'ai/roles/rtk/files/configure_rtk.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
BINARY = Path(__file__).parent / 'rtk'


class MergeTests(unittest.TestCase):
    def generated(self, client='claude'):
        return {'hooks': {'PreToolUse': [{'matcher': 'Bash', 'hooks': [
            {'type': 'command', 'command': 'rtk hook ' + client}]}]}}

    def test_hooks_preserve_unrelated_settings_events_and_commands(self):
        original = {'permissions': {'deny': ['Bash(example)']}, 'env': {'EXAMPLE': 'kept'},
                    'hooks': {'Stop': [{'hooks': [{'command': 'other-stop'}]}],
                              'PreToolUse': [{'matcher': 'Bash', 'hooks': [
                                  {'type': 'command', 'command': 'other-hook'}]}]}}
        result = MODULE.merge_hooks(original, self.generated(), 'claude', Path('/test/rtk'))
        self.assertEqual(result['permissions'], original['permissions'])
        self.assertEqual(result['env'], original['env'])
        self.assertEqual(result['hooks']['Stop'], original['hooks']['Stop'])
        self.assertEqual(result['hooks']['PreToolUse'][0], original['hooks']['PreToolUse'][0])
        self.assertEqual(MODULE.merge_hooks(result, self.generated(), 'claude', Path('/test/rtk')), result)

    def test_native_existing_hook_is_updated_without_duplicating(self):
        original = self.generated()
        result = MODULE.merge_hooks(original, self.generated(), 'claude', Path('/test path/rtk'))
        self.assertEqual(len(result['hooks']['PreToolUse']), 1)
        self.assertEqual(result['hooks']['PreToolUse'][0]['hooks'][0]['command'], "'/test path/rtk' hook claude")

    def test_old_absolute_native_hook_is_migrated_for_both_clients(self):
        for client in ['claude', 'codex']:
            with self.subTest(client=client):
                original = self.generated(client)
                original['hooks']['PreToolUse'][0]['hooks'][0]['command'] = "'/old install/bin/rtk' hook " + client
                original['hooks']['PreToolUse'][0]['hooks'].append({'type': 'command', 'command': 'echo hook ' + client})
                result = MODULE.merge_hooks(original, self.generated(client), client, Path('/new install/bin/rtk'))
                commands = [h['command'] for h in result['hooks']['PreToolUse'][0]['hooks']]
                self.assertEqual(commands, ["'/new install/bin/rtk' hook " + client, 'echo hook ' + client])
                self.assertEqual(original['hooks']['PreToolUse'][0]['hooks'][0]['command'],
                                 "'/old install/bin/rtk' hook " + client)

    def test_duplicates_across_old_current_and_bare_paths_are_rejected(self):
        for client in ['claude', 'codex']:
            for commands in [
                ['/old/bin/rtk', '/new/bin/rtk'],
                ['/old/bin/rtk', 'rtk'],
                ['/old/bin/rtk', '/other-old/bin/rtk'],
            ]:
                with self.subTest(client=client, commands=commands):
                    original = self.generated(client)
                    original['hooks']['PreToolUse'][0]['hooks'] = [
                        {'type': 'command', 'command': command + ' hook ' + client} for command in commands]
                    before = json.dumps(original)
                    with self.assertRaises(ValueError):
                        MODULE.merge_hooks(original, self.generated(client), client, Path('/new/bin/rtk'))
                    self.assertEqual(json.dumps(original), before)

    def test_old_absolute_hook_uses_matcher_guard_and_ambiguous_wrappers_are_rejected(self):
        for client in ['claude', 'codex']:
            for executable, matcher in [('/old/bin/rtk', 'Write'), ('/old/bin/custom-wrapper', 'Bash')]:
                with self.subTest(client=client, executable=executable):
                    original = self.generated(client)
                    original['hooks']['PreToolUse'][0]['matcher'] = matcher
                    original['hooks']['PreToolUse'][0]['hooks'][0]['command'] = executable + ' hook ' + client
                    before = json.dumps(original)
                    with self.assertRaises(ValueError):
                        MODULE.merge_hooks(original, self.generated(client), client, Path('/new/bin/rtk'))
                    self.assertEqual(json.dumps(original), before)

    def test_customized_native_hook_flags_are_rejected_before_migration(self):
        original = self.generated('codex')
        original['hooks']['PreToolUse'][0]['hooks'][0]['command'] = '/old/bin/rtk hook codex --skip-env'
        before = json.dumps(original)
        with self.assertRaises(ValueError):
            MODULE.merge_hooks(original, self.generated('codex'), 'codex', Path('/new/bin/rtk'))
        self.assertEqual(json.dumps(original), before)

    def test_malformed_or_legacy_hooks_fail_without_changing_input(self):
        for original in [[], {'hooks': []}, {'hooks': {'PreToolUse': {}}},
                         {'hooks': {'PreToolUse': [{'hooks': ['bad']}]}},
                         {'hooks': {'PreToolUse': [{'hooks': [{'command': 'rtk-rewrite.sh'}]}]}}]:
            before = json.dumps(original)
            with self.assertRaises(ValueError):
                MODULE.merge_hooks(original, self.generated(), 'claude', Path('/test/rtk'))
            self.assertEqual(json.dumps(original), before)

    def test_duplicate_or_custom_matcher_rtk_hooks_fail(self):
        for groups in [self.generated()['hooks']['PreToolUse'] * 2,
                       [{'matcher': 'Write', 'hooks': [{'type': 'command', 'command': 'rtk hook claude'}]}]]:
            with self.assertRaises(ValueError):
                MODULE.merge_hooks({'hooks': {'PreToolUse': groups}}, self.generated(), 'claude', Path('/test/rtk'))

    def test_unknown_release_hook_schema_fails(self):
        with self.assertRaises(ValueError):
            MODULE.merge_hooks({}, self.generated('new-client'), 'claude', Path('/test/rtk'))

    def test_instruction_block_preserves_user_text_and_is_idempotent(self):
        original = '  user instructions \n\n'
        merged = MODULE.merge_block(original, 'body')
        self.assertTrue(merged.startswith(original))
        self.assertEqual(MODULE.merge_block(merged, 'body'), merged)
        changed = MODULE.merge_block(merged, 'new')
        self.assertTrue(changed.startswith(original))
        self.assertNotIn('\nbody\n', changed)

    def test_broken_markers_fail(self):
        for text in [MODULE.START, MODULE.END, MODULE.START + MODULE.END + MODULE.START + MODULE.END]:
            with self.assertRaises(ValueError):
                MODULE.merge_block(text, 'body')

    def test_symlink_and_outside_home_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / '.codex').symlink_to('/nonexistent')
            for path in [home / '.codex/AGENTS.md', Path('/outside/AGENTS.md')]:
                with self.assertRaises(ValueError):
                    MODULE.safe_path(home, path)


@unittest.skipUnless(BINARY.exists(), 'Download and verify the release binary first')
class RealReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.binary = self.home / 'bin/rtk'
        self.binary.parent.mkdir()
        self.binary.write_text('#!/bin/sh\nexport RTK_TELEMETRY_DISABLED=1 RTK_ONRAMP_DISABLED=1\nexec '
                               + str(BINARY) + ' "$@"\n')
        self.binary.chmod(0o755)
        self.claude = self.home / '.claude'
        self.codex = self.home / '.codex'
        self.claude.mkdir(); self.codex.mkdir()
        self.original = {'permissions': {'allow': ['Bash(git status)']},
                         'hooks': {'PreToolUse': [{'matcher': 'Bash', 'hooks': [
                             {'type': 'command', 'command': 'echo existing'}]}]}}
        (self.claude / 'settings.json').write_text(json.dumps(self.original))
        (self.codex / 'hooks.json').write_text(json.dumps(self.original))
        for path in [self.claude / 'CLAUDE.md', self.codex / 'AGENTS.md',
                     self.claude / 'RTK.md', self.codex / 'RTK.md']:
            path.write_text('User notes must stay.\n')
        # Synthetic configs are left byte-identical, and are never passed to init.
        self.configs = [self.codex / 'config.toml', self.home / '.config/rtk/config.toml']
        for path in self.configs:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# preserved\n[custom]\nvalue = "keep"\n')

    def configure(self, check=False):
        return MODULE.configure(self.home, self.binary, self.claude, self.codex,
                                ['claude_code', 'codex'], check)

    def test_release_init_merge_backups_and_second_run_idempotence(self):
        first = self.configure()
        self.assertTrue(first['changed'])
        self.assertEqual(len(first['files']), 6)
        for client, name in [(self.claude, 'settings.json'), (self.codex, 'hooks.json')]:
            result = json.loads((client / name).read_text())
            self.assertEqual(result['permissions'], self.original['permissions'])
            self.assertEqual(result['hooks']['PreToolUse'][0], self.original['hooks']['PreToolUse'][0])
            self.assertEqual(len(list(client.glob(name + '.rtk-backup.*'))), 1)
        for path in self.configs:
            self.assertEqual(path.read_text(), '# preserved\n[custom]\nvalue = "keep"\n')
        for path in [self.claude / 'CLAUDE.md', self.codex / 'AGENTS.md',
                     self.claude / 'RTK.md', self.codex / 'RTK.md']:
            self.assertTrue(path.read_text().startswith('User notes must stay.\n'))
        before = {str(p): p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        self.assertFalse(self.configure()['changed'])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.home.rglob('*') if p.is_file()})
        self.assertFalse(list(self.home.rglob('pipeline.toml')))

    def test_dry_run_does_not_change_selected_home(self):
        before = {str(p): p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        self.assertTrue(self.configure(check=True)['changed'])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.home.rglob('*') if p.is_file()})

    def test_invalid_second_client_prevents_partial_configuration(self):
        (self.codex / 'hooks.json').write_text('not json')
        before = (self.claude / 'settings.json').read_bytes()
        with self.assertRaises(ValueError):
            self.configure()
        self.assertEqual((self.claude / 'settings.json').read_bytes(), before)
        self.assertFalse(list(self.home.rglob('*.rtk-backup.*')))

    def test_native_hooks_rewrite_supported_shell_and_keep_other_tools(self):
        self.configure()
        environment = dict(os.environ, HOME=str(self.home), CODEX_HOME=str(self.codex),
                           CLAUDE_CONFIG_DIR=str(self.claude), XDG_CONFIG_HOME=str(self.home / '.config'),
                           XDG_DATA_HOME=str(self.home / '.local/share'))
        for client in ['claude', 'codex']:
            for tool in ['Bash', 'Read']:
                payload = {'hook_event_name': 'PreToolUse', 'tool_name': tool, 'permission_mode': 'default',
                           'tool_input': ({'command': 'git status', 'timeout': 30000}
                                          if tool == 'Bash' else {'file_path': '/example.txt'}),
                           'cwd': str(self.home)}
                result = subprocess.run([str(self.binary), 'hook', client], input=json.dumps(payload),
                                        capture_output=True, text=True, env=environment, cwd=self.home, check=True)
                if tool == 'Bash':
                    self.assertTrue(result.stdout.strip(), (client, tool, result.stderr))
                    output = json.loads(result.stdout)['hookSpecificOutput']
                    self.assertEqual(output['updatedInput']['command'], 'rtk git status')
                    self.assertEqual(output['updatedInput']['timeout'], 30000)
                else:
                    self.assertEqual(result.stdout.strip(), '')

    def test_wrapper_relocation_migrates_existing_hooks_without_duplicate(self):
        self.configure()
        moved = self.home / 'relocated bin/rtk'
        moved.parent.mkdir()
        moved.write_bytes(self.binary.read_bytes())
        moved.chmod(0o755)
        result = MODULE.configure(self.home, moved, self.claude, self.codex, ['claude_code', 'codex'])
        self.assertEqual(len(result['files']), 2)
        for directory, filename, client in [(self.claude, 'settings.json', 'claude'),
                                             (self.codex, 'hooks.json', 'codex')]:
            root = json.loads((directory / filename).read_text())
            commands = [hook['command'] for group in root['hooks']['PreToolUse'] for hook in group['hooks']]
            self.assertEqual(commands, ['echo existing', shlex.quote(str(moved)) + ' hook ' + client])
        self.assertFalse(MODULE.configure(self.home, moved, self.claude, self.codex,
                                         ['claude_code', 'codex'])['changed'])

    def test_ambiguous_old_codex_hook_rejects_before_any_client_write(self):
        self.configure()
        hooks = json.loads((self.codex / 'hooks.json').read_text())
        hooks['hooks']['PreToolUse'][1]['hooks'][0]['command'] = '/previous/custom-wrapper hook codex'
        (self.codex / 'hooks.json').write_text(json.dumps(hooks))
        moved = self.home / 'other/rtk'
        moved.parent.mkdir()
        moved.write_bytes(self.binary.read_bytes())
        moved.chmod(0o755)
        before = {str(p): p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        with self.assertRaises(ValueError):
            MODULE.configure(self.home, moved, self.claude, self.codex, ['claude_code', 'codex'])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.home.rglob('*') if p.is_file()})

    def test_wrapper_blocks_telemetry_even_with_enabled_config(self):
        self.configs[1].write_text('[telemetry]\nenabled = true\nconsent_given = true\n')
        environment = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / '.config'),
                           XDG_DATA_HOME=str(self.home / '.local/share'))
        result = subprocess.run([str(self.binary), 'telemetry', 'status'], capture_output=True,
                                text=True, env=environment, check=True)
        self.assertIn('RTK_TELEMETRY_DISABLED=1 (blocked)', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
