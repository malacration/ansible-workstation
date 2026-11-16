from pathlib import Path
p=Path('ai/roles/cao/files/sync_mcps.py'); s=p.read_text(); s=s.replace('def base_profile(home, name):\n    local', 'def base_profile(home, name, base_dir=None):\n    local'); s=s.replace('    if local.exists():\n        text = local.read_text', '    preferred = base_dir / f\'{name}.md\' if base_dir else None\n    if preferred is not None and preferred.is_file():\n        text = preferred.read_text(encoding=\'utf-8\')\n    elif local.exists():\n        text = local.read_text'); s=s.replace("    metadata['provider'] = client", "    metadata['provider'] = client\n    metadata.pop('claudeConfig' if client == 'codex' else 'codexConfig', None)"); s=s.replace("def synchronize(home, clients, profiles, prefix='ai_stack', check=False):", "def synchronize(home, clients, profiles, prefix='ai_stack', check=False, base_dir=None, prune=False):"); s=s.replace('    summary = []\n', '    summary = []\n    removals = []\n'); s=s.replace('base_profile(home, original)', 'base_profile(home, original, base_dir)'); s=s.replace('    if not check:\n        for path, text in planned:', '''    if prune and store.exists():
        for client in dict.fromkeys(clients):
            stem = f'{prefix}_{CLIENT_LABELS[client]}_'
            current = {f'{stem}{name}.md' for name in profiles}
            for path in store.glob(f'{stem}*.md'):
                if path.name not in current and not path.is_symlink() and path.is_file():
                    if MARKER in path.read_text(encoding='utf-8'):
                        removals.append(path)

    if not check:
        for path in removals:
            path.unlink()
        for path, text in planned:'''); s=s.replace("return {'changed': bool(planned), 'check': check, 'profiles': summary}", "return {'changed': bool(planned or removals), 'check': check, 'profiles': summary}"); s=s.replace("    parser.add_argument('--check', action='store_true')", "    parser.add_argument('--check', action='store_true')\n    parser.add_argument('--base-dir', type=Path)\n    parser.add_argument('--prune', action='store_true')"); s=s.replace('args.prefix, args.check)', 'args.prefix, args.check, args.base_dir, args.prune)'); p.write_text(s)
p=Path('ai/roles/cao/defaults/main.yml'); s=p.read_text().replace('cao_mcp_profiles: [code_supervisor, developer, reviewer]', '''cao_mcp_profiles: [code_supervisor, developer_low, developer_medium, developer_high, reviewer_basic, reviewer_advanced]
cao_profile_efforts:
  code_supervisor: {codex: medium, claude: medium}
  developer_low: {codex: low, claude: low}
  developer_medium: {codex: medium, claude: medium}
  developer_high: {codex: high, claude: high}
  reviewer_basic: {codex: low, claude: low}
  reviewer_advanced: {codex: high, claude: high}'''); p.write_text(s)
p=Path('ai/roles/cao/tasks/mcp.yml'); s=p.read_text(); s=s.replace('- name: Preparar sincronização', '''- name: Validar níveis de esforço dos perfis gerenciados
  ansible.builtin.assert:
    that:
      - item.value.codex in ['minimal', 'low', 'medium', 'high', 'xhigh']
      - item.value.claude in ['low', 'medium', 'high', 'xhigh']
  loop: "{{ cao_profile_efforts | dict2items }}"

- name: Preparar sincronização'''); s=s.replace('    - name: Instalar sincronizador dos MCPs', '''    - name: Preparar diretório privado dos perfis base
      ansible.builtin.file:
        path: "{{ ai_stack_home }}/.local/share/ai-stack/profiles"
        state: directory
        mode: '0700'

    - name: Instalar perfis base gerenciados
      ansible.builtin.template:
        src: "profiles/{{ item.template }}.md.j2"
        dest: "{{ ai_stack_home }}/.local/share/ai-stack/profiles/{{ item.name }}.md"
        mode: '0600'
      loop:
        - {name: code_supervisor, template: code_supervisor}
        - {name: developer_low, template: developer}
        - {name: developer_medium, template: developer}
        - {name: developer_high, template: developer}
        - {name: reviewer_basic, template: reviewer}
        - {name: reviewer_advanced, template: reviewer}

    - name: Instalar sincronizador dos MCPs'''); s=s.replace('argv: ["{{ ai_stack_bin_dir }}/ai-stack-sync-mcps"]', 'argv: ["{{ ai_stack_bin_dir }}/ai-stack-sync-mcps", --prune]'); p.write_text(s)
p=Path('ai/roles/cao/templates/ai-stack-sync-mcps.j2'); s=p.read_text().replace('  --prefix', "  --base-dir {{ (ai_stack_home ~ '/.local/share/ai-stack/profiles') | quote }} \\\n  --prefix"); p.write_text(s)
d=Path('ai/roles/cao/templates/profiles'); d.mkdir(exist_ok=True)
head='''---
name: {{ item.name }}
description: "{{ item.name }} managed agent"
role: ROLE
tags: [coding, "{{ item.name }}"]
codexConfig:
  model_reasoning_effort: "{{ cao_profile_efforts[item.name].codex }}"
claudeConfig:
  effort: "{{ cao_profile_efforts[item.name].claude }}"
mcpServers:
  cao-mcp-server:
    type: stdio
    command: cao-mcp-server
    args: []
---

'''
(d/'developer.md.j2').write_text(head.replace('ROLE','developer')+'''# Developer

Implement assigned tasks with maintainable, correct code. Read the project's own
AGENTS.md, CLAUDE.md, README and applicable conventions; follow existing patterns.
Consider edge cases, document complex logic, and run the project's relevant tests
and checks. Report changes, verification, and remaining limitations to the supervisor.
Use absolute paths for task artifacts and follow the assigned task description.
''')
(d/'reviewer.md.j2').write_text(head.replace('ROLE','reviewer')+'''# Code reviewer

Independently review the assigned changes against the task and repository conventions.
Look for defects, regressions, security risks, missing edge cases and meaningful test
coverage. Inspect relevant context and run appropriate checks when useful. Report
concrete actionable findings with absolute paths and locations, or explicitly approve
when no blocking issues remain. Do not implement the changes under review.
''')
(d/'code_supervisor.md.j2').write_text(head.replace('ROLE','supervisor')+'''# Coding supervisor

Coordinate development; never write code or perform the code review yourself. Write
each task description in a dedicated tasks directory using an absolute path, and
instruct workers to read that file. Record the task level and a one-line reason in
that file before delegation. Track artifacts with absolute paths. Every code change
must be reviewed; relay findings and repeat the review until approved.

## Classification and routing

Use a user override `[level: low|medium|high]` or `[nivel: baixo|medio|alto]`
without classifying. Otherwise classify each task:

- LOW: one file or mechanical change, clear specification and low risk, such as a
  rename, configuration tweak, documentation, formatting or small obvious fix.
- MEDIUM: feature or bug fix across a few files, clear specification, tests needed.
- HIGH: architecture or design, concurrency, security, migration or data loss risk,
  production infrastructure, ambiguous specification, debugging without a known
  cause, or roughly more than five files.

Raise the level by one, up to HIGH, if any applies: ambiguity; three or more files
or systems; security, production or data-loss stakes; unfamiliar territory; or a
wrong result that would be hard to detect later. If unsure between levels, choose
the higher; default to MEDIUM when information is missing.

Route LOW, MEDIUM and HIGH to developer_low, developer_medium and developer_high,
respectively. Route LOW and MEDIUM reviews to reviewer_basic and HIGH reviews to
reviewer_advanced. Use reviewer_advanced regardless of level whenever security,
production or data-loss stakes apply. After two reviewer rejections of the same task,
reassign the fix one developer level higher, capped at HIGH; use reviewer_advanced
once the task reaches HIGH. Always use workers on your own provider, using the
provider-specific names in the appended routes section.
''')
