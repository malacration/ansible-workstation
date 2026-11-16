"""Offline tests using disposable uv tools and local wheel/Git fixtures only."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from unittest.mock import patch
import zipfile

import packaging


SCRIPT = Path(__file__).parents[1] / 'roles/cao/files/install_cao.py'
SPEC = importlib.util.spec_from_file_location('install_cao', SCRIPT)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


def wheel(directory, name, version, revision='release'):
    path = directory / f'{name}-{version}-py3-none-any.whl'
    metadata = f'{name}-{version}.dist-info'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(f'{name}.py', f'REVISION = {revision!r}\ndef main(): pass\n')
        archive.writestr(f'{metadata}/METADATA',
                         f'Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n'
                         'Provides-Extra: memory\nProvides-Extra: ui\n')
        archive.writestr(f'{metadata}/WHEEL',
                         'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
        archive.writestr(f'{metadata}/entry_points.txt',
                         f'[console_scripts]\n{name} = {name}:main\n')
        archive.writestr(f'{metadata}/RECORD', '')
    return path


def parser_wheel(directory):
    """Expose the existing parser source to offline uv-run fixture resolution."""
    path = wheel(directory, 'packaging', packaging.__version__)
    package = Path(packaging.__file__).parent
    with zipfile.ZipFile(path, 'a') as archive:
        for source in package.rglob('*.py'):
            archive.write(source, 'packaging/' + str(source.relative_to(package)))
    return path


class ReceiptTests(unittest.TestCase):
    def test_requirement_aliases_extras_and_specifiers_compare_semantically(self):
        canonical = installer.normalized_requirement('fixture-plugin[local-extra]>=1,==1.0')
        for alias in ['FiXtUrE_PlUgIn [LOCAL_Extra] ( == 1.0.0, >= 1.0 )',
                      'fixture...plugin[local.extra]==1.0,>=1']:
            with self.subTest(alias=alias):
                parsed = installer.normalized_requirement(alias)
                self.assertEqual(parsed, canonical)
                self.assertEqual(hash(parsed), hash(canonical))

    def test_unknown_receipt_resolution_state_is_rejected(self):
        for state in [{'constraints': [{'name': 'plugin', 'specifier': '==1.0'}]},
                      {'overrides': [{'name': 'plugin', 'specifier': '==1.0'}]},
                      {'options': {'resolution': 'lowest'}},
                      {'options': {'index-url': 'https://example.org/simple'}},
                      {'future-resolution-field': ['nonempty']}]:
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, 'Unsupported'):
                installer.receipt_options({'tool': {'requirements': [], **state}})

    def test_pinned_requirement_with_extra_and_marker(self):
        self.assertEqual(installer.requirement_text({
            'name': 'plugin', 'specifier': '==1.0', 'extras': ['local'],
            'marker': 'python_version >= "3.11"',
        }), 'plugin[local]==1.0; python_version >= "3.11"')

    def test_direct_sources(self):
        for key, source, expected in [
            ('url', 'https://example.org/plugin.whl', 'https://example.org/plugin.whl'),
            ('path', '/tmp/plugin dir', 'file:///tmp/plugin%20dir'),
            ('git', 'https://example.org/plugin.git@main',
             'git+https://example.org/plugin.git@main'),
            ('git', 'https://example.org/plugin.git?rev=main',
             'git+https://example.org/plugin.git@main'),
        ]:
            with self.subTest(key=key):
                self.assertEqual(installer.requirement_text({'name': 'plugin', key: source}),
                                 'plugin @ ' + expected)

    def test_unknown_or_ambiguous_fields_fail(self):
        for requirement in [
            {'name': 'plugin', 'editable': True},
            {'name': 'plugin', 'git': {'url': 'unsupported'}},
            {'name': 'plugin', 'url': 'a', 'path': 'b'},
            {'name': 'plugin', 'url': 'a', 'specifier': '==1.0'},
        ]:
            with self.subTest(requirement=requirement), self.assertRaises(ValueError):
                installer.requirement_text(requirement)


@unittest.skipUnless(shutil.which('uv') and shutil.which('git'), 'Requires uv and git')
class IsolatedInstallTests(unittest.TestCase):
    def test_install_repeat_pin_upgrade_and_git_source_preserve_extras(self):
        self.assert_install_scenarios('fixture-plugin==1.0')

    def test_auxiliary_alias_does_not_advance_branch_without_upgrade(self):
        self.assert_install_scenarios('FiXtUrE_PlUgIn ( == 1.0 )')

    def assert_install_scenarios(self, auxiliary):
        with tempfile.TemporaryDirectory(prefix='ansible-cao-test-') as directory:
            root = Path(directory)
            wheels = root / 'wheels'
            wheels.mkdir()
            wheel(wheels, 'cli_agent_orchestrator', '0.1')
            wheel(wheels, 'fixture_plugin', '1.0')
            parser_wheel(wheels)
            env = dict(os.environ, UV_TOOL_DIR=str(root / 'tools'),
                       UV_TOOL_BIN_DIR=str(root / 'bin'), UV_CACHE_DIR=str(root / 'cache'),
                       UV_PYTHON_DOWNLOADS='never', UV_OFFLINE='true',
                       UV_FIND_LINKS=str(wheels), UV_NO_CONFIG='true')
            uv = shutil.which('uv')
            config = {'spec': 'cli-agent-orchestrator==0.1', 'python': shutil.which('python3'),
                      'upgrade': False, 'extras': ['memory'],
                      'with_packages': [auxiliary]}
            with patch.dict(os.environ, env, clear=True):
                initial = installer.install(uv, config)
                self.assertTrue(initial['changed'])
                self.assertEqual(initial['with_count'], 1)
                self.assertFalse(installer.install(uv, config)['changed'])
                # Newly available versions are used only when upgrading latest.
                wheel(wheels, 'cli_agent_orchestrator', '0.2')
                config.update(extras=[], upgrade=True)
                self.assertFalse(installer.install(uv, config)['changed'])  # Pin holds.
                config.update(spec='cli-agent-orchestrator', upgrade=False)
                installer.install(uv, config)  # Remove the old constraint once.
                wheel(wheels, 'cli_agent_orchestrator', '0.3')
                self.assertFalse(installer.install(uv, config)['changed'])
                config['upgrade'] = True
                self.assertTrue(installer.install(uv, config)['changed'])
                # A Git build may retain the same version across distinct commits.
                repo = root / 'repo'
                repo.mkdir()
                (repo / 'pyproject.toml').write_text(
                    '[build-system]\nrequires=[]\nbuild-backend="backend"\nbackend-path=["."]\n')
                (repo / 'backend.py').write_text(
                    'from pathlib import Path\nimport shutil\n'
                    'def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):\n'
                    '    wheel = next(Path(__file__).parent.glob("*.whl"))\n'
                    '    shutil.copyfile(wheel, Path(wheel_directory)/wheel.name)\n'
                    '    return wheel.name\n')
                wheel(repo, 'cli_agent_orchestrator', '0.3', 'first')

                def git(*args):
                    return subprocess.check_output(['git', '-C', str(repo), *args],
                                                   text=True, stderr=subprocess.DEVNULL).strip()

                git('init', '-b', 'main')
                git('add', '.')
                git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost',
                    'commit', '-m', 'first')
                first = git('rev-parse', 'HEAD')
                config.update(spec=f'cli-agent-orchestrator @ git+{repo.as_uri()}@main',
                              upgrade=False)
                self.assertTrue(installer.install(uv, config)['changed'])
                self.assertFalse(installer.install(uv, config)['changed'])
                installed_module = next((root / 'tools').rglob('cli_agent_orchestrator.py'))
                self.assertIn("REVISION = 'first'", installed_module.read_text())
                wheel(repo, 'cli_agent_orchestrator', '0.3', 'second')
                git('add', '.')
                git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost',
                    'commit', '-m', 'second')
                self.assertFalse(installer.install(uv, config)['changed'])
                self.assertIn("REVISION = 'first'", installed_module.read_text())
                config['upgrade'] = True
                self.assertTrue(installer.install(uv, config)['changed'])
                self.assertIn("REVISION = 'second'", installed_module.read_text())
                config['spec'] = f'cli-agent-orchestrator[ui] @ git+{repo.as_uri()}@{first}'
                self.assertTrue(installer.install(uv, config)['changed'])
                self.assertFalse(installer.install(uv, config)['changed'])
                receipt_path = root / 'tools/cli-agent-orchestrator/uv-receipt.toml'
                receipt = tomllib.loads(receipt_path.read_text())['tool']['requirements']
                primary = next(r for r in receipt if r['name'] == 'cli-agent-orchestrator')
                self.assertEqual(set(primary['extras']), {'memory', 'ui'})
                plugin = next(r for r in receipt if r['name'] == 'fixture-plugin')
                self.assertEqual(plugin['specifier'], '==1.0')
                # Check the CLI boundary too; Ansible consumes only this JSON.
                result = subprocess.run([
                    shutil.which('python3'), str(SCRIPT), '--uv', uv,
                    '--config', json.dumps(config),
                ], check=True, capture_output=True, text=True)
                self.assertFalse(json.loads(result.stdout)['changed'])

                # Execute the actual Ansible script task, including its JSON
                # quoting and uv-run interpreter. No role dependencies/services.
                if shutil.which('ansible-playbook'):
                    import yaml

                    role = SCRIPT.parents[1]
                    tasks = yaml.safe_load((role / 'tasks/main.yml').read_text())
                    block = next(task['block'] for task in tasks if 'block' in task)
                    install_task = block[0]
                    playbook = root / 'isolated.yml'
                    playbook.write_text(yaml.safe_dump([{
                        'name': 'Test actual CAO installer task in isolation',
                        'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
                        'vars': {
                            'role_path': str(role), 'ai_stack_bin_dir': str(Path(uv).parent),
                            'cao_install_spec': config['spec'],
                            'cao_python_version': config['python'], 'cao_upgrade': True,
                            'cao_extras': [], 'cao_with_packages': [],
                        },
                        'tasks': [install_task],
                        'handlers': [{'name': 'Reiniciar servidor CAO',
                                      'ansible.builtin.debug': {'msg': 'fixture handler'}}],
                    }], sort_keys=False))
                    ansible_env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(root / 'ansible-local'),
                                       ANSIBLE_REMOTE_TEMP=str(root / 'ansible-remote'),
                                       ANSIBLE_NOCOLOR='1')
                    for flags in [[], ['--check']]:
                        before = receipt_path.read_bytes()
                        result = subprocess.run([
                            'ansible-playbook', '-i', 'localhost,', str(playbook), *flags,
                        ], cwd=root, env=ansible_env, capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertIn('changed=0', result.stdout)
                        self.assertEqual(receipt_path.read_bytes(), before)

    def test_stored_constraints_reject_upgrade_and_source_change_without_mutation(self):
        with tempfile.TemporaryDirectory(prefix='ansible-cao-constraints-') as directory:
            root = Path(directory)
            wheels = root / 'wheels'
            wheels.mkdir()
            wheel(wheels, 'cli_agent_orchestrator', '0.1')
            wheel(wheels, 'fixture_plugin', '1.0')
            constraint = root / 'constraints.txt'
            constraint.write_text('fixture-plugin==1.0\n')
            env = dict(os.environ, UV_TOOL_DIR=str(root / 'tools'),
                       UV_TOOL_BIN_DIR=str(root / 'bin'), UV_CACHE_DIR=str(root / 'cache'),
                       UV_PYTHON_DOWNLOADS='never', UV_OFFLINE='true',
                       UV_FIND_LINKS=str(wheels), UV_NO_CONFIG='true',
                       UV_CONSTRAINT=str(constraint))
            uv = shutil.which('uv')
            config = {'spec': 'cli-agent-orchestrator==0.1', 'python': shutil.which('python3'),
                      'upgrade': False, 'extras': [], 'with_packages': ['fixture-plugin']}
            with patch.dict(os.environ, env, clear=True):
                installer.install(uv, config)
                receipt = root / 'tools/cli-agent-orchestrator/uv-receipt.toml'
                self.assertTrue(tomllib.loads(receipt.read_text())['tool']['constraints'])
                wheel(wheels, 'fixture_plugin', '2.0')
                os.environ.pop('UV_CONSTRAINT')

                def snapshot():
                    return {str(path.relative_to(root / 'tools')): path.read_bytes()
                            for path in (root / 'tools').rglob('*') if path.is_file()}

                before = snapshot()
                for source, upgrade in [('cli-agent-orchestrator==0.1', True),
                                        ('cli-agent-orchestrator @ git+file:///unused@main', False)]:
                    config.update(spec=source, upgrade=upgrade)
                    with patch.object(installer.subprocess, 'run', wraps=subprocess.run) as run:
                        with self.assertRaisesRegex(ValueError, 'constraints'):
                            installer.install(uv, config)
                        self.assertEqual([call.args[0] for call in run.call_args_list],
                                         [[uv, 'tool', 'dir']])
                    self.assertEqual(snapshot(), before)
                self.assertTrue(list((root / 'tools').rglob('fixture_plugin-1.0.dist-info')))
                self.assertFalse(list((root / 'tools').rglob('fixture_plugin-2.0.dist-info')))


if __name__ == '__main__':
    unittest.main()
