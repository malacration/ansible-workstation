from pathlib import Path
p=Path('ai/roles/cao/tasks/service.yml');s=p.read_text(); cut=s.index('    - name: Informar migração prevista'); pre=s[:cut]; remainder=s[cut:]; Path('ai/roles/cao/tasks/service-preflight.yml').write_text(pre)
p.write_text('''---
- name: Verificar condições para migração de unidade CAO
  ansible.builtin.import_tasks: service-preflight.yml

- name: Configurar serviço opcional do CAO
  become: true
  become_user: root
  when: cao_service_enabled | bool
  block:
'''+remainder)
p=Path('ai/cao-service-preflight.yml');p.write_text('''---
- name: Verificar antecipadamente a migração do serviço CAO
  hosts: localhost
  connection: local
  become: false
  gather_facts: true
  tasks:
    - name: Aplicar padrão da opção de serviço quando ausente
      ansible.builtin.set_fact:
        cao_service_enabled: false
      when: cao_service_enabled is not defined

    - name: Preparar informações para verificação da unidade
      when: cao_service_enabled | bool
      block:
        - name: Determinar usuário padrão dos agentes
          ansible.builtin.set_fact:
            ai_stack_user: "{{ ansible_facts['env']['SUDO_USER'] | default(ansible_facts['user_id'], true) }}"
          when: ai_stack_user is not defined

        - name: Consultar usuário de instalação
          ansible.builtin.getent:
            database: passwd
            key: "{{ ai_stack_user }}"
          when: ai_stack_home is not defined

        - name: Determinar diretório padrão dos agentes
          ansible.builtin.set_fact:
            ai_stack_home: "{{ ansible_facts['getent_passwd'][ai_stack_user][4] }}"
          when: ai_stack_home is not defined

        - name: Determinar diretório padrão de executáveis
          ansible.builtin.set_fact:
            ai_stack_bin_dir: "{{ ai_stack_home }}/.local/bin"
          when: ai_stack_bin_dir is not defined

        - name: Determinar nome padrão da unidade
          ansible.builtin.set_fact:
            cao_service_name: cao-server
          when: cao_service_name is not defined

        - name: Determinar nomes legados padrão
          ansible.builtin.set_fact:
            cao_service_legacy_names: ["cao-server-{{ ai_stack_user }}"]
          when: cao_service_legacy_names is not defined

        - name: Determinar política padrão de reinício
          ansible.builtin.set_fact:
            cao_restart_on_change: false
          when: cao_restart_on_change is not defined

        - name: Validar unidades legadas antes de mudanças
          ansible.builtin.import_tasks: roles/cao/tasks/service-preflight.yml
''')
p=Path('ai/cao-service.yml');s=p.read_text();p.write_text('''---
- name: Verificar previamente unidades do CAO
  ansible.builtin.import_playbook: cao-service-preflight.yml

'''+s.removeprefix('---\n'))
p=Path('ai/all.yml');s=p.read_text();p.write_text('''---
- name: Verificar previamente unidades do CAO
  ansible.builtin.import_playbook: cao-service-preflight.yml
  tags: [always]

'''+s.removeprefix('---\n'))
# Keep the isolated tests pointed at the same production preflight and unit tasks.
p=Path('ai/tests/test_cao_service_migration.py');s=p.read_text();s=s.replace("        (self.root / 'service.yml').write_text(tasks)", "        (self.root / 'service.yml').write_text(tasks)\n        preflight = (ROLE / 'tasks/service-preflight.yml').read_text().replace(\n            '/etc/systemd/system/', str(self.units) + '/').replace('  become: true', '  become: false')\n        (self.root / 'service-preflight.yml').write_text(preflight)");p.write_text(s)
