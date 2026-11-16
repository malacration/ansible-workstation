from pathlib import Path
p=Path('ai/tests/test_sync_mcps.py');s=p.read_text().replace('sync.DEFAULT_PROFILES, **kwargs', "['code_supervisor', 'developer', 'reviewer'], **kwargs").replace("f'ai_stack_{client}_{base}.md'", "f'mala_{base}_{client}.md'").replace('ai_stack_codex_developer', 'mala_developer_codex').replace('ai_stack_claude_reviewer', 'mala_reviewer_claude').replace('ai_stack_codex_old.md', 'mala_old_codex.md').replace('ai_stack_codex_custom.md', 'mala_custom_codex.md').replace('another_codex_old.md', 'another_old_codex.md');s=s.replace("self.assertIn('agent_name: mala_developer_codex', codex.content)", "self.assertIn('mala_developer_codex', codex.content)").replace("self.assertIn('agent_name: mala_reviewer_claude', claude.content)", "self.assertIn('mala_reviewer_claude', claude.content)")
s=s.replace("        self.assertTrue(self.run_sync(check=True, prune=True)['changed'])", "        preview = self.run_sync(check=True, prune=True)\n        self.assertTrue(preview['changed'])\n        self.assertEqual(preview['removed'], [str(old)])")
pos=s.index('\n\nclass CaoCompatibilityTests')
s=s[:pos]+'''
    def test_prune_symlink_other_clients_legacy_and_binary(self):
        self.store.mkdir(parents=True)
        target = self.home / 'target'
        target.write_text(sync.MARKER)
        link = self.store / 'mala_old_codex.md'
        link.symlink_to(target)
        unselected = self.store / 'mala_old_claude.md'
        unselected.write_text(sync.MARKER)
        old = self.store / 'ai_stack_codex_developer.md'
        old.write_bytes(b'\\xff' + sync.MARKER.encode())
        with patch.object(sync, 'client_servers', return_value={}):
            result = sync.synchronize(self.home, ['codex'], ['developer'], prune=True,
                                      prune_prefixes=['ai_stack'])
        self.assertEqual(result['removed'], [str(old)])
        self.assertTrue(link.is_symlink())
        self.assertTrue(target.exists())
        self.assertTrue(unselected.exists())

    def test_cli_options(self):
        definitions = self.home / 'definitions'
        definitions.mkdir()
        (definitions / 'custom.md').write_text('---\\ndescription: Test\\n---\\nPrompt')
        self.store.mkdir(parents=True)
        old = self.store / 'ai_stack_codex_developer.md'
        old.write_text(sync.MARKER)
        result = subprocess.run([sys.executable, str(SCRIPT), '--home', str(self.home),
            '--base-dir', str(definitions), '--clients', 'claude_code', '--profiles', 'custom',
            '--prune', '--prune-prefix', 'ai_stack', '--check'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['removed'], [str(old)])
        self.assertTrue(old.exists())


class RenderedProfilesTests(unittest.TestCase):
    def test_all_definitions_render_and_validate(self):
        import yaml
        from jinja2 import Environment, FileSystemLoader
        from cli_agent_orchestrator.models.agent_profile import AgentProfile
        role = SCRIPT.parents[1]
        defaults = yaml.safe_load((role / 'defaults/main.yml').read_text())
        env = Environment(loader=FileSystemLoader(role / 'templates'))
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[2] / 'tasks/tiered-agent-profiles') as temp:
            home = Path(temp)
            definitions = home / 'definitions'
            definitions.mkdir()
            for item in defaults['cao_profile_definitions']:
                template = env.get_template('profiles/' + item['template'] + '.md.j2')
                (definitions / (item['name'] + '.md')).write_text(template.render(
                    item=item, cao_profile_efforts=defaults['cao_profile_efforts'],
                    cao_profile_models=defaults['cao_profile_models']))
            legacy = home / sync.RELATIVE_STORE / 'ai_stack_codex_developer.md'
            legacy.parent.mkdir(parents=True)
            legacy.write_text(sync.MARKER)
            result = sync.synchronize(home, list(sync.CLIENT_LABELS), sync.DEFAULT_PROFILES,
                                      base_dir=definitions, prune=True, prune_prefixes=['ai_stack'])
            self.assertEqual(result['removed'], [str(legacy)])
            paths = sorted(legacy.parent.glob('*.md'))
            self.assertEqual(len(paths), 12)
            for path in paths:
                profile = frontmatter.load(path)
                AgentProfile.model_validate(profile.metadata)
                self.assertEqual(sum(name in profile.metadata for name in ('codexConfig', 'claudeConfig')), 1)
                if 'supervisor' in path.name:
                    self.assertIn('fs_write', profile['allowedTools'])
                if 'reviewer' in path.name:
                    self.assertIn('execute_bash', profile['allowedTools'])
                    self.assertIn('fs_write', profile['allowedTools'])
                if 'developer' in path.name and path.stem.endswith('_claude'):
                    self.assertEqual(profile['model'], 'opus')
                self.assertIn('mala_supervisor_claude', profile.content)
                self.assertIn('mala_supervisor_codex', profile.content)
            self.assertFalse(sync.synchronize(home, list(sync.CLIENT_LABELS), sync.DEFAULT_PROFILES,
                base_dir=definitions, prune=True, prune_prefixes=['ai_stack'])['changed'])

'''+s[pos:];p.write_text(s)
