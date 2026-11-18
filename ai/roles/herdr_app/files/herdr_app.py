#!/usr/bin/env python3
"""Install pinned Herdr app layouts and mods, apply local patches, merge owned settings.

Inputs come from the role as one JSON spec (--spec). For each source the release
tarball must already be in the cache and match its pinned SHA256. Only the listed
paths are extracted (no links, no absolute or parent paths), the local patch is
applied with `git apply` in a private staging directory, and each resulting file
is written to the Herdr app home only when its content differs, so Herdr reloads
nothing that did not change. Nothing is ever deleted.

Owned settings, merged without touching anything else:
- keys.json: sections/keys from each source's keys file; a key the person bound
  differently is kept and reported.
- mods/herdr-crew-rpg/config.json: claudeAccounts (keys the person added to an account,
  such as a budget, are kept; claude_budgets sets budgetUsd/budgetPeriod); other keys preserved.
- <claude config dir>/settings.json: statusLine, only when absent or already ours;
  a foreign status line is kept and reported. The first change of a file keeps a
  backup (settings.json.herdr-app-backup.<sha256>). Setting values are never printed.
- <codex home>/config.toml: [tui] terminal_title, only when unset (backup as above).

Clones: copies of mods Herdr ships (agents, spaces, tabs -> *-titles) with a local patch. Herdr
rewrites its own mods on every start, so changes live in a copy made from the mod in
the Herdr home. When Herdr's mod changed and the patch no longer applies, the copy
is left as it is and reported.

Prints one JSON object: {changed, files, warnings, backups}.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile

ACCOUNT = re.compile(r'^[a-z0-9][a-z0-9-]{0,31}$')
SOURCE = re.compile(r'^[a-z0-9][a-z0-9_-]{0,31}$')
STATUSLINE_MARK = 'herdr-crew-rpg/claude-statusline.py'
CREW_CONFIG = 'mods/herdr-crew-rpg/config.json'
CREW_DEFAULTS = {'language': 'auto', 'cursorQuota': False}


def safe_path(root, path):
    """A path inside root with no symlink in it or its parents (dangling links included)."""
    root = Path(os.path.abspath(root))
    path = Path(os.path.abspath(path))
    if path != root and root not in path.parents:
        raise ValueError('Managed path escapes its root')
    for candidate in [path, *path.parents]:
        if candidate.is_symlink():
            raise ValueError('Symlink in a managed path; review it manually')
        if candidate == root:
            break
    return path


def relative(value):
    """A clean relative POSIX path (no absolute, empty, '.' or '..' parts)."""
    parts = PurePosixPath(value).parts
    if not parts or value.startswith('/') or any(p in ('', '.', '..') for p in parts):
        raise ValueError('Invalid relative path in spec')
    return PurePosixPath(*parts)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def extract(tarball, wanted, stage):
    """Extract the wanted paths (files or folders) from a GitHub archive into stage."""
    wanted = [relative(w) for w in wanted]
    found = set()
    with tarfile.open(tarball, 'r:gz') as archive:
        top = None
        for member in archive.getmembers():
            parts = PurePosixPath(member.name).parts
            if not parts or member.name.startswith('/') or '..' in parts:
                raise ValueError('Unsafe path in archive')
            top = top or parts[0]
            if parts[0] != top:
                raise ValueError('Archive has more than one top-level folder')
            if len(parts) == 1:
                continue
            inner = PurePosixPath(*parts[1:])
            match = next((w for w in wanted if inner == w or w in inner.parents), None)
            if match is None:
                continue
            if not (member.isfile() or member.isdir()):
                raise ValueError('Links and special files are not installed: ' + str(inner))
            found.add(match)
            target = stage / inner
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, open(target, 'wb') as output:
                shutil.copyfileobj(source, output)
            os.chmod(target, 0o755 if member.mode & 0o111 else 0o644)
    missing = [str(w) for w in wanted if w not in found]
    if missing:
        raise ValueError('Paths missing from the pinned archive: ' + ', '.join(missing))


def apply_patch(stage, patch):
    """git apply in the staging folder; ceiling dirs keep git from finding any repository."""
    env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(stage.parent), LC_ALL='C')
    for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'):
        env.pop(key, None)
    done = subprocess.run(['git', 'apply', '-p1', '--whitespace=nowarn', str(patch)],
                          cwd=stage, env=env, capture_output=True, text=True, timeout=60)
    if done.returncode != 0:
        raise ValueError('Local patch does not apply to the pinned source: ' + patch.name)


def stage_clone(plan, app_home, clone, patches_dir, stage_root):
    """Copy a shipped mod (flat folder) to its new name in stage_root and patch it; None if not possible."""
    source = safe_path(app_home, app_home / relative(clone['from']))
    dest = relative(clone['dest'])
    if not source.is_dir():
        plan.warnings.append(f'{clone["from"]} missing from the Herdr home: {dest} not installed')
        return None
    stage = stage_root / ('clone-' + dest.name)
    (stage / dest).mkdir(parents=True)
    for file in sorted(source.iterdir()):
        if file.is_file() and not file.is_symlink():
            shutil.copyfile(file, stage / dest / file.name)
    try:
        apply_patch(stage, Path(patches_dir) / relative(clone['patch']))
    except ValueError:
        plan.warnings.append(f'{dest}: patch no longer applies to {clone["from"]} (Herdr updated?); left as installed')
        return None
    return stage


TITLE_ITEM = re.compile(r'^[a-z][a-z-]{0,39}$')


def merge_codex_title(plan, home, codex_home, items):
    """[tui] terminal_title in Codex's config.toml, only when the person has none."""
    if not items:
        return
    if not all(isinstance(i, str) and TITLE_ITEM.match(i) for i in items):
        raise ValueError('Codex terminal title items must be simple identifiers')
    path = safe_path(home, Path(codex_home) / 'config.toml')
    if not path.is_file():
        plan.warnings.append('Codex config.toml missing: terminal title not set')
        return
    try:
        import tomllib
    except ImportError:
        plan.warnings.append('Python without tomllib: Codex terminal title not set')
        return
    text = path.read_text(encoding='utf-8')
    try:
        tui = tomllib.loads(text).get('tui', {})
    except tomllib.TOMLDecodeError:
        plan.warnings.append('Codex config.toml is not valid TOML, left as is')
        return
    if not isinstance(tui, dict):
        plan.warnings.append('Codex config.toml: tui is not a table, left as is')
        return
    if 'terminal_title' in tui:
        if tui['terminal_title'] != items:
            plan.warnings.append('Codex config.toml: another tui.terminal_title is set, kept')
        return
    line = 'terminal_title = ' + json.dumps(items) + '\n'
    header = re.search(r'(?m)^\[tui\][ \t]*(#.*)?\n', text)
    if header:
        new = text[:header.end()] + line + text[header.end():]
    elif tui:
        plan.warnings.append('Codex config.toml: tui is not a [tui] table, terminal title not set')
        return
    else:
        new = text + ('\n' if text and not text.endswith('\n') else '') + '\n[tui]\n' + line
    if tomllib.loads(new).get('tui', {}).get('terminal_title') != items:
        plan.warnings.append('Codex config.toml: terminal title could not be added safely')
        return
    plan.write(home, path, new.encode('utf-8'), mode=0o600, backup=True)


def load_json(path, default):
    if not path.exists():
        return default
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def dump_json(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8')


class Plan:
    """Collects writes so check mode and apply mode share one code path."""

    def __init__(self, check):
        self.check = check
        self.files = []
        self.warnings = []
        self.backups = []

    def write(self, root, path, data, mode=0o644, backup=False):
        path = safe_path(root, path)
        if path.exists() and not path.is_file():
            raise ValueError('Destination is not a regular file: ' + str(path))
        old = path.read_bytes() if path.exists() else None
        if old == data:
            return
        self.files.append(str(path))
        if self.check:
            return
        if backup and old is not None:
            copy = safe_path(root, path.with_name(path.name + '.herdr-app-backup.' + hashlib.sha256(old).hexdigest()))
            if not copy.exists():
                with open(copy, 'xb') as output:
                    os.chmod(copy, 0o600)
                    output.write(old)
                self.backups.append(str(copy))
        if old is not None:
            mode = stat.S_IMODE(path.stat().st_mode)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        descriptor, name = tempfile.mkstemp(prefix='.herdr-app-', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'wb') as output:
                output.write(data)
                os.fchmod(output.fileno(), mode)
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)


def merge_keys(plan, app_home, staged_keys):
    path = app_home / 'keys.json'
    if not path.exists():
        plan.warnings.append('keys.json missing: start the Herdr app once, then run again to add the layout keys')
        return
    current = load_json(path, {})
    merged = json.loads(json.dumps(current))
    for section, keys in staged_keys.items():
        if not isinstance(keys, dict):
            continue
        target = merged.setdefault(section, {})
        for key, action in keys.items():
            if key not in target:
                target[key] = action
            elif target[key] != action:
                plan.warnings.append(f'keys.json: {section} {key} kept as you bound it')
    if merged != current:
        plan.write(app_home, path, dump_json(merged))


def crew_accounts(accounts, home):
    """configDir lets claude-statusline.py find the account from CLAUDE_CONFIG_DIR: the
    status line argument alone is unreliable, since a session started in ~ also loads
    ~/.claude/settings.json as project settings. Paths under home are written as ~/..."""
    def short(path):
        path = os.path.abspath(path)
        return '~/' + os.path.relpath(path, home) if path.startswith(str(home) + os.sep) else path
    return [{'id': 'claude' if a['name'] == 'home' else 'claude-' + a['name'],
             'name': 'Claude' if a['name'] == 'home' else 'Claude ' + a['name'].upper(),
             'account': a['name'], 'configDir': short(a['config_dir'])} for a in accounts]


OWNED_ACCOUNT_KEYS = {'id', 'name', 'account', 'configDir'}


def crew_budget(name, budget):
    """{usd: >0, period: month}: a pay-per-token account's budget (quota.py shows its monthly spend)."""
    if not isinstance(budget, dict) or not isinstance(budget.get('usd'), (int, float)) or budget['usd'] <= 0 \
            or budget.get('period', 'month') != 'month':
        raise ValueError(f'Claude budget {name}: expected {{usd: > 0, period: month}}')
    return {'budgetUsd': budget['usd'], 'budgetPeriod': 'month'}


def merge_crew_config(plan, home, app_home, accounts, budgets=None):
    path = app_home / CREW_CONFIG
    try:
        current = load_json(path, {})
    except ValueError:
        current = {}
        plan.warnings.append('Crew config.json was not valid JSON; rewritten with defaults')
    current = current if isinstance(current, dict) else {}
    previous = {a.get('account'): a for a in current.get('claudeAccounts') or [] if isinstance(a, dict)}
    wanted = []
    for entry in crew_accounts(accounts, home):
        extra = {k: v for k, v in previous.get(entry['account'], {}).items() if k not in OWNED_ACCOUNT_KEYS}
        if entry['account'] in (budgets or {}):
            extra.update(crew_budget(entry['account'], budgets[entry['account']]))
        wanted.append({**entry, **extra})
    merged = {**CREW_DEFAULTS, **current, 'claudeAccounts': wanted}
    if merged != current:
        plan.write(app_home, path, dump_json(merged))


def merge_statusline(plan, home, account, script, refresh):
    config_dir = safe_path(home, account['config_dir'])
    if not config_dir.is_dir():
        plan.warnings.append(f'Claude account {account["name"]}: {config_dir} missing, status line not set')
        return
    path = config_dir / 'settings.json'
    try:
        settings = load_json(path, {})
    except ValueError:
        plan.warnings.append(f'Claude account {account["name"]}: settings.json is not valid JSON, left as is')
        return
    if not isinstance(settings, dict):
        plan.warnings.append(f'Claude account {account["name"]}: settings.json root is not an object, left as is')
        return
    wanted = {'type': 'command',
              'command': f'python3 -I {shlex.quote(str(script))} {account["name"]} 2>/dev/null || true',
              'refreshInterval': refresh}
    current = settings.get('statusLine')
    command = current.get('command', '') if isinstance(current, dict) else ''
    if current is not None and STATUSLINE_MARK not in str(command):
        plan.warnings.append(f'Claude account {account["name"]}: another status line is set, kept (no quota for it)')
        return
    if current != wanted:
        plan.write(home, path, dump_json({**settings, 'statusLine': wanted}), mode=0o600, backup=True)


def run(spec, check):
    home = Path(os.path.abspath(spec['home']))
    app_home = safe_path(home, spec['app_home'])
    cache = safe_path(home, spec['cache_dir'])
    plan = Plan(check)
    if not app_home.is_dir():
        plan.warnings.append(f'{app_home} missing: start the Herdr app once, then run again')
        return plan
    names = [s['name'] for s in spec['sources']]
    if len(set(names)) != len(names) or not all(SOURCE.match(n) for n in names):
        raise ValueError('Source names must be unique and simple')
    accounts = spec.get('claude_accounts', [])
    if len({a['name'] for a in accounts}) != len(accounts) or not all(ACCOUNT.match(a['name']) for a in accounts):
        raise ValueError('Claude account names must be unique and match ' + ACCOUNT.pattern)
    staged_keys = {}
    stages = []
    cache.mkdir(parents=True, exist_ok=True, mode=0o755)
    with tempfile.TemporaryDirectory(prefix='herdr-app-', dir=cache) as temporary:
        for source in spec['sources']:
            if not re.fullmatch(r'[0-9a-f]{40}', source['commit']):
                raise ValueError(f'{source["name"]}: commit must be a full SHA-1')
            tarball = safe_path(home, cache / f'{source["name"]}-{source["commit"]}.tar.gz')
            if not tarball.is_file():
                if check:
                    plan.warnings.append(f'{source["name"]}: archive not downloaded yet; files would be installed')
                    plan.files.append(f'{source["name"]} (pending download)')
                    continue
                raise ValueError(f'{source["name"]}: archive missing from the cache')
            if sha256(tarball) != source['sha256'].lower():
                raise ValueError(f'{source["name"]}: archive does not match its pinned SHA256')
            stage = Path(temporary) / source['name']
            stage.mkdir()
            extract(tarball, source['paths'], stage)
            if source.get('patch'):
                apply_patch(stage, Path(spec['patches_dir']) / relative(source['patch']))
            if source.get('keys'):
                keys_file = stage / relative(source['keys'])
                for section, keys in load_json(keys_file, {}).items():
                    staged_keys.setdefault(section, {}).update(keys if isinstance(keys, dict) else {})
            stages.append(stage)
        for clone in spec.get('clones', []):
            stage = stage_clone(plan, app_home, clone, spec['patches_dir'], Path(temporary))
            if stage:
                stages.append(stage)
        # Every source is extracted and patched before the first write: one bad pin or
        # patch leaves the Herdr home untouched.
        for stage in stages:
            for file in sorted(p for p in stage.rglob('*') if p.is_file()):
                inner = file.relative_to(stage)
                if inner.as_posix() == CREW_CONFIG and accounts:
                    continue  # merged below: the person's own settings in it are kept
                plan.write(app_home, app_home / inner, file.read_bytes(), mode=stat.S_IMODE(file.stat().st_mode))
        for extra in spec.get('files', []):
            plan.write(app_home, app_home / relative(extra['dest']), Path(extra['src']).read_bytes())
    if staged_keys:
        merge_keys(plan, app_home, staged_keys)
    if accounts and 'crew' in names:
        merge_crew_config(plan, home, app_home, accounts, spec.get('claude_budgets') or {})
        script = app_home / 'mods/herdr-crew-rpg/claude-statusline.py'
        for account in accounts:
            merge_statusline(plan, home, account, script, spec.get('statusline_refresh', 60))
    if spec.get('codex_home'):
        merge_codex_title(plan, home, spec['codex_home'], spec.get('codex_terminal_title', []))
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--spec', required=True, help='JSON spec (see the role defaults)')
    parser.add_argument('--check', action='store_true', help='report what would change, write nothing')
    args = parser.parse_args()
    try:
        plan = run(json.loads(args.spec), args.check)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, tarfile.TarError) as error:
        # Never echo file contents or settings values.
        print('herdr-app setup failed: ' + type(error).__name__ + ': ' + str(error), file=sys.stderr)
        return 1
    print(json.dumps({'changed': bool(plan.files), 'files': plan.files,
                      'warnings': plan.warnings, 'backups': plan.backups}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
