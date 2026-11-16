# CAO: origem configurável e atualização explícita

Status: **implementado e validado; pronto para revisão independente**. Sem bloqueio. O playbook não foi aplicado ao workstation; nenhum servidor/sessão foi reiniciado. RTK pertence ao agente cf398da8 e não foi alterado por esta tarefa.

## Descoberta e escopo

A tarefa foi copiada para `/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/specification.md` antes das mudanças. Não havia AGENTS.md aplicável em `/`, `/home`, `/home/andrew`, `/home/andrew/git`, no repositório alvo ou nas pastas modificadas. Um AGENTS.md encontrado posteriormente em fixture RTK, `tasks/rtk-install/probe-home/.codex`, não se aplica a este escopo. Não surgiram passos adicionais de AGENTS.

O checkout já tinha alterações em README.md, all.yml, browser/chrome.yml e sdk/*.yml; `.gitignore` e toda a pasta `ai/` já eram não rastreadas. `BASELINE_STATUS.txt`, `BASELINE_TRACKED.diff` e `BASELINE.json` preservam a descoberta. Arquivos preexistentes foram editados apenas nos cinco caminhos CAO abaixo, sem sobrescrever o conteúdo anterior. Nada foi gravado no checkout `/home/andrew/git/central-de-incidentes`.

## Implementação

- `/home/andrew/git/ansible-workstation/ai/roles/cao/defaults/main.yml`: origem Git oficial como padrão, com commit `3e30ea3ed6e7fb607b13358d81123afff5a8e69f`; URL/ref/SHA, PyPI/version, extras, dependências e upgrade configuráveis. `cao_upgrade` herda `ai_stack_upgrade` para compatibilidade; pode ser acionado isoladamente.
- `/home/andrew/git/ansible-workstation/ai/roles/cao/tasks/main.yml`: valida as variáveis e executa o helper com `uv run --no-project --no-config --python`, incluindo Ubuntu 22.04 cujo Python de sistema é 3.10. Mantém a verificação dos executáveis.
- `/home/andrew/git/ansible-workstation/ai/roles/cao/files/install_cao.py`: preserva extras e requisitos --with declarados no recibo uv ao trocar origem/ref; falha antes de instalar se encontrar formato auxiliar não suportado; não congela dependências transitivas. Usa recibo compatível como fronteira de não atualização, pois uv resolve branches móveis mesmo sem --upgrade. Mudanças de configuração são reconciliadas; upgrade explícito consulta a origem. Reconhece mudanças reais de pacotes/recibo sem confundir anúncio de executáveis com mudança.
- `/home/andrew/git/ansible-workstation/ai/roles/cao/handlers/main.yml`: reinício exige `cao_restart_on_change=true` e serviço habilitado. Padrão false.
- `/home/andrew/git/ansible-workstation/ai/cao-update.yml`: atualização explícita do CAO reutilizando cao.yml, sem importar gerenciamento de serviço ou sincronização MCP.
- `/home/andrew/git/ansible-workstation/ai/vars.example.yml` e `/home/andrew/git/ansible-workstation/ai/README.md`: exemplos de pin, main, PyPI, atualização e janela de manutenção.
- `/home/andrew/git/ansible-workstation/ai/tests/test_install_cao.py`: testes do helper e integração com wheels/Git/uv descartáveis e execução da tarefa Ansible real, sem executar a role inteira.

## PyPI versus upstream

Consulta direta às fontes oficiais em 2026-11-16 confirmou PyPI latest = **2.5.4**, e main = **3e30ea3ed6e7fb607b13358d81123afff5a8e69f**, também declarando versão 2.5.4. O código desse commit inclui `LaunchPlan.effort` e o transporte do esforço decidido (`upstream-types.txt`, `upstream-engine.txt`). Os documentos desse commit limitam o consumidor a agentes efêmeros com `effort: auto`; lançamentos de perfis instalados não consultam effort.route. As URLs estão em `UPSTREAM.json` e as cópias oficiais em `upstream-*.txt`.

Não foi criado/instalado decider, habilitado ponto de decisão ou contratado serviço externo. Não há alegação de validação ponta a ponta de esforço: esse trabalho entrega instalação/atualização configurável do core. O diagnóstico anterior APPROVED em `/home/andrew/git/central-de-incidentes/tasks/cao-decider-install/REVIEW.md` continua distinto desta mudança.

## Validação e evidências

`VALIDATION.json` registra argv, códigos, stdout/stderr. Todos os comandos finais retornaram zero:

- Syntax-check de `/home/andrew/git/ansible-workstation/ai/cao.yml`, `/home/andrew/git/ansible-workstation/ai/cao-update.yml` e `/home/andrew/git/ansible-workstation/ai/all.yml`.
- List-tasks de cao-update.yml: pré-requisitos comuns e CAO; não contém serviço/MCP.
- **15 testes aprovados**: 4 testes CAO novos (um com múltiplos cenários de integração) e 11 existentes de MCP. Cobrem instalação, repetição, pin, upgrade PyPI local, mudança PyPI→Git, branch que avança com mesma versão, upgrade explícito, volta ao SHA, extras/--with preservados, CLI JSON e tarefa Ansible real em execução normal e --check. Os testes finais usam uv offline com diretórios de ferramentas/bin/cache temporários.
- AST dos dois Python alterados, `git diff --check` e whitespace checks individuais dos oito arquivos aprovados.
- `uv tool list` real continua exibindo cli-agent-orchestrator v2.5.4. O servidor real segue PID **240075**, iniciado em **Fri Nov 13 13:42:29 2026**, com o mesmo comando documentado no diagnóstico anterior. Não foi enviada mensagem a sessões nem executado gerenciamento de serviço.

Avisos do syntax-check: inventário localhost implícito e deprecações preexistentes apt_key/apt_repository em browser/chrome.yml. Nenhum foi corrigido neste escopo.

Sondagens preliminares identificaram perda de extras pelo uv e dois detalhes de idempotência que foram corrigidos antes da validação final. Uma sondagem descartável usou inicialmente UV_NO_INDEX, que não desativa o índice; ela baixou pacotes oficiais PyPI dentro do ambiente temporário. O teste final usa UV_OFFLINE=true com cache isolado e não acessa o índice. Nenhum desses testes instalou no ambiente real do CAO.

## Preservação e limitações

`CHANGES.diff` inclui alterações de arquivos não rastreados contra cópias dos originais em `baseline/`, pois git diff comum não os exibe. Quatro originais foram reconstruídos do conteúdo inicial e conferidos contra hashes capturados antes da edição. O original de `ai/roles/cao/tasks/main.yml` veio da leitura inicial completa registrada no transcript: a primeira coleta de hashes excluiu qualquer componente de caminho chamado tasks e, por isso, não capturou hashes dos arquivos de tasks de roles. Essa limitação está explícita em `PRESERVATION.json`; não há alegação de hash inicial desse arquivo. Os outros **56 arquivos da baseline** mantêm os hashes originais.

Extras e --with preservados são aditivos; remoção/substituição de um pin auxiliar exige planejar uma recriação do ambiente. Pacotes ad hoc instalados no venv sem declaração no recibo não são preservados como requisitos explícitos. Requisitos auxiliares com campos desconhecidos falham antes da instalação.

Atualizar o venv compartilhado durante sessões ativas continua inadequado, mesmo sem reinício automático: processos existentes podem carregar módulos de versões distintas. Os comandos de aplicação documentados devem ser usados em janela de manutenção. Nenhuma aplicação no workstation foi iniciada.

## Comandos futuros (não executados)

```bash
ansible-playbook /home/andrew/git/ansible-workstation/ai/cao-update.yml -K
ansible-playbook /home/andrew/git/ansible-workstation/ai/cao-update.yml -K -e cao_git_ref=main
ansible-playbook /home/andrew/git/ansible-workstation/ai/cao-update.yml -K -e cao_source=pypi
```

O primeiro respeita o SHA configurado e pode atualizar dependências dentro das restrições. O segundo acompanha main. O terceiro atualiza o canal PyPI, que não deve ser confundido com main. Guarde overrides no mesmo arquivo de variáveis usado nas execuções futuras; -e não muda os defaults persistentes. Os pré-requisitos comuns podem executar APT; cao_upgrade sozinho não atualiza uv nem outros CLIs.
