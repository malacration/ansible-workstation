"""Mirror the user-scope MCP servers of ~/.claude.json into extra Claude Code accounts.

CAO workers already get these servers from their profiles, but an interactive
`claude-<account>` session reads only <config_dir>/.claude.json. Changes go through
`claude mcp remove/add-json --scope user` (with CLAUDE_CONFIG_DIR set) so running Claude Code
sessions keep owning their file. Servers with env values or headers (possible secrets) go
through stdin, which Claude Code refuses inside one of its own sessions; run the playbook
from a plain terminal for those. Others go as an argument. Nothing is printed. Servers that
exist only in the account are left alone.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def user_servers(config_file):
    if not config_file.exists():
        return {}
    try:
        config = json.loads(config_file.read_text(encoding='utf-8'))
    except (ValueError, UnicodeError):
        raise ValueError(f'Configuração do Claude inválida: {config_file}') from None
    if not isinstance(config, dict):
        raise ValueError(f'A configuração deve ser um objeto: {config_file}')
    servers = config.get('mcpServers') or {}
    if not isinstance(servers, dict):
        raise ValueError(f'mcpServers deve ser um objeto em {config_file}')
    disabled = set(config.get('disabledMcpServers') or [])
    return {name: entry for name, entry in servers.items()
            # The session coordinator belongs to CAO profiles, never to an interactive client.
            if name != 'cao-mcp-server' and name not in disabled and isinstance(entry, dict)}


def may_hold_secrets(entry):
    return bool(entry.get('env')) or bool(entry.get('headers'))


def run_claude(claude, config_dir, args, stdin=None):
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(config_dir))
    result = subprocess.run([claude, 'mcp', *args, '--scope', 'user'], input=stdin, env=env,
                            capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        # Only the server name is reported; stdout/stderr may echo the configuration.
        raise ValueError(f'claude mcp {args[0]} {args[1]} falhou na conta {config_dir}')


def synchronize(home, accounts, claude, check=False):
    source = user_servers(home / '.claude.json')
    report = {'changed': False, 'check': check, 'servers': sorted(source), 'accounts': {}}
    for config_dir in accounts:
        current = user_servers(config_dir / '.claude.json')
        pending = sorted(name for name, entry in source.items() if current.get(name) != entry)
        report['accounts'][str(config_dir)] = pending
        report['changed'] = report['changed'] or bool(pending)
        if check:
            continue
        for name in pending:
            if name in current:
                run_claude(claude, config_dir, ['remove', name])
            payload = json.dumps(source[name])
            if may_hold_secrets(source[name]):
                run_claude(claude, config_dir, ['add-json', name, '-'], stdin=payload)
            else:
                run_claude(claude, config_dir, ['add-json', name, payload])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--claude', default='claude')
    parser.add_argument('--account-dir', type=Path, action='append', default=[])
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        if any(not path.is_absolute() for path in args.account_dir):
            raise ValueError('Use diretórios absolutos para as contas Claude')
        result = synchronize(args.home, args.account_dir, args.claude, args.check)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f'Falha ao sincronizar MCPs das contas Claude: {error}', file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
