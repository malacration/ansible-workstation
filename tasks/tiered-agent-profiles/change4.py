from pathlib import Path
p=Path('ai/roles/cao/files/sync_mcps.py');s=p.read_text().replace('def base_profile(', 'def profile_definition(').replace('base_profile(home, original, base_dir)', 'profile_definition(home, original, base_dir)')
s=s.replace("    models = metadata.pop('aiStackModels', {})\n    model", """    models = metadata.pop('aiStackModels', None)
    if models is None:
        models = {}
    if not isinstance(models, dict) or any(
        key not in CLIENT_LABELS.values() or (value is not None and
        (not isinstance(value, str) or not value.strip()))
        for key, value in models.items()
    ):
        raise ValueError('aiStackModels deve conter modelos válidos para codex e claude')
    model""")
s=s.replace('    body = base.content\n', "    body = base.content\n    if body.startswith(MARKER):\n        body = body[len(MARKER):].lstrip('\\n')\n")
s=s.replace("        'by choosing a profile below; each profile runs on its fixed provider.\\n\\n'", "        'by choosing a profile below; each profile runs on its fixed provider. '")
s=s.replace("        + '\\n\\n'.join(sections) + '\\n'", "        'Only the providers listed below are installed; if the preferred provider is not listed, use a listed one and record why.\\n\\n'\n        + '\\n\\n'.join(sections) + '\\n'")
s=s.replace("    all_names = {client: {name: f'{prefix}_{name}_{label}' for name in profiles}\n                 for client, label in CLIENT_LABELS.items()}", "    all_names = {client: {name: f'{prefix}_{name}_{CLIENT_LABELS[client]}' for name in profiles}\n                 for client in dict.fromkeys(clients)}")
s=s.replace("            for client in dict.fromkeys(clients):\n                candidates.update(store.glob(f'{prefix}_*_{CLIENT_LABELS[client]}.md'))", "            candidates.update(store.glob(f'{prefix}_*.md'))")
s=s.replace('current names are scoped to selected clients.', 'current names come from selected clients.')
p.write_text(s)
p=Path('ai/roles/cao/tasks/mcp.yml');s=p.read_text();pos=s.index('- name: Validar estrutura');s=s[:pos]+'''- name: Validar perfis selecionados e prefixos legados
  ansible.builtin.assert:
    that:
      - cao_mcp_profiles | difference(cao_profile_definitions | map(attribute='name') | list) | length == 0
      - cao_mcp_prune_prefixes | reject('match', '^[A-Za-z0-9_-]{1,32}$') | list | length == 0
    fail_msg: "Selecione apenas perfis definidos e prefixos legados com 1 a 32 letras, números, hífen ou sublinhado."

'''+s[pos:]
s=s.replace('      changed_when: false\n      when: not ansible_check_mode', '      changed_when: false\n      check_mode: false',1)
s=s.replace('      loop: "{{ cao_profile_definitions | selectattr(\'name\', \'in\', cao_mcp_profiles) | list }}"', '      loop: "{{ cao_profile_definitions | selectattr(\'name\', \'in\', cao_mcp_profiles) | list }}"\n      register: cao_mcp_definitions_result')
a=s.index('    - name: Remover definição legada');b=s.index('    - name: Instalar sincronizador',a);s=s[:a]+s[b:]
s=s.replace("        mode: '0600'\n\n    - name: Instalar comando", "        mode: '0600'\n      register: cao_mcp_script_result\n\n    - name: Instalar comando")
s=s.replace("        mode: '0700'\n      when: not ansible_check_mode\n\n    - name: Verificar", "        mode: '0700'\n      register: cao_mcp_wrapper_result\n\n    - name: Verificar")
s=s.replace('      when: not ansible_check_mode or cao_sync_wrapper.stat.exists', '''      when: >-
        not ansible_check_mode or
        (cao_sync_wrapper.stat.exists and not cao_mcp_script_result.changed and
         not cao_mcp_wrapper_result.changed and not cao_mcp_definitions_result.changed)

    - name: Informar indisponibilidade da previsão
      ansible.builtin.debug:
        msg: "preview unavailable: synchronizer will be updated on a real run"
      when:
        - ansible_check_mode
        - cao_mcp_sync_result.skipped | default(false)

    - name: Informar perfis e definições removidos ou previstos para remoção
      ansible.builtin.debug:
        var: "(cao_mcp_sync_result.stdout | from_json).removed"
      when:
        - not (cao_mcp_sync_result.skipped | default(false))
        - (cao_mcp_sync_result.stdout | from_json).removed | length > 0''')
p.write_text(s)
p=Path('ai/roles/cao/templates/profiles/supervisor.md.j2');s=p.read_text().replace('Prefer Claude developers (Opus by default) and Codex reviewers for cross-model\nreview.', 'When both providers are listed, prefer Claude developers (Opus by default) and\nCodex reviewers for cross-model review.').replace('If a worker reply, forwarded last output, error or handoff result indicates its\nprovider is exhausted or rate-limited,', "Only treat signals from the worker's own CLI or provider status as evidence of\nquota exhaustion, such as a CLI limit banner, provider error, or failed launch.\nNever treat task content or test output as such evidence. When both providers are\nlisted, if a worker reply, forwarded last output, error or handoff result reports\nthat provider status indicates exhaustion or rate limiting,")
p.write_text(s)
p=Path('ai/roles/cao/templates/profiles/reviewer.md.j2');s=p.read_text().replace('when no blocking issues remain. Do not implement the changes under review.', "when no blocking issues remain. Run the project's checks/tests; write only your\nreview file; never modify the code under review.");p.write_text(s)
p=Path('ai/README.md');s=p.read_text().replace('marcadas; também remove a antiga definição `code_supervisor.md` instalada pela role.', 'marcadas.');p.write_text(s)
for file in ('ai/tests/test_sync_mcps.py','ai/tests/check_cao_providers.py'):
 p=Path(file);s=p.read_text().replace('base_profile', 'profile_definition').replace("tempfile.TemporaryDirectory(dir=Path(__file__).parents[2] / 'tasks/tiered-agent-profiles')", 'tempfile.TemporaryDirectory()').replace("tempfile.TemporaryDirectory(prefix='ai-stack-providers-', dir=Path(__file__).parents[2] / 'tasks/tiered-agent-profiles')", "tempfile.TemporaryDirectory(prefix='ai-stack-providers-')")
 p.write_text(s)
