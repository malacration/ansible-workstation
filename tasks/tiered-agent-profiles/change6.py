from pathlib import Path
p=Path('ai/cao-service-preflight.yml');p.write_text('''---
- name: Verificar antecipadamente a migração do serviço CAO
  hosts: localhost
  connection: local
  become: false
  gather_facts: true
  roles:
    - role: cao
      when: false
  tasks:
    - name: Consultar usuário de instalação
      ansible.builtin.getent:
        database: passwd
        key: "{{ ai_stack_user }}"
      when: cao_service_enabled | bool and ai_stack_user not in (ansible_facts['getent_passwd'] | default({}))

    - name: Validar unidades legadas antes de mudanças
      ansible.builtin.import_tasks: roles/cao/tasks/service-preflight.yml
      when: cao_service_enabled | bool
''')
p=Path('ai/cao-service.yml');s=p.read_text().replace('- name: Configurar serviço opcional do CAO\n', '''- name: Validar backend de terminal do CAO
  ansible.builtin.import_playbook: cao-terminal-backend.yml
  tags: [cao_service, herdr]

- name: Configurar serviço opcional do CAO
''');p.write_text(s)
p=Path('ai/all.yml');s=p.read_text();s=s.replace('''- name: Validar backend de terminal do CAO
  ansible.builtin.import_playbook: cao-terminal-backend.yml
  tags: [cao_service, herdr]

''','');p.write_text(s)
p=Path('ai/roles/cao/tasks/service-preflight.yml');s=p.read_text();pos=s.index('    - name: Informar migração prevista') if '    - name: Informar migração prevista' in s else len(s);s=s[:pos]+'''
    - name: Consultar cgroup da sessão tmux
      ansible.builtin.command:
        argv: [cat, /proc/self/cgroup]
      register: cao_session_cgroup
      changed_when: false
      failed_when: false
      check_mode: false
      when: ansible_facts['env']['TMUX'] is defined

    - name: Impedir interrupção da própria sessão CAO
      ansible.builtin.assert:
        that:
          - >-
            not ((ansible_facts['env']['CAO_TERMINAL_ID'] is defined or
                  (ansible_facts['env']['TMUX'] is defined and
                   'cao-server' in (cao_session_cgroup.stdout | default('')))) and
                 (cao_restart_on_change | bool or
                  (cao_legacy_states.results | rejectattr('skipped', 'defined') |
                   selectattr('stdout', 'defined') | map(attribute='stdout') |
                   map('trim') | reject('in', ['inactive', 'failed']) | list | length > 0)))
        fail_msg: >-
          A operação pode encerrar esta sessão; execute fora de uma sessão CAO
          (terminal comum ou SSH).
'''+s[pos:];p.write_text(s)
p=Path('ai/roles/cao/tasks/restart-service.yml');s=p.read_text();idx=s.index('- name: Reiniciar unidade existente');s=s[:idx]+'''- name: Impedir reinício a partir da própria sessão CAO
  ansible.builtin.assert:
    that:
      - ansible_facts['env']['CAO_TERMINAL_ID'] is not defined
    fail_msg: "Para reiniciar o servidor, execute fora de uma sessão CAO (terminal comum ou SSH)."
  when:
    - cao_service_enabled | bool
    - cao_restart_on_change | bool
    - not ansible_check_mode
    - cao_service_unit.stat.exists | default(false)

'''+s[idx:];p.write_text(s)
p=Path('ai/roles/cao/handlers/main.yml');s=p.read_text().replace('    - not ansible_check_mode','    - not ansible_check_mode\n    - not (cao_legacy_removed.changed | default(false))');p.write_text(s)
p=Path('ai/roles/cao/tasks/mcp.yml');s=p.read_text().replace('    - name: Consultar diretório dos ambientes uv', '''    - name: Verificar disponibilidade do uv
      ansible.builtin.stat:
        path: "{{ ai_stack_bin_dir }}/uv"
      register: cao_mcp_uv

    - name: Consultar diretório dos ambientes uv''').replace('      check_mode: false\n\n    - name: Preparar diretório', '      check_mode: false\n      when: cao_mcp_uv.stat.executable | default(false)\n\n    - name: Preparar diretório',1).replace('      register: cao_mcp_wrapper_result\n', "      register: cao_mcp_wrapper_result\n      when: cao_mcp_uv.stat.executable | default(false)\n").replace('(cao_sync_wrapper.stat.exists and not cao_mcp_script_result.changed and', '(cao_mcp_uv.stat.executable | default(false) and cao_sync_wrapper.stat.exists and not cao_mcp_script_result.changed and');p.write_text(s)
p=Path('ai/README.md');s=p.read_text().replace('avulsa de `ai/cao-service.yml`, execute essa validação antes do serviço:\nPara validar isoladamente:', 'avulsa de `ai/cao-service.yml`, a validação também é executada automaticamente.\nPara validar isoladamente:').replace('ele inicia o serviço se estiver parado. Mesmo com a unidade atualizada, o servidor em execução mantém o backend anterior até\nser reiniciado.', 'ele inicia o serviço se estiver parado. Mesmo com a unidade atualizada, o servidor\nem execução mantém o backend anterior até ser reiniciado.').replace('Essa verificação também abre `ai/all.yml`. Unidades legadas não reconhecidas são recusadas.', 'Essa verificação também é executada no início de `ai/all.yml`.\nUnidades legadas não reconhecidas são recusadas.').replace('em janela de manutenção, confira o conteúdo da unidade antiga e execute:', 'em janela de manutenção, execute fora de uma sessão CAO (terminal comum ou SSH),\nconfira o conteúdo da unidade antiga e execute:');p.write_text(s)
