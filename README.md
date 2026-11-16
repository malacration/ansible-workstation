# Ansible Workstation

Playbooks para configurar uma workstation Ubuntu, organizados por categoria.
O `all.yml` reúne os componentes de `sdk`, `ide`, `browser`, `cli`, `util`,
`media-editor` e `ai`.

## Preparar e executar

```bash
chmod +x install.sh
./install.sh
ansible-playbook all.yml --ask-become-pass
```

O script instala o Ansible e as roles de `requirements.yml`. Use Ansible Core
2.16 ou superior para os novos playbooks de IA. Execute como o usuário da
workstation; as tarefas que precisam de root usam sudo.

## Stack de IA

Cada componente possui seu próprio YAML em `ai/`. Para instalar apenas a stack:

```bash
ansible-playbook ai/all.yml --ask-become-pass
# Ou pelo playbook principal:
ansible-playbook all.yml --tags ai --ask-become-pass
```

Também é possível executar um componente separadamente:

```bash
ansible-playbook ai/codex.yml --ask-become-pass
ansible-playbook ai/claude.yml --ask-become-pass
ansible-playbook ai/chrome-devtools.yml --ask-become-pass
ansible-playbook ai/cao.yml --ask-become-pass
ansible-playbook ai/mcp.yml --ask-become-pass
```

A stack inclui Codex CLI, Claude Code, Chrome DevTools MCP, uv, CAO e
compartilhamento dos MCPs dos clientes com os perfis do CAO. O instalador do
Chrome DevTools chama os subplaybooks de Node.js e Chrome. O serviço systemd é opcional e fica em
`ai/cao-service.yml`.

Veja [a documentação da stack de IA](ai/README.md) para versões, autenticação,
MCPs, serviço e testes.
