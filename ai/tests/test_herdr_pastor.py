"""herdr-pastor: role wiring (isolated HOME) and script behavior against a fake herdr."""

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest


ROLE = Path(__file__).resolve().parents[1] / 'roles/herdr'

PLAY = '''---
- hosts: localhost
  connection: local
  gather_facts: false
  vars_files: [defaults.yml, vars.json]
  tasks:
    - ansible.builtin.include_tasks: pastor.yml
'''

# Records argv (without the global --session) and mimics herdr 0.9.5 responses
# observed on the real binary: workspace create -> .result.root_pane,
# pane split -> .result.pane, agent start exit 2 for an unknown kind and exit 1
# with agent_not_ready when the agent waits on a startup dialog.
FAKE_HERDR = r'''#!PYTHON
import json, os, sys
from pathlib import Path

state = Path(os.environ['FAKE_HERDR_STATE'])
argv = sys.argv[1:]
session = None
if argv[:1] == ['--session']:
    session, argv = argv[1], argv[2:]
with open(state / 'calls.jsonl', 'a') as log:
    log.write(json.dumps({'session': session, 'argv': argv}) + '\n')

def reply(result, code=0):
    print(json.dumps({'id': 'cli:fake', 'result': result}, ensure_ascii=False, separators=(',', ':')))
    sys.exit(code)

running = state / ('running-' + (session or 'default'))
if argv == ['status', 'server', '--json']:
    up = running.exists() or not (state / 'stopped').exists()
    print(json.dumps({'status': 'running' if up else 'not_running', 'running': up}, separators=(',', ':')))
    sys.exit(0)
if argv == ['server']:
    running.touch()
    sys.exit(0)
if argv[:2] == ['workspace', 'create']:
    reply({'type': 'workspace_created',
           'root_pane': {'pane_id': 'w7:p1', 'tab_id': 'w7:t1', 'workspace_id': 'w7'},
           'tab': {'tab_id': 'w7:t1', 'workspace_id': 'w7'},
           'workspace': {'workspace_id': 'w7', 'label': 'x'}})
if argv[:2] == ['pane', 'split']:
    counter = state / 'panes'
    number = int(counter.read_text()) + 1 if counter.exists() else 2
    counter.write_text(str(number))
    reply({'type': 'pane_info', 'pane': {'pane_id': 'w7:p%d' % number, 'workspace_id': 'w7'}})
if argv[:2] == ['agent', 'start']:
    kind = argv[argv.index('--kind') + 1]
    if kind not in ('claude', 'codex'):
        print('unsupported interactive agent kind: ' + kind, file=sys.stderr)
        sys.exit(2)
    if kind == 'codex':
        print(json.dumps({'id': 'cli:agent:start', 'error': {'code': 'agent_not_ready',
              'message': 'agent is blocked during startup'}}), file=sys.stderr)
        sys.exit(1)
    reply({'type': 'agent_info'})
if argv[:1] in (['pane'], ['agent'], ['workspace']):
    reply({'type': 'ok'})
if argv == []:
    sys.exit(0)  # attach
print('fake herdr: unexpected ' + ' '.join(argv), file=sys.stderr)
sys.exit(3)
'''


def run_play(root, home, overrides=None, check=False):
    variables = {
        'ai_stack_home': str(home), 'ai_stack_bin_dir': str(home / 'bin'),
        'ai_stack_user': 'test', 'ansible_facts': {'user_id': 'test'},
        'ai_stack_environment': {'HOME': str(home)}, 'herdr_binary': str(home / 'bin/herdr'),
    }
    variables.update(overrides or {})
    (root / 'vars.json').write_text(json.dumps(variables))
    command = ['ansible-playbook', '-i', 'localhost,', str(root / 'play.yml')]
    if check:
        command.append('--check')
    return subprocess.run(command, env=dict(os.environ, HOME=str(home)), text=True,
                          capture_output=True, timeout=90)


def prepare_play(root):
    (root / 'templates').symlink_to(ROLE / 'templates', target_is_directory=True)
    (root / 'pastor.yml').write_text((ROLE / 'tasks/pastor.yml').read_text())
    (root / 'defaults.yml').write_text((ROLE / 'defaults/main.yml').read_text())
    (root / 'play.yml').write_text(PLAY)


class RoleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        prepare_play(self.root)
        self.script = self.home / 'bin/herdr-pastor'

    def test_check_install_idempotence_and_removal(self):
        result = run_play(self.root, self.home, check=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.script.exists())

        result = run_play(self.root, self.home)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(stat.S_IMODE(self.script.stat().st_mode), 0o755)
        text = self.script.read_text()
        self.assertIn("SHEEP='claude codex'", text)
        self.assertIn("EDITOR_SHARE=0.65", text)
        self.assertIn(str(self.home / 'bin/herdr'), text)
        self.assertNotIn('{{', text)

        result = run_play(self.root, self.home)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'changed=0\s')

        disabled = {'herdr_pastor_enabled': False}
        result = run_play(self.root, self.home, disabled, check=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.script.exists())
        result = run_play(self.root, self.home, disabled)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.script.exists())
        # The role never creates herdr runtime state or config.
        self.assertFalse((self.home / '.config/herdr').exists())

    def test_invalid_sheep_is_rejected(self):
        result = run_play(self.root, self.home, {'herdr_pastor_sheep': ['claude; rm -rf ~']})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('herdr_pastor_sheep', result.stdout)
        self.assertFalse(self.script.exists())


class ScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        home = root / 'home'
        home.mkdir()
        prepare_play(root)
        # ghost is never on PATH; mytool is not a herdr agent kind.
        result = run_play(root, home, {'herdr_pastor_sheep': ['claude', 'ghost', 'mytool', 'codex']})
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.script = home / 'bin/herdr-pastor'

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.state = self.root / 'state'
        self.state.mkdir()
        self.fakebin = self.root / 'fakebin'
        self.fakebin.mkdir()
        self.project = self.root / 'meu projeto'
        self.project.mkdir()
        fake = self.fakebin / 'herdr'
        fake.write_text(FAKE_HERDR.replace('PYTHON', sys.executable, 1))
        fake.chmod(0o755)
        for tool in ('claude', 'codex', 'mytool'):
            path = self.fakebin / tool
            path.write_text('#!/bin/sh\nexit 0\n')
            path.chmod(0o755)

    def run_script(self, *args, env=None):
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith('HERDR_') and key not in ('VISUAL', 'EDITOR')}
        environment.update(PATH=str(self.fakebin) + ':/usr/bin:/bin', FAKE_HERDR_STATE=str(self.state),
                           EDITOR='myeditor', LC_ALL='pt_BR.UTF-8')  # decimal comma locale
        environment.update(env or {})
        result = subprocess.run([str(self.script), *args], cwd=self.project, env=environment,
                                text=True, capture_output=True, timeout=30)
        log = self.state / 'calls.jsonl'
        calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        return result, calls

    def expected(self, project):
        return [
            ['status', 'server', '--json'],
            ['workspace', 'create', '--cwd', project, '--label', '🧑‍🌾 meu projeto', '--focus'],
            ['pane', 'rename', 'w7:p1', '🧑‍🌾 pastor'],
            ['pane', 'run', 'w7:p1', 'myeditor'],
            ['pane', 'split', 'w7:p1', '--direction', 'right', '--ratio', '0.65', '--cwd', project, '--no-focus'],
            ['pane', 'rename', 'w7:p2', '🐑 claude'],
            ['agent', 'start', 'claude-w7', '--kind', 'claude', '--pane', 'w7:p2'],
            ['pane', 'split', 'w7:p2', '--direction', 'down', '--ratio', '0.3333', '--cwd', project, '--no-focus'],
            ['pane', 'rename', 'w7:p3', '🐑 mytool'],
            ['agent', 'start', 'mytool-w7', '--kind', 'mytool', '--pane', 'w7:p3'],
            ['pane', 'run', 'w7:p3', 'mytool'],
            ['pane', 'split', 'w7:p3', '--direction', 'down', '--ratio', '0.5000', '--cwd', project, '--no-focus'],
            ['pane', 'rename', 'w7:p4', '🐑 codex'],
            ['agent', 'start', 'codex-w7', '--kind', 'codex', '--pane', 'w7:p4'],
            ['pane', 'focus', '--direction', 'left', '--pane', 'w7:p2'],
        ]

    def test_layout_sequence_outside_herdr_attaches_default_session(self):
        result, calls = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([call['argv'] for call in calls],
                         self.expected(str(self.project)) + [[]])
        self.assertEqual({call['session'] for call in calls}, {'default'})
        # Missing sheep is a warning, not a failure; agent_not_ready is reported.
        self.assertIn("ovelha 'ghost' ignorada", result.stderr)
        self.assertNotIn('🐑 ghost', json.dumps(calls, ensure_ascii=False))
        self.assertIn("'codex' iniciado, aguardando interação", result.stderr)

    def test_session_option_is_propagated_to_every_call(self):
        for args in (['--session', 'meu'], ['--session=meu']):
            with self.subTest(args=args):
                (self.state / 'calls.jsonl').unlink(missing_ok=True)
                (self.state / 'panes').unlink(missing_ok=True)
                result, calls = self.run_script(*args, str(self.project))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual({call['session'] for call in calls}, {'meu'})
                self.assertEqual(calls[-1]['argv'], [])

    def test_visual_wins_and_directory_argument(self):
        other = self.root / 'outro'
        other.mkdir()
        result, calls = self.run_script('--no-attach', '--', str(other), env={'VISUAL': 'nvim -p'})
        self.assertEqual(result.returncode, 0, result.stderr)
        argv = [call['argv'] for call in calls]
        self.assertIn(['pane', 'run', 'w7:p1', 'nvim -p'], argv)
        self.assertIn(['workspace', 'create', '--cwd', str(other), '--label', '🧑‍🌾 outro', '--focus'], argv)
        self.assertNotIn([], argv)
        self.assertIn('herdr --session default', result.stderr)

    def test_inside_cao_session_targets_default_without_attach(self):
        result, calls = self.run_script(env={'HERDR_PANE_ID': 'w2:p2', 'HERDR_SESSION': 'cao',
                                             'HERDR_SOCKET_PATH': '/nonexistent/cao.sock'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({call['session'] for call in calls}, {'default'})
        self.assertEqual([call['argv'] for call in calls], self.expected(str(self.project)))
        self.assertIn("criado na sessão 'default'", result.stderr)

    def test_inside_other_session_stays_there(self):
        result, calls = self.run_script(env={'HERDR_PANE_ID': 'w1:p1', 'HERDR_SESSION': 'work'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({call['session'] for call in calls}, {'work'})
        self.assertNotIn([], [call['argv'] for call in calls])
        self.assertNotIn('anexe', result.stderr)

    def test_starts_headless_server_when_not_running(self):
        (self.state / 'stopped').touch()
        result, calls = self.run_script('--session', 'nova', '--no-attach')
        self.assertEqual(result.returncode, 0, result.stderr)
        argv = [call['argv'] for call in calls]
        self.assertIn(['server'], argv)
        self.assertLess(argv.index(['server']), argv.index(self.expected(str(self.project))[1]))
        self.assertEqual({call['session'] for call in calls}, {'nova'})

    def test_no_sheep_available_keeps_only_editor(self):
        for tool in ('claude', 'codex', 'mytool'):
            (self.fakebin / tool).unlink()
        result, calls = self.run_script('--no-attach')
        self.assertEqual(result.returncode, 0, result.stderr)
        argv = [call['argv'] for call in calls]
        self.assertEqual(argv, self.expected(str(self.project))[:4])

    def test_help_and_errors_do_not_call_herdr(self):
        result, calls = self.run_script('--help')
        self.assertEqual(result.returncode, 0)
        self.assertIn('Uso: herdr-pastor', result.stdout)
        for args, code in ((['--bogus'], 2), (['--session'], 2), (['a', 'b'], 2),
                           ([str(self.root / 'missing')], 1)):
            result, _ = self.run_script(*args)
            self.assertEqual(result.returncode, code, (args, result.stderr))
        self.assertEqual(calls, [])
        self.assertFalse((self.state / 'calls.jsonl').exists())


if __name__ == '__main__':
    unittest.main()
