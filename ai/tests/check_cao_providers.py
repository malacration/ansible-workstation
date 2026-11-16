"""Exercise CAO's actual profile loader and launch configuration, without agents."""

import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile


def main():
    with tempfile.TemporaryDirectory(prefix='ai-stack-providers-') as temporary:
        home = Path(temporary)
        # CAO reads these at import time. Isolate its settings and runtime files.
        os.environ['HOME'] = str(home)
        os.environ['CAO_HOME_DIR'] = str(home / '.aws/cli-agent-orchestrator')
        os.environ['CAO_TERMINAL_ID'] = 'mcp-config-test'
        (home / '.codex').mkdir()
        (home / '.codex/config.toml').write_text(
            '[mcp_servers.chrome-devtools]\ncommand = "/usr/bin/true"\n'
            'args = ["--headless"]\n'
            '[mcp_servers.clickup]\nurl = "https://mcp.clickup.com/mcp"\n'
        )
        (home / '.claude.json').write_text(json.dumps({'mcpServers': {
            'chrome-devtools': {'command': '/usr/bin/true', 'args': ['--headless']},
            'clickup': {'type': 'http', 'url': 'https://mcp.clickup.com/mcp'},
        }}))
        originals = {path: path.read_bytes() for path in (
            home / '.codex/config.toml', home / '.claude.json',
        )}
        script = Path(__file__).parents[1] / 'roles/cao/files/sync_mcps.py'
        spec = importlib.util.spec_from_file_location('sync_mcps', script)
        sync = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sync)
        import yaml
        from jinja2 import Environment, FileSystemLoader
        role = script.parents[1]
        defaults = yaml.safe_load((role / 'defaults/main.yml').read_text())
        env = Environment(loader=FileSystemLoader(role / 'templates'))
        env.filters['to_json'] = json.dumps
        defaults['cao_profile_models']['developer_high']['codex'] = 'test-model-id'
        definitions = home / 'definitions'
        definitions.mkdir()
        for item in defaults['cao_profile_definitions']:
            template = env.get_template('profiles/' + item['template'] + '.md.j2')
            (definitions / (item['name'] + '.md')).write_text(template.render(
                item=item, cao_profile_efforts=defaults['cao_profile_efforts'],
                cao_profile_models=defaults['cao_profile_models']))
        assert sync.synchronize(home, ['codex', 'claude_code'], sync.DEFAULT_PROFILES,
                                base_dir=definitions)['changed']

        from cli_agent_orchestrator.utils.agent_profiles import load_agent_profile
        from cli_agent_orchestrator.providers.codex import CodexProvider
        from cli_agent_orchestrator.providers.claude_code import ClaudeCodeProvider

        for client in ('codex', 'claude'):
            for base in sync.DEFAULT_PROFILES:
                profile = load_agent_profile(f'mala_{base}_{client}')
                assert {'cao-mcp-server', 'chrome-devtools'} <= set(profile.mcpServers)
                if client == 'codex':
                    assert 'clickup' not in profile.mcpServers
                    assert '@clickup' in profile.allowedTools
                else:
                    assert 'clickup' in profile.mcpServers

        codex = CodexProvider(
            'mcp-config-test', 'test', 'test', agent_profile='mala_supervisor_codex',
        )
        codex_command = codex._build_codex_command()
        assert 'mcp_servers.chrome-devtools.command' in codex_command
        assert 'mcp_servers.cao-mcp-server.command' in codex_command
        assert 'mcp_servers.clickup.' not in codex_command
        # Validate with the actual Codex configuration parser when available.
        # mcp get reads configuration without starting a session or an MCP.
        codex_binary = shutil.which('codex')
        if codex_binary:
            environment = dict(os.environ, CODEX_HOME=str(home / '.codex'))
            failure = subprocess.run(
                [codex_binary, '-c', 'mcp_servers.clickup.env_vars=["CAO_TERMINAL_ID"]',
                 'mcp', 'get', 'clickup', '--json'],
                env=environment, capture_output=True, text=True, timeout=30,
            )
            assert failure.returncode != 0
            assert 'env_vars is not supported for streamable_http' in failure.stderr
            words = shlex.split(codex_command)
            overrides = []
            for index, word in enumerate(words[:-1]):
                if word == '-c' and words[index + 1].startswith('mcp_servers.'):
                    overrides.extend(['-c', words[index + 1]])
            success = subprocess.run(
                [codex_binary, *overrides, 'mcp', 'get', 'clickup', '--json'],
                env=environment, capture_output=True, text=True, timeout=30,
            )
            assert success.returncode == 0, success.stderr
            entry = json.loads(success.stdout)
            assert entry['transport']['type'] == 'streamable_http'
            assert entry['transport']['url'] == 'https://mcp.clickup.com/mcp'
        codex_developer = CodexProvider(
            'mcp-config-test', 'test', 'test', agent_profile='mala_developer_high_codex',
        )
        codex_words = shlex.split(codex_developer._build_codex_command())
        overrides = [codex_words[i + 1] for i, word in enumerate(codex_words[:-1]) if word == '-c']
        assert 'model="test-model-id"' in overrides, overrides
        assert 'model_reasoning_effort="high"' in overrides, overrides
        claude_developer = ClaudeCodeProvider(
            'mcp-config-test', 'test', 'test', agent_profile='mala_developer_high_claude',
        )
        developer_words = shlex.split(claude_developer._build_claude_command())
        assert developer_words[developer_words.index('--model') + 1] == 'opus'
        assert developer_words[developer_words.index('--effort') + 1] == 'high'

        claude = ClaudeCodeProvider(
            'mcp-config-test', 'test', 'test', agent_profile='mala_supervisor_claude',
        )
        words = shlex.split(claude._build_claude_command())
        assert '--strict-mcp-config' in words
        config_arg = words[words.index('--mcp-config') + 1]
        config_path = Path(config_arg)
        # Supported CAO releases use either a file or an inline JSON argument.
        config = json.loads(config_arg) if config_arg.startswith('{') else json.loads(config_path.read_text())
        servers = config['mcpServers']
        assert servers['clickup']['url'] == 'https://mcp.clickup.com/mcp'
        assert servers['chrome-devtools']['command'] == '/usr/bin/true'
        assert servers['cao-mcp-server']['env']['CAO_TERMINAL_ID'] == 'mcp-config-test'
        for path, data in originals.items():
            assert path.read_bytes() == data
        assert not sync.synchronize(home, ['codex', 'claude_code'], sync.DEFAULT_PROFILES, base_dir=definitions)['changed']


if __name__ == '__main__':
    main()
