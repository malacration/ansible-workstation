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


class ReceiptTests(unittest.TestCase):
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
        with tempfile.TemporaryDirectory(prefix='ansible-cao-test-') as directory:
            root = Path(directory)
            wheels = root / 'wheels'
            wheels.mkdir()
            wheel(wheels, 'cli_agent_orchestrator', '0.1')
            wheel(wheels, 'fixture_plugin', '1.0')
            env = dict(os.environ, UV_TOOL_DIR=str(root / 'tools'),
                       UV_TOOL_BIN_DIR=str(root / 'bin'), UV_CACHE_DIR=str(root / 'cache'),
                       UV_PYTHON_DOWNLOADS='never', UV_OFFLINE='true',
                       UV_FIND_LINKS=str(wheels), UV_NO_CONFIG='true')
            uv = shutil.which('uv')
            config = {'spec': 'cli-agent-orchestrator==0.1', 'python': shutil.which('python3'),
                      'upgrade': False, 'extras': ['memory'],
                      'with_packages': ['fixture-plugin==1.0']}
            with patch.dict(os.environ, env, clear=True):
                self.assertTrue(installer.install(uv, config)['changed'])
                self.assertFalse(installer.install(uv, config)['changed'])
                # Newly available versions are used only when upgrading latest.
                wheel(wheels, 'cli_agent_orchestrator', '0.2')
                config.update(extras=[], with_packages=[], upgrade=True)
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
                wheel(repo, 'cli_agent_orchestrator', '0.3', 'second')
                git('add', '.')
                git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost',
                    'commit', '-m', 'second')
                self.assertFalse(installer.install(uv, config)['changed'])
                config['upgrade'] = True
                self.assertTrue(installer.install(uv, config)['changed'])
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


if __name__ == '__main__':
    unittest.main()
