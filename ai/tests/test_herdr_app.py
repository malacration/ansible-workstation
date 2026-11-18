"""herdr_app.py: pinned archive install, local patches and owned-settings merges (isolated HOME)."""

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest


ROLE = Path(__file__).resolve().parents[1] / 'roles/herdr_app'
HELPER = ROLE / 'files/herdr_app.py'
COMMIT = 'a' * 40

PATCH = '''diff --git a/mods/demo/main.js b/mods/demo/main.js
--- a/mods/demo/main.js
+++ b/mods/demo/main.js
@@ -1 +1 @@
-export const answer = 1;
+export const answer = 2;
diff --git a/mods/demo/extra.js b/mods/demo/extra.js
new file mode 100644
--- /dev/null
+++ b/mods/demo/extra.js
@@ -0,0 +1 @@
+export const extra = true;
'''


def make_tarball(path, files, links=()):
    """A GitHub-style archive: one top folder, then the repository tree."""
    with tarfile.open(path, 'w:gz') as archive:
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo('repo-' + COMMIT + '/' + name)
            info.size = len(data)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))
        for name, target in links:
            info = tarfile.TarInfo('repo-' + COMMIT + '/' + name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            archive.addfile(info)
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class HerdrAppTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.app = self.home / '.config/herdr-app'
        self.app.mkdir(parents=True)
        (self.app / 'keys.json').write_text(json.dumps({'global': {'ctrl-shift-b': 'layout.toggle:sidebar'}}))
        self.cache = self.home / '.cache/ai-stack/herdr-app'
        self.cache.mkdir(parents=True)
        self.patches = self.home / 'patches'
        self.patches.mkdir()
        (self.patches / 'demo.patch').write_text(PATCH)
        self.files = {
            'mods/demo/main.js': 'export const answer = 1;\n',
            'mods/demo/KEYS.json': json.dumps({'layout:demo': {'ctrl-shift-j': 'layout.toggle:place'},
                                               'global': {'ctrl-shift-b': 'something.else'}}),
            'layouts/demo.json': '{"id": "root"}\n',
            'README.md': 'not installed\n',
        }
        self.sha = make_tarball(self.cache / f'demo-{COMMIT}.tar.gz', self.files)

    def tearDown(self):
        self.tmp.cleanup()

    def spec(self, **extra):
        spec = {
            'home': str(self.home), 'app_home': str(self.app), 'cache_dir': str(self.cache),
            'patches_dir': str(self.patches), 'claude_accounts': [], 'statusline_refresh': 60,
            'sources': [{'name': 'demo', 'commit': COMMIT, 'sha256': self.sha, 'patch': 'demo.patch',
                         'keys': 'mods/demo/KEYS.json', 'paths': ['mods/demo', 'layouts/demo.json']}],
        }
        spec.update(extra)
        return spec

    def run_helper(self, spec, check=False, ok=True):
        args = [sys.executable, '-I', str(HELPER), '--spec', json.dumps(spec)] + (['--check'] if check else [])
        done = subprocess.run(args, capture_output=True, text=True, timeout=60)
        if ok:
            self.assertEqual(done.returncode, 0, done.stderr)
            return json.loads(done.stdout)
        self.assertEqual(done.returncode, 1)
        return done.stderr

    def test_installs_listed_paths_with_patch_and_is_idempotent(self):
        first = self.run_helper(self.spec())
        self.assertTrue(first['changed'])
        self.assertEqual((self.app / 'mods/demo/main.js').read_text(), 'export const answer = 2;\n')
        self.assertEqual((self.app / 'mods/demo/extra.js').read_text(), 'export const extra = true;\n')
        self.assertTrue((self.app / 'layouts/demo.json').is_file())
        self.assertFalse((self.app / 'README.md').exists())
        second = self.run_helper(self.spec())
        self.assertFalse(second['changed'], second['files'])

    def test_keys_are_added_and_conflicts_keep_the_persons_binding(self):
        result = self.run_helper(self.spec())
        keys = json.loads((self.app / 'keys.json').read_text())
        self.assertEqual(keys['layout:demo'], {'ctrl-shift-j': 'layout.toggle:place'})
        self.assertEqual(keys['global']['ctrl-shift-b'], 'layout.toggle:sidebar')
        self.assertTrue(any('ctrl-shift-b' in w for w in result['warnings']))

    def test_checksum_mismatch_writes_nothing(self):
        spec = self.spec()
        spec['sources'][0]['sha256'] = 'b' * 64
        self.assertIn('SHA256', self.run_helper(spec, ok=False))
        self.assertFalse((self.app / 'mods').exists())

    def test_links_in_installed_paths_are_refused(self):
        self.sha = make_tarball(self.cache / f'demo-{COMMIT}.tar.gz', self.files, links=[('mods/demo/evil', '/etc/passwd')])
        self.assertIn('Links', self.run_helper(self.spec(), ok=False))
        self.assertFalse((self.app / 'mods').exists())

    def test_patch_that_does_not_apply_fails_before_writing(self):
        (self.patches / 'demo.patch').write_text(PATCH.replace('answer = 1', 'answer = 9'))
        self.assertIn('patch', self.run_helper(self.spec(), ok=False))
        self.assertFalse((self.app / 'mods').exists())

    def test_a_later_bad_source_leaves_earlier_sources_unwritten(self):
        sha = make_tarball(self.cache / f'other-{COMMIT}.tar.gz', {'mods/demo/main.js': 'export const answer = 7;\n'})
        spec = self.spec()
        spec['sources'].append({'name': 'other', 'commit': COMMIT, 'sha256': sha, 'patch': 'demo.patch', 'paths': ['mods/demo']})
        self.assertIn('patch', self.run_helper(spec, ok=False))
        self.assertFalse((self.app / 'mods').exists())

    def test_check_mode_reports_without_writing(self):
        result = self.run_helper(self.spec(), check=True)
        self.assertTrue(result['changed'])
        self.assertFalse((self.app / 'mods').exists())

    def test_missing_app_home_is_a_warning(self):
        result = self.run_helper(self.spec(app_home=str(self.home / '.config/none')))
        self.assertFalse(result['changed'])
        self.assertIn('start the Herdr app', result['warnings'][0])

    def crew_spec(self, accounts):
        files = {'mods/herdr-crew-rpg/config.json': '{"language": "auto"}\n',
                 'mods/herdr-crew-rpg/claude-statusline.py': '# script\n'}
        sha = make_tarball(self.cache / f'crew-{COMMIT}.tar.gz', files)
        return self.spec(claude_accounts=accounts, sources=[
            {'name': 'crew', 'commit': COMMIT, 'sha256': sha, 'patch': '', 'paths': ['mods/herdr-crew-rpg']}])

    def test_statusline_and_crew_accounts(self):
        home_dir, b_dir, other = self.home / '.claude', self.home / '.claude-b', self.home / '.claude-c'
        for d in (home_dir, b_dir, other):
            d.mkdir()
        (home_dir / 'settings.json').write_text(json.dumps({'hooks': {'PreToolUse': []}, 'theme': 'dark'}))
        (other / 'settings.json').write_text(json.dumps({'statusLine': {'type': 'command', 'command': 'mine.sh'}}))
        accounts = [{'name': 'home', 'config_dir': str(home_dir)}, {'name': 'b', 'config_dir': str(b_dir)},
                    {'name': 'c', 'config_dir': str(other)}, {'name': 'd', 'config_dir': str(self.home / '.claude-d')}]
        (self.app / 'mods/herdr-crew-rpg').mkdir(parents=True)
        (self.app / 'mods/herdr-crew-rpg/config.json').write_text('{"language": "en"}\n')
        result = self.run_helper(self.crew_spec(accounts))

        settings = json.loads((home_dir / 'settings.json').read_text())
        self.assertEqual(settings['hooks'], {'PreToolUse': []})
        self.assertIn('herdr-crew-rpg/claude-statusline.py home', settings['statusLine']['command'])
        self.assertEqual(len(result['backups']), 1)  # the existing home settings.json
        self.assertIn('claude-statusline.py b', json.loads((b_dir / 'settings.json').read_text())['statusLine']['command'])
        self.assertEqual(json.loads((other / 'settings.json').read_text())['statusLine']['command'], 'mine.sh')
        self.assertTrue(any('account c' in w for w in result['warnings']))
        self.assertTrue(any('account d' in w for w in result['warnings']))

        config = json.loads((self.app / 'mods/herdr-crew-rpg/config.json').read_text())
        self.assertEqual(config['language'], 'en')  # the person's choice is kept
        self.assertEqual([a['id'] for a in config['claudeAccounts']], ['claude', 'claude-b', 'claude-c', 'claude-d'])
        self.assertEqual(config['claudeAccounts'][1]['name'], 'Claude B')
        self.assertEqual(config['claudeAccounts'][1]['configDir'], '~/.claude-b')
        self.assertFalse(self.run_helper(self.crew_spec(accounts))['changed'])

    def test_budgets_and_keys_the_person_added_to_an_account_are_kept(self):
        gw = self.home / '.claude-gw'
        gw.mkdir()
        (self.app / 'mods/herdr-crew-rpg').mkdir(parents=True)
        (self.app / 'mods/herdr-crew-rpg/config.json').write_text(json.dumps({'claudeAccounts': [
            {'id': 'claude-gw', 'name': 'Old', 'account': 'gw', 'configDir': '~/x', 'note': 'mine'}]}))
        spec = self.crew_spec([{'name': 'gw', 'config_dir': str(gw)}])
        spec['claude_budgets'] = {'gw': {'usd': 100, 'period': 'month'}}
        self.run_helper(spec)
        account = json.loads((self.app / 'mods/herdr-crew-rpg/config.json').read_text())['claudeAccounts'][0]
        self.assertEqual(account, {'id': 'claude-gw', 'name': 'Claude GW', 'account': 'gw', 'configDir': '~/.claude-gw',
                                   'note': 'mine', 'budgetUsd': 100, 'budgetPeriod': 'month'})
        self.assertFalse(self.run_helper(spec)['changed'])
        spec['claude_budgets'] = {'gw': {'usd': 0}}
        self.assertIn('budget', self.run_helper(spec, ok=False))

    def test_invalid_account_name_is_refused(self):
        spec = self.crew_spec([{'name': '../x', 'config_dir': str(self.home)}])
        self.assertIn('account', self.run_helper(spec, ok=False))

    CLONE_PATCH = '''diff --git a/mods/agents-titles/main.js b/mods/agents-titles/main.js
--- a/mods/agents-titles/main.js
+++ b/mods/agents-titles/main.js
@@ -1 +1 @@
-export const rows = 1;
+export const rows = 2;
'''

    def test_clone_of_a_shipped_mod_is_patched_and_kept_when_herdr_changes_it(self):
        shipped = self.app / 'mods/agents'
        shipped.mkdir(parents=True)
        (shipped / 'main.js').write_text('export const rows = 1;\n')
        (shipped / 'mod.json').write_text('{"title": "Agents"}\n')
        (self.patches / 'clone.patch').write_text(self.CLONE_PATCH)
        spec = self.spec(clones=[{'from': 'mods/agents', 'dest': 'mods/agents-titles', 'patch': 'clone.patch'}])
        self.run_helper(spec)
        self.assertEqual((self.app / 'mods/agents-titles/main.js').read_text(), 'export const rows = 2;\n')
        self.assertEqual((self.app / 'mods/agents-titles/mod.json').read_text(), '{"title": "Agents"}\n')
        self.assertEqual((shipped / 'main.js').read_text(), 'export const rows = 1;\n')
        self.assertFalse(self.run_helper(spec)['changed'])
        (shipped / 'main.js').write_text('export const rows = 5;\n')  # a Herdr update
        result = self.run_helper(spec)
        self.assertTrue(any('no longer applies' in w for w in result['warnings']))
        self.assertEqual((self.app / 'mods/agents-titles/main.js').read_text(), 'export const rows = 2;\n')

    def test_codex_terminal_title_is_added_once_and_a_persons_value_is_kept(self):
        import tomllib
        items = ['run-state', 'thread-title']
        codex = self.home / '.codex'
        codex.mkdir()
        config = codex / 'config.toml'
        config.write_text('model = "x"\n\n[tui]\nscreen_reader_detection_done = true\n\n[mcp_servers.a]\ncommand = "a"\n')
        spec = self.spec(codex_home=str(codex), codex_terminal_title=items)
        result = self.run_helper(spec)
        parsed = tomllib.loads(config.read_text())
        self.assertEqual(parsed['tui'], {'terminal_title': items, 'screen_reader_detection_done': True})
        self.assertEqual(parsed['mcp_servers'], {'a': {'command': 'a'}})
        self.assertEqual(len(result['backups']), 1)
        self.assertFalse(self.run_helper(spec)['changed'])

        config.write_text('[tui]\nterminal_title = ["project-name"]\n')
        result = self.run_helper(spec)
        self.assertEqual(config.read_text(), '[tui]\nterminal_title = ["project-name"]\n')
        self.assertTrue(any('kept' in w for w in result['warnings']))

        config.write_text('model = "x"')
        self.run_helper(spec)
        self.assertEqual(tomllib.loads(config.read_text()), {'model': 'x', 'tui': {'terminal_title': items}})

    def test_codex_title_items_are_validated(self):
        (self.home / '.codex').mkdir()
        (self.home / '.codex/config.toml').write_text('')
        spec = self.spec(codex_home=str(self.home / '.codex'), codex_terminal_title=['x"]\nevil = ["'])
        self.assertIn('identifiers', self.run_helper(spec, ok=False))


class StatuslineTest(unittest.TestCase):
    """claude-statusline.py as shipped in crew-rpg.patch (a new file there)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        mod = self.home / 'mod'
        mod.mkdir()
        subprocess.run(['git', 'apply', '-p1', '--include=mods/herdr-crew-rpg/claude-statusline.py',
                        str(ROLE / 'files/patches/crew-rpg.patch')], cwd=mod, check=True,
                       env=dict(os.environ, GIT_CEILING_DIRECTORIES=str(self.home)))
        self.script = mod / 'mods/herdr-crew-rpg/claude-statusline.py'
        (self.script.parent / 'config.json').write_text(json.dumps({'claudeAccounts': [
            {'account': 'home', 'configDir': '~/.claude'}, {'account': 'b', 'configDir': '~/.claude-b'}]}))

    def tearDown(self):
        self.tmp.cleanup()

    def send(self, five, config_dir, arg='home'):
        env = {k: v for k, v in os.environ.items() if k not in ('HC_TERMINAL_ID', 'CLAUDE_CONFIG_DIR')}
        env['HOME'] = str(self.home)
        if config_dir:
            env['CLAUDE_CONFIG_DIR'] = str(self.home / config_dir)
        payload = {'rate_limits': {'five_hour': five}} if five else {'rate_limits': {}}
        subprocess.run([sys.executable, '-I', str(self.script), arg], input=json.dumps(payload),
                       text=True, env=env, check=True, timeout=30)

    def five(self, account):
        path = self.home / f'.cache/agent-crew/claude-{account}.json'
        return json.loads(path.read_text())['five_hour'] if path.exists() else None

    def test_account_comes_from_the_process_config_dir(self):
        self.send({'used_percentage': 35, 'resets_at': 1000}, '.claude-b', arg='home')
        self.assertEqual(self.five('b')['used_percentage'], 35)
        self.assertIsNone(self.five('home'))
        self.send({'used_percentage': 55, 'resets_at': 900}, None, arg='b')
        self.assertEqual(self.five('home')['used_percentage'], 55)

    def test_idle_sessions_never_bring_back_older_numbers(self):
        self.send({'used_percentage': 35, 'resets_at': 1000}, '.claude-b')
        self.send({'used_percentage': 6, 'resets_at': 1000}, '.claude-b')   # same window, stale
        self.assertEqual(self.five('b')['used_percentage'], 35)
        self.send({'used_percentage': 2, 'resets_at': 20000}, '.claude-b')  # newer window
        self.assertEqual(self.five('b')['used_percentage'], 2)
        self.send({'used_percentage': 40, 'resets_at': 1000}, '.claude-b')  # an old window again
        self.assertEqual(self.five('b')['used_percentage'], 2)
        self.send(None, '.claude-b')                                       # no limits in this update
        self.assertEqual(self.five('b')['used_percentage'], 2)


class ShippedFilesTest(unittest.TestCase):
    def test_patches_are_well_formed(self):
        for patch in sorted((ROLE / 'files/patches').glob('*.patch')):
            done = subprocess.run(['git', 'apply', '--stat', str(patch)], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, patch.name + ': ' + done.stderr)

    def test_mala_layout_uses_the_titles_copies_and_quota_only_crew(self):
        layout = json.loads((ROLE / 'files/layouts/mala.json').read_text())

        def blocks(node):
            yield node
            for child in node.get('children', []):
                yield from blocks(child)
        contents = [n.get('content') for n in blocks(layout)]
        self.assertIn({'mod': 'herdr-crew-rpg', 'props': {'quotaOnly': True, 'block': 'crew'}}, contents)
        for mod in ('agents-titles', 'spaces-titles', 'tabs-titles'):
            self.assertIn({'mod': mod}, contents)
        self.assertEqual(layout['cloned_from']['name'], 'main')

    @unittest.skipUnless((Path.home() / '.config/herdr-app/mods/agents/main.js').is_file(), 'Herdr app not installed here')
    def test_titles_patches_apply_to_this_herdr(self):
        for mod in ('agents', 'spaces', 'tabs'):
            with self.subTest(mod), tempfile.TemporaryDirectory() as stage:
                dest = Path(stage) / f'mods/{mod}-titles'
                dest.mkdir(parents=True)
                for f in (Path.home() / f'.config/herdr-app/mods/{mod}').iterdir():
                    if f.is_file():
                        dest.joinpath(f.name).write_bytes(f.read_bytes())
                done = subprocess.run(['git', 'apply', '--check', '-p1', str(ROLE / f'files/patches/{mod}-titles.patch')],
                                      cwd=stage, capture_output=True, text=True, env=dict(os.environ, GIT_CEILING_DIRECTORIES=stage))
                self.assertEqual(done.returncode, 0, done.stderr)


if __name__ == '__main__':
    unittest.main()
