"""Import user MCP configurations into provider-specific CAO profiles.

Run with the Python environment installed by CAO (Python >=3.11 and frontmatter).
Client configuration files and authentication stores are never written.
"""

import argparse
from copy import deepcopy
from importlib import resources
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import tomllib

import frontmatter
import yaml


MARKER = '<!-- Managed by ai-stack-sync-mcps; regenerate instead of editing. -->'
CLIENT_LABELS = {'codex': 'codex', 'claude_code': 'claude'}
DEFAULT_PROFILES = ['supervisor', 'developer_low', 'developer_medium', 'developer_high', 'reviewer_basic', 'reviewer_advanced']
SAFE_NAME = re.compile(r'^[A-Za-z0-9_-]+$')
RELATIVE_STORE = Path('.aws/cli-agent-orchestrator/agent-store')


def read_config(path, toml=False):
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding='utf-8')
        data = tomllib.loads(text) if toml else json.loads(text)
    except (ValueError, UnicodeError):
        raise ValueError(f'Configuração MCP inválida: {path}') from None
    if not isinstance(data, dict):
        raise ValueError(f'A configuração deve ser um objeto: {path}')
    return data


def client_servers(home, client):
    if client == 'codex':
        config = read_config(home / '.codex/config.toml', toml=True)
        servers = config.get('mcp_servers', {})
        disabled = set()
    else:
        config = read_config(home / '.claude.json')
        servers = config.get('mcpServers', {})
        disabled = set(config.get('disabledMcpServers', []))
    if not isinstance(servers, dict):
        raise ValueError(f'A lista de MCPs de {client} deve ser um objeto')

    imported = {}
    for name, original in servers.items():
        # The session coordinator belongs to CAO, never to a client import.
        if name == 'cao-mcp-server' or name in disabled:
            continue
        if not isinstance(original, dict):
            raise ValueError(f'Configuração inválida do MCP {name} em {client}')
        if original.get('enabled') is False or original.get('disabled') is True:
            continue
        if client == 'codex' and not SAFE_NAME.fullmatch(name):
            raise ValueError(f'O nome do MCP {name} não é compatível com CAO/Codex')
        if not original.get('command') and not original.get('url'):
            raise ValueError(f'O MCP {name} precisa de command ou url')
        entry = deepcopy(original)
        entry.pop('enabled', None)
        entry.pop('disabled', None)
        imported[name] = entry
    return imported


def profile_definition(home, name, base_dir=None):
    local = home / RELATIVE_STORE / f'{name}.md'
    preferred = base_dir / f'{name}.md' if base_dir else None
    if preferred is not None and preferred.is_file():
        text = preferred.read_text(encoding='utf-8')
    elif local.exists():
        text = local.read_text(encoding='utf-8')
    else:
        package = resources.files('cli_agent_orchestrator.agent_store')
        resource = package / f'{name}.md'
        if not resource.is_file():
            raise ValueError(f'Definição de perfil não encontrado: {name}')
        text = resource.read_text(encoding='utf-8')
    try:
        profile = frontmatter.loads(text)
    except (ValueError, yaml.YAMLError):
        raise ValueError(f'Definição de perfil inválido: {name}') from None
    if not profile.get('description'):
        raise ValueError(f'Definição de perfil sem description: {name}')
    if not isinstance(profile.get('mcpServers', {}), dict):
        raise ValueError(f'mcpServers deve ser um objeto no perfil {name}')
    for policy in ('allowedTools', 'delegateTools'):
        value = profile.get(policy)
        if value is not None and (
            not isinstance(value, list) or any(not isinstance(tool, str) for tool in value)
        ):
            raise ValueError(f'{policy} deve ser uma lista de nomes no perfil {name}')
    return profile


def role_allowed_tools(metadata, server_names):
    # Resolve the installed CAO role, including any operator-defined role policy.
    from cli_agent_orchestrator.utils.tool_mapping import resolve_allowed_tools

    return resolve_allowed_tools(None, metadata.get('role'), server_names)


def render_profile(base, target, client, imported, names):
    metadata = deepcopy(base.metadata)
    metadata['name'] = target
    metadata['provider'] = client
    models = metadata.pop('aiStackModels', None)
    if models is None:
        models = {}
    if not isinstance(models, dict) or any(
        key not in CLIENT_LABELS.values() or (value is not None and
        (not isinstance(value, str) or not value.strip()))
        for key, value in models.items()
    ):
        raise ValueError('aiStackModels deve conter modelos válidos para codex e claude')
    model = models.get(CLIENT_LABELS[client])
    if model:
        if client == 'codex':
            metadata.setdefault('codexConfig', {})['model'] = model
        else:
            metadata['model'] = model
    if metadata.get('tags') is not None:
        effort = (metadata.get('codexConfig') or {}).get('model_reasoning_effort') if client == 'codex' else (metadata.get('claudeConfig') or {}).get('effort')
        if effort:
            metadata['tags'] = [tag for tag in metadata['tags'] if not tag.startswith('effort-')]
            metadata['tags'].append(f'effort-{effort}')
        metadata['tags'].append(CLIENT_LABELS[client])
    metadata.pop('claudeConfig' if client == 'codex' else 'codexConfig', None)
    servers = deepcopy(metadata.get('mcpServers') or {})
    coordinator = deepcopy(servers.get('cao-mcp-server') or {
        'type': 'stdio', 'command': 'cao-mcp-server', 'args': [],
    })
    servers.update(deepcopy(imported))
    servers['cao-mcp-server'] = coordinator
    server_names = list(servers)
    if client == 'codex':
        # CAO 2.5.4 adds env_vars to every declared server. Codex rejects that
        # option for HTTP transports. Inherit HTTP entries from Codex's global
        # config instead, keeping their URL, headers and OAuth configuration.
        inherited = [name for name, entry in servers.items()
                     if isinstance(entry, dict) and entry.get('url')]
        for name in inherited:
            if not imported.get(name, {}).get('url'):
                raise ValueError(f'Configure o MCP HTTP {name} no Codex global antes de sincronizar')
            del servers[name]
        if inherited and metadata.get('allowedTools') is None:
            # HTTP servers no longer appear in mcpServers, so explicitly retain
            # their grants in the effective CAO role and its delegation policy.
            metadata['allowedTools'] = role_allowed_tools(metadata, server_names)
    metadata['mcpServers'] = servers

    # Explicit policies need to name imported servers; role defaults add them
    # automatically in CAO. Keep all the other existing tool restrictions.
    for policy in ('allowedTools', 'delegateTools'):
        if metadata.get(policy) is not None and '*' not in metadata[policy]:
            grants = [f'@{name}' for name in server_names]
            metadata[policy] = list(dict.fromkeys([*metadata[policy], *grants]))

    body = base.content
    if body.startswith(MARKER):
        body = body[len(MARKER):].lstrip('\n')
    sections = []
    for provider, provider_names in names.items():
        routes = '\n'.join(f'- {original}: `{generated}`' for original, generated in provider_names.items())
        sections.append(f'### {CLIENT_LABELS[provider]}\n\n{routes}')
    body = (
        f'{MARKER}\n\n{body}\n\n'
        '## AI stack: provider and delegation\n\n'
        f'This profile runs on `{client}`. Supervisors may delegate across providers '
        'by choosing a profile below; each profile runs on its fixed provider. '
        'Only the providers listed below are installed; if the preferred provider is not listed, use a listed one and record why.\n\n'
        + '\n\n'.join(sections) + '\n'
    )
    return frontmatter.dumps(frontmatter.Post(body, **metadata)) + '\n'


def write_private(path, text):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix='.ai-stack-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
        # mkstemp creates 0600 files; replace only after a complete write.
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def synchronize(home, clients, profiles, prefix='mala', check=False, base_dir=None, prune=False, prune_prefixes=(), definitions_only=False):
    if not SAFE_NAME.fullmatch(prefix) or len(prefix) > 32:
        raise ValueError('Prefixo de perfis inválido')
    if not clients or any(client not in CLIENT_LABELS for client in clients):
        raise ValueError('Use os clientes codex e/ou claude_code')
    if not profiles or any(not SAFE_NAME.fullmatch(name) for name in profiles):
        raise ValueError('Nomes de perfis inválidos')

    if any(not SAFE_NAME.fullmatch(value) or len(value) > 32 for value in prune_prefixes):
        raise ValueError('Prefixo de remoção inválido')
    if definitions_only and (base_dir is None or any(not (base_dir / f'{name}.md').is_file() for name in profiles)):
        raise ValueError('Todas as definições de perfis devem existir no diretório configurado')
    store = home / RELATIVE_STORE
    all_names = {client: {name: f'{prefix}_{name}_{CLIENT_LABELS[client]}' for name in profiles}
                 for client in dict.fromkeys(clients)}
    planned = []
    summary = []
    removals = []
    # Build and validate the full plan before writing any profile.
    for client in dict.fromkeys(clients):
        imported = client_servers(home, client)
        names = all_names[client]
        if any(len(name) > 64 for name in names.values()):
            raise ValueError('O nome completo de cada perfil deve ter até 64 caracteres')
        for original, target in names.items():
            destination = store / f'{target}.md'
            if destination.is_symlink():
                raise ValueError(f'O perfil de destino não pode ser um link: {target}')
            existing = destination.read_text(encoding='utf-8') if destination.exists() else None
            if existing is not None and MARKER not in existing:
                raise ValueError(f'O perfil {target} já existe e não pertence à stack')
            text = render_profile(profile_definition(home, original, base_dir), target, client, imported, all_names)
            changed = existing != text or (
                destination.exists() and stat.S_IMODE(destination.stat().st_mode) != 0o600
            )
            if changed:
                planned.append((destination, text))
            summary.append({'name': target, 'provider': client, 'servers': sorted(imported)})

    if prune:
        # Only remove regular, marker-bearing files. Explicit legacy prefixes
        # cover the old naming scheme; current names come from selected clients.
        candidates = set()
        if store.exists():
            candidates.update(store.glob(f'{prefix}_*.md'))
            for old_prefix in prune_prefixes:
                candidates.update(store.glob(f'{old_prefix}_*.md'))
            current = {f'{name}.md' for names in all_names.values() for name in names.values()}
            for path in candidates:
                if path.name not in current and not path.is_symlink() and path.is_file():
                    if MARKER.encode() in path.read_bytes():
                        removals.append(path)
        if base_dir and base_dir.is_dir():
            for path in base_dir.glob('*.md'):
                if path.stem not in profiles and not path.is_symlink() and path.is_file():
                    if MARKER.encode() in path.read_bytes():
                        removals.append(path)

    if not check:
        for path in removals:
            path.unlink()
        for path, text in planned:
            write_private(path, text)
    return {'changed': bool(planned or removals), 'check': check, 'profiles': summary, 'removed': sorted(str(path) for path in removals)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--clients', nargs='+', choices=list(CLIENT_LABELS), default=list(CLIENT_LABELS))
    parser.add_argument('--profiles', nargs='+', default=DEFAULT_PROFILES)
    parser.add_argument('--prefix', default='mala')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--base-dir', type=Path)
    parser.add_argument('--prune', action='store_true')
    parser.add_argument('--prune-prefix', action='append', default=[])
    parser.add_argument('--definitions-only', action='store_true')
    args = parser.parse_args()
    try:
        result = synchronize(args.home, args.clients, args.profiles, args.prefix, args.check, args.base_dir, args.prune, args.prune_prefix, args.definitions_only)
    except (OSError, ValueError) as error:
        # Configuration payloads and authentication tokens are never logged.
        print(f'Falha ao sincronizar MCPs: {error}', file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
