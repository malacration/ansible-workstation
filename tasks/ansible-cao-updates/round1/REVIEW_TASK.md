# Revisão independente: instalação e updates CAO via Ansible

Repositório: `/home/andrew/git/ansible-workstation`.
Escopo: oito arquivos listados em `/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/REPORT.md`, e seus artefatos. RTK é separado (agente cf398da8); não alterar ai/roles/rtk nem incorporar RTK nesta revisão.

1. Leia AGENTS.md aplicáveis e git status antes de agir. Use caminhos absolutos. Preserve mudanças preexistentes e não altere central-de-incidentes.
2. Leia specification.md, REPORT.md, CHANGES.diff, VALIDATION.json, UPSTREAM.json, PRESERVATION.json, FINAL_STATE.json e baseline/ nesse diretório. Compare os arquivos atuais com o diff e hashes. A baseline inicial excluiu componentes tasks, incluindo role tasks: o original cao/tasks/main.yml foi reconstruído da primeira leitura completa e não tem hash inicial; avaliar essa limitação explicitamente.
3. Verifique origem/ref/pin configuráveis, default upstream fixado, diferença PyPI latest vs main e limite de effort:auto ao consumidor efêmero. Não confundir número 2.5.4 do upstream com release PyPI. As cópias oficiais datadas estão em upstream-*.txt e o manifesto contém seus hashes.
4. Revise idempotência para pins/branches, upgrade explícito, manutenção de extras/--with, erros antes de alterações com recibos não suportados, compatibilidade Python/Ubuntu e guarda de reinício. Confirme que cao-update.yml não importa serviço/MCP, mas preserva pré-requisitos comuns da role.
5. Confira os 15 testes e syntax-checks registrados. Se repetir, use apenas os testes isolados abaixo e syntax-check/list-tasks; não aplicar playbook no workstation, instalar no uv real, tocar settings/credenciais, reiniciar servidor/sessões nem lançar workers. Não instalar/inventar decider nem acessar serviço novo. Não ler ~/.aws/credentials, ~/.ssh/*, .env ou *.pem.
6. Registre REVIEW.md neste diretório com APPROVED explícito ou achados concretos, severidade, caminhos e comandos/evidências. Aprovação refere-se ao código validado, sem afirmar instalação real nem esforço ponta a ponta.

Comandos seguros de reprodução:

```bash
ansible-playbook /home/andrew/git/ansible-workstation/ai/cao.yml --syntax-check
ansible-playbook /home/andrew/git/ansible-workstation/ai/cao-update.yml --syntax-check
ansible-playbook /home/andrew/git/ansible-workstation/ai/all.yml --syntax-check
ansible-playbook /home/andrew/git/ansible-workstation/ai/cao-update.yml --list-tasks
/home/andrew/.local/share/uv/tools/cli-agent-orchestrator/bin/python -m unittest discover -s /home/andrew/git/ansible-workstation/ai/tests -v
```
