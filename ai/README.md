# Stack de IA para Ubuntu

Playbooks Ansible para instalar **Codex CLI**, **Claude Code** e **CAO (CLI Agent
Orchestrator, da AWS Labs)**. Os CLIs ficam no home de um usuário comum já
existente, em `~/.local/bin`. O CAO usa `uv tool install`, com Python 3.12 isolado
e baixado automaticamente quando necessário. O Python do Ubuntu é preservado.

## Requisitos

- Destino: Ubuntu 22.04 ou superior, arquitetura x86_64 ou ARM64, acesso à internet,
  Python 3 e usuário com acesso a sudo. Reserve pelo menos 4 GB de RAM.
- Workstation/controlador: Ansible Core 2.16+; os playbooks executam localmente.
- Credenciais/assinatura de cada provedor para usar os agentes após a instalação.

No Ubuntu, prepare o controlador:

```bash
sudo apt-get update
sudo apt-get install -y ansible-core
```

Se a versão do Ansible do seu Ubuntu for anterior à 2.16 (como no Ubuntu 22.04),
use um ambiente separado no controlador:

```bash
sudo apt-get install -y python3-venv
python3 -m venv ~/.venvs/ansible
~/.venvs/ansible/bin/pip install 'ansible-core>=2.16,<2.20'
source ~/.venvs/ansible/bin/activate
```

Em um destino mínimo sem Python, instale `python3` antes da execução. As demais
dependências, incluindo `tmux`, Git, curl e ripgrep, são instaladas pelo playbook.
O componente Chrome DevTools instala suas dependências Node.js e Chrome por
subplaybooks. Não é necessário configurar uma conta AWS para estes provedores.

## Instalar a stack completa localmente

Execute como o usuário que utilizará os agentes:

```bash
cd /home/andrew/git/ansible-workstation
ansible-playbook ai/all.yml --ask-become-pass
```

Se o sudo não exige senha, omita `--ask-become-pass` (`-K`). As tarefas de sistema
usam root e os instaladores usam o usuário escolhido. Se executar como root,
informe `-e ai_stack_user=andrew` ou outro usuário comum existente.

Abra outro terminal ou ajuste o PATH da sessão atual:

```bash
export PATH="$HOME/.local/bin:$PATH"
codex --version
claude --version
cao --version
```

## Integração com a workstation

Os playbooks seguem o padrão do projeto: execução em `localhost`, com conexão
local, e um YAML por componente. O `all.yml` da raiz inclui `ai/all.yml` com a
tag `ai`. Para executar somente a stack de IA pelo playbook da workstation:

```bash
ansible-playbook all.yml --tags ai -K
```

| Arquivo | Responsabilidade |
| --- | --- |
| `ai/common.yml` | Dependências do Ubuntu e diretórios do usuário |
| `ai/codex.yml` | Codex CLI |
| `ai/claude.yml` | Claude Code |
| `ai/rtk.yml` | RTK OSS local shell filtering and native Codex/Claude hooks |
| `ai/herdr.yml` | herdr, multiplexador do backend experimental de terminal do CAO |
| `ai/cao-terminal-backend.yml` | Validação do backend e do herdr antes do serviço |
| `ai/node.yml` | Reaproveitar Node.js compatível ou instalar uma cópia local LTS |
| `ai/chrome-devtools.yml` | Dependências, pacote e registro do Chrome DevTools MCP |
| `ai/playwright-mcp.yml` | Dependências, pacote e registro do Playwright MCP local |
| `browser/chrome.yml` | Navegador Chrome, reutilizado pelo componente Chrome DevTools |
| `ai/uv.yml` | Gerenciador uv |
| `ai/cao.yml` | CAO e seu ambiente Python isolado |
| `ai/cao-update.yml` | Atualização explícita do CAO na origem/ref configurada |
| `ai/mcp.yml` | Sincronizador e perfis CAO com os MCPs dos clientes |
| `ai/cao-service.yml` | Serviço systemd opcional |
| `ai/all.yml` | Sequência completa da stack de IA |

As roles ficam em `ai/roles`, junto aos playbooks que as utilizam. Não há um
inventário ou `ansible.cfg` separado para a stack.

## Subplaybooks e tags

Os instaladores incluem as dependências comuns e podem ser executados
separadamente. O serviço pressupõe que o CAO já esteja instalado:

```bash
ansible-playbook ai/common.yml -K
ansible-playbook ai/codex.yml -K
ansible-playbook ai/claude.yml -K
ansible-playbook ai/herdr.yml -K
ansible-playbook ai/node.yml -K
ansible-playbook ai/chrome-devtools.yml -K
ansible-playbook ai/uv.yml -K
ansible-playbook ai/cao.yml -K
ansible-playbook ai/mcp.yml -K
ansible-playbook ai/cao-service.yml -K -e cao_service_enabled=true
```

Também é possível selecionar componentes no principal:

```bash
ansible-playbook ai/all.yml --tags codex,claude -K
ansible-playbook ai/all.yml --tags cao -K
```

O subplaybook do CAO instala o orquestrador. O de MCPs também garante o CAO
antes de configurar os perfis; instale pelo menos um dos clientes para lançar
agentes. O serviço é configurado separadamente e permanece opcional.

## RTK OSS shell filtering

RTK is an optional component of `ai/all.yml`, enabled by default. Its standalone
entry point imports `ai/common.yml` for stack prerequisites and PATH setup.
The release source is [rtk-ai/rtk](https://github.com/rtk-ai/rtk), pinned to the
audited OSS release `1.2.0`, with mandatory official checksum verification.
Clients default to `[claude_code, codex]`. Native hooks filter shell-tool output;
RTK does not change provider URLs, MCP configuration or sandbox permissions.
Unselected hooks and instructions are preserved. New client/CAO sessions load
the merged hooks; their launch environment must include the stack bin directory.
Live authenticated agent behavior has not been tested by this integration.

Commands for validation, followed by optional application after review:

```bash
ansible-playbook /home/andrew/git/ansible-workstation/ai/rtk.yml --syntax-check
ansible-playbook /home/andrew/git/ansible-workstation/ai/all.yml --list-tasks --tags rtk
# Review predicted changes before applying in a maintenance window:
ansible-playbook /home/andrew/git/ansible-workstation/ai/rtk.yml --check --diff -K
ansible-playbook /home/andrew/git/ansible-workstation/ai/rtk.yml -K
# Apply another reviewed release pin:
ansible-playbook /home/andrew/git/ansible-workstation/ai/rtk.yml -K -e rtk_version=VERSION
# Explicitly resolve and refresh the latest release:
ansible-playbook /home/andrew/git/ansible-workstation/ai/rtk.yml -K -e rtk_version=latest -e rtk_upgrade=true
```

`latest` resolves on installation or explicit upgrade; ordinary runs keep the
installed release. `rtk_upgrade` inherits `ai_stack_upgrade`; a fixed version
remains fixed. Use `-e rtk_enabled=false` to skip RTK in `ai/all.yml` and use
`--tags rtk` to select its import with prerequisites. No RTK installation or
session restart was performed while adding these entry points.

## herdr e backend de terminal do CAO

O CAO usa tmux por padrão, mas este repositório configura o serviço com o
backend **herdr-app** (`cao_terminal_backend`), que usa o herdr-core do
aplicativo gráfico Herdr. Também há o backend **herdr** (interface de terminal),
marcado como **experimental** pelo próprio CAO: um multiplexador em Rust que
informa o estado dos agentes. `ai/all.yml` instala o herdr de terminal por padrão.

A origem é o repositório oficial [herdrdev/herdr](https://github.com/herdrdev/herdr),
fixada na release `0.9.5`, a versão de referência do CAO instalado. O binário
Linux (x86_64 ou ARM64) é conferido pelo SHA256 do manifesto oficial
`https://herdr.dev/latest.json`, pelo digest do GitHub e pelo pin auditado antes
de ser executado. Ele fica em `~/.local/share/ai-stack/herdr`, com o comando
`~/.local/bin/herdr`. Outras arquiteturas são omitidas com aviso. A role não
inicia servidor herdr nem altera `~/.config/herdr`. Detalhes em
`ai/roles/herdr/README.md`.

```bash
ansible-playbook ai/herdr.yml --syntax-check
ansible-playbook ai/all.yml --list-tasks --tags herdr
ansible-playbook ai/herdr.yml --check --diff -K
ansible-playbook ai/herdr.yml -K
# Aplicar outro pin revisado:
ansible-playbook ai/herdr.yml -K -e herdr_version=VERSAO
# Resolver e verificar explicitamente a última release:
ansible-playbook ai/herdr.yml -K -e herdr_version=latest -e herdr_upgrade=true
```

`latest` só é resolvido na instalação ou com `herdr_upgrade=true`/
`ai_stack_upgrade=true`. Para omitir o herdr da stack, use
`-e herdr_enabled=false`. Não use `herdr update` nem `herdr channel set` nesta
instalação: a próxima execução do playbook detecta o binário alterado e restaura
o pin configurado.

### herdr-pastor: o editor como pastor, os agentes como ovelhas

A role também instala `~/.local/bin/herdr-pastor`, que abre um workspace herdr
com o seu editor à esquerda e os agentes empilhados à direita:

```
┌──────────────────┬──────────┐
│                  │ 🐑 claude│
│  🧑‍🌾 pastor        ├──────────┤
│  ($EDITOR)       │ 🐑 codex │
└──────────────────┴──────────┘
```

```bash
herdr-pastor                     # workspace no diretório atual
herdr-pastor ~/git/projeto       # outro diretório
herdr-pastor --session trabalho  # sessão herdr nomeada
herdr-pastor --no-attach         # não anexar ao final
```

O workspace recebe o rótulo `🧑‍🌾 <nome do diretório>`. O editor é
`${VISUAL:-${EDITOR:-vi}}`. As ovelhas vêm de `herdr_pastor_sheep`
(`[claude, codex]`). Agentes suportados pelo herdr são iniciados com
`herdr agent start` (nomes `claude-wN`, `codex-wN`; uma ovelha repetida vira
`claude-2-wN`), e os demais com `herdr pane run`. Uma ovelha fora do PATH é
ignorada com aviso; qualquer outra falha do herdr interrompe o comando com
saída 1 e a mensagem de erro. Sem
`--session`, o comando usa a sessão atual quando executado dentro do herdr, ou a
sessão `default`. Ele nunca usa a sessão `cao` do CAO, a menos que você peça
com `--session cao`. Se o servidor da sessão não estiver em execução, o comando
o inicia em segundo plano (`herdr --session NOME server`). Fora do herdr, ele
anexa à sessão no final. Na instalação, a role só grava o script: não inicia
servidor nem altera `~/.config/herdr`. Para remover o comando, use
`-e herdr_pastor_enabled=false`.

### Escolher o backend do cao-server

A escolha vale para cada processo `cao-server`, nesta ordem:
`cao-server --terminal <tmux|herdr|herdr-app>` > variável `CAO_TERMINAL_BACKEND` >
`terminal.backend` nas configurações do CAO > `tmux`.

Antes de trocar o backend:

- encerre todas as sessões do CAO (`cao session list` e
  `cao shutdown --session NOME`). As sessões **não migram** entre backends:
  sessões tmux não aparecem em um servidor herdr, e vice-versa;
- pare o `cao-server` atual. A troca exige **reiniciar** o servidor;
- nunca execute dois `cao-server` com o mesmo home do CAO
  (`~/.aws/cli-agent-orchestrator`, ou `CAO_HOME_DIR`), por exemplo um com tmux e
  outro com herdr: eles compartilham banco de dados e estado.

Execução manual, em primeiro plano:

```bash
# herdr (experimental)
cao-server --host 127.0.0.1 --port 9889 --terminal herdr
# Voltar ao tmux, após encerrar as sessões e parar o servidor herdr:
cao-server --host 127.0.0.1 --port 9889 --terminal tmux
```

Com o backend herdr, o CAO cria seus workspaces na sessão herdr `cao`
(`terminal.herdr_session`/`CAO_HERDR_SESSION`) e inicia
`herdr --session cao server` se ela não estiver em execução. Para acompanhar os
agentes, execute `herdr --session cao`.

Com o serviço systemd opcional, defina `cao_terminal_backend`:

```bash
ansible-playbook ai/cao-service.yml -K -e cao_service_enabled=true -e cao_terminal_backend=herdr
```

Com `tmux` (padrão), a unidade não recebe `--terminal` e permanece idêntica à
anterior; `CAO_TERMINAL_BACKEND` em `~/.config/ai-stack/environment` ou as
configurações do CAO continuam valendo. Com `herdr` ou `herdr-app`, o `ExecStart` recebe
`--terminal <backend>`, que prevalece sobre esses valores. Em `ai/all.yml`,
`ai/cao-terminal-backend.yml` roda antes do serviço: valores diferentes de `tmux`,
`herdr` e `herdr-app` são recusados nessa etapa. Com o serviço habilitado, `herdr` exige o
comando instalado; no `--check`, basta `herdr_enabled=true`. Para uma execução
avulsa de `ai/cao-service.yml`, a validação também é executada automaticamente.
Opcionalmente, valide o backend isoladamente:

```bash
ansible-playbook ai/cao-terminal-backend.yml -e cao_service_enabled=true -e cao_terminal_backend=herdr
```

Por padrão, o playbook não reinicia um servidor que já esteja em execução;
ele inicia o serviço se estiver parado. Mesmo com a unidade atualizada, o servidor
em execução mantém o backend anterior até ser reiniciado. Em uma janela de
manutenção, sem sessões abertas, reinicie a unidade definida em `cao_service_name` (padrão `cao-server`), por exemplo
`sudo systemctl restart cao-server`. Com
`cao_restart_on_change=true`, o handler reinicia o serviço ao mudar a unidade e
encerra as sessões abertas; use somente sem sessões em uso. Processos iniciados
pelo serviço, incluindo o servidor herdr, terminam junto com a unidade.

Para voltar ao tmux pelo playbook, use `-e cao_terminal_backend=tmux` e reinicie o serviço da mesma forma.


### Usar o aplicativo gráfico Herdr com o CAO

O fork fixado inclui o backend experimental `herdr-app` do
[PR #1356](https://github.com/awslabs/cli-agent-orchestrator/pull/1356), além das
variáveis por perfil do PR #665. Cada sessão nova do CAO aparece como um espaço,
com uma aba por terminal e os status nativos dos agentes. O backend `herdr`
continua disponível para a interface de terminal antiga.

O backend gráfico exige **herdr-core 0.1.21+** (`hc --version`), instalado com o
aplicativo Herdr. A role `herdr` deste repositório instala a interface antiga;
ela não instala o aplicativo gráfico nem o core. O preflight verifica o `hc`
em `herdr_core_binary` (padrão `~/.local/bin/hc`), sem iniciar sessão e inclusive
em `--check`. Ter apenas o binário `herdr` não satisfaz esse requisito.

Primeiro atualize a instalação do CAO para o commit fixado:

```bash
ansible-playbook ai/cao.yml -K
```

Para configurar a unidade, após encerrar as sessões e parar o servidor na janela
de manutenção descrita acima:

```bash
ansible-playbook ai/cao-service.yml -K -e cao_service_enabled=true -e cao_terminal_backend=herdr-app
```

Também é possível iniciar manualmente com `cao-server --terminal herdr-app`.
O core usa uma sessão separada chamada `cao`
(`terminal.herdr_app_session` / `CAO_HERDR_APP_SESSION`). Para mostrá-la no
aplicativo instalado na mesma máquina:

```bash
hc machine add --via "sh -c" --name cao-local --session cao
```

Em outra máquina, use `hc machine add <host-ssh> --session cao`. Crie sessões
novas do CAO nesse backend; os processos existentes no herdr antigo não são
transferidos. O script upstream `scripts/herdr_tui_to_app.py` é opcional para
trabalho pessoal na TUI e ignora a sessão `cao` por padrão. A aplicação destes
playbooks mantém `cao_restart_on_change=false` e o backend padrão `tmux`.


## Instalar Chrome DevTools MCP e suas dependências

`ai/all.yml` instala o Chrome DevTools MCP antes de sincronizar os perfis do
CAO. Para instalar apenas esse componente:

```bash
ansible-playbook ai/chrome-devtools.yml -K
# Se já usa o CAO, atualize seus perfis em seguida:
ai-stack-sync-mcps
```

Esse subplaybook chama `ai/codex.yml` e `ai/claude.yml` para garantir os clientes
selecionados, `ai/node.yml` para garantir Node.js e `browser/chrome.yml` para
garantir o navegador. As instalações existentes são reutilizadas.

O Node.js é procurado no PATH, no NVM do usuário e no diretório gerenciado pela
stack. Se não houver versão compatível, `ai/node.yml` baixa uma versão LTS da
linha 24 do site oficial, confere o SHA256 e a extrai em
`~/.local/share/ai-stack/node`. O Node.js do sistema e a versão padrão do NVM são
preservados. O runtime encontrado fica registrado por caminho absoluto no
comando do MCP, para funcionar também com o PATH reduzido das sessões do CAO.

O pacote npm é instalado em `~/.local/share/ai-stack/chrome-devtools`, com um
comando estável em `~/.local/bin/chrome-devtools-mcp`. O playbook registra esse
comando como `chrome-devtools` nos MCPs globais dos clientes selecionados, sem
alterar os outros servidores configurados. Verifique no Codex:

```bash
codex mcp get chrome-devtools --json
```

Para executar sem interface gráfica, use
`-e '{"chrome_devtools_args":["--headless"]}'`. Para selecionar apenas Codex, use
`-e '{"chrome_devtools_clients":["codex"]}'`.

O Chrome oficial instalado por APT é x86_64. Em ARM64, o componente é omitido por
padrão em `ai/all.yml`; para usar um Chrome remoto, execute o subplaybook com
`chrome_devtools_install_browser=false` e configure `chrome_devtools_args` com
`--browser-url=http://HOST:PORTA`. É possível desativar esse componente na stack
com `-e chrome_devtools_enabled=false`.

## Instalar Playwright MCP local

`ai/all.yml` instala o Playwright MCP e registra o servidor `playwright` no
Codex e no Claude Code, antes da sincronização com o CAO. Para instalar apenas
esse componente e atualizar os perfis do CAO existentes:

```bash
ansible-playbook ai/playwright-mcp.yml -K
ai-stack-sync-mcps
codex mcp get playwright --json
```

O pacote `@playwright/mcp` fica em `~/.local/share/ai-stack/playwright`, com
o comando `~/.local/bin/playwright-mcp`. Por padrão, usa o Chrome local
(`--browser chrome`) em um perfil próprio. O subplaybook prepara Node.js, os
clientes selecionados e, em x86_64, o Chrome. Não conecta automaticamente ao
perfil pessoal nem instala a extensão do navegador.

Use `playwright_mcp_clients`, `playwright_mcp_version` e
`playwright_mcp_args` para ajustar o registro; por exemplo, use
`-e '{"playwright_mcp_args":["--browser","chrome","--headless"]}'` sem
interface gráfica. Desative a instalação automática na stack com
`-e playwright_mcp_enabled=false`. Em ARM64, a stack omite esse componente por
padrão; para configurá-lo manualmente, defina
`playwright_mcp_install_browser=false` e argumentos compatíveis com um
navegador já disponível.

## Autenticar e usar

Execute no destino, como o mesmo usuário informado em `ai_stack_user`:

```bash
codex login
claude
```

Conclua os fluxos de autenticação interativa de cada CLI. Em um servidor sem
navegador, o Codex também oferece `codex login --device-auth`.

Para usar chaves de API, configure-as no ambiente desse usuário:

```bash
read -rsp 'OpenAI API key: ' OPENAI_API_KEY; echo
export OPENAI_API_KEY
printf '%s' "$OPENAI_API_KEY" | codex login --with-api-key
read -rsp 'Anthropic API key: ' ANTHROPIC_API_KEY; echo
export ANTHROPIC_API_KEY
```

O playbook não realiza login nem grava chaves. Autentique antes de iniciar o
servidor e as sessões. O CAO coordena os agentes em terminais tmux; não instala
modelos para inferência local.

Em um terminal, inicie o servidor:

```bash
cao-server --host 127.0.0.1 --port 9889
```

Em outro terminal, entre no projeto e escolha um provedor:

```bash
cd /caminho/do/projeto

# Claude Code
cao launch --agents mala_supervisor_claude --session-name projeto-claude

# Ou Codex
cao launch --agents mala_supervisor_codex --session-name projeto-codex
```

Cada perfil `mala_*` já determina o provedor correspondente.
Para acompanhar e encerrar, consulte os nomes completos das sessões:

```bash
cao session list
cao shutdown --session cao-projeto-claude
```

## Reutilizar os MCPs do Codex e Claude nas sessões do CAO

A stack instala `ai-stack-sync-mcps` e o executa depois da instalação do CAO.
Ele lê os MCPs globais do mesmo usuário dos agentes:

- Codex: `~/.codex/config.toml`, tabela `mcp_servers`.
- Claude Code: `~/.claude.json`, objeto `mcpServers`.

Os arquivos dos clientes são apenas lidos. As definições de perfis são instaladas
em `~/.local/share/ai-stack/profiles/`; os perfis utilizáveis ficam no agent store.
Execute `ansible-playbook ai/mcp.yml -K` para instalar e sincronizar os perfis:

| Função e nível | Codex | Claude | Esforço padrão |
| --- | --- | --- | --- |
| Supervisor | `mala_supervisor_codex` | `mala_supervisor_claude` | medium |
| Desenvolvimento simples | `mala_developer_low_codex` | `mala_developer_low_claude` | low |
| Desenvolvimento intermediário | `mala_developer_medium_codex` | `mala_developer_medium_claude` | medium |
| Desenvolvimento complexo | `mala_developer_high_codex` | `mala_developer_high_claude` | high |
| Revisão simples/intermediária | `mala_reviewer_basic_codex` | `mala_reviewer_basic_claude` | low |
| Revisão de alto risco | `mala_reviewer_advanced_codex` | `mala_reviewer_advanced_claude` | high |

### Segunda conta do Claude Code

`cao_claude_accounts` cria uma família extra de perfis para cada conta Claude, com
`CLAUDE_CONFIG_DIR` próprio e, portanto, limite de uso próprio. O padrão é a conta `b`
em `~/.claude-b`, que gera `mala_<perfil>_claude_b` (por exemplo,
`mala_developer_medium_claude_b`) com os mesmos MCPs globais do Claude. O playbook cria o
diretório com `skipDangerousModePermissionPrompt` e avisa enquanto faltar o login, que é
manual e feito uma vez por conta:

```bash
CLAUDE_CONFIG_DIR=$HOME/.claude-b claude /login
ansible-playbook ai/mcp.yml -K
```

Requer um CAO com `env:` por perfil
([awslabs/cli-agent-orchestrator#665](https://github.com/awslabs/cli-agent-orchestrator/pull/665)).
Enquanto o PR não é integrado, `cao_git_url` aponta para o fork
`malacration/cli-agent-orchestrator`; o playbook falha antes de gerar os perfis se o CAO
instalado ignorar `env:`. Use `cao_claude_accounts: []` para desativar.

O supervisor trata cada conta como uma cota separada: começa por `claude`, passa para
`claude_b` quando a primeira esgota e só então usa Codex. `[provider: claude_b]` fixa a
conta extra.

O supervisor registra nível, motivo e provedor no arquivo da tarefa. Por padrão,
desenvolvimento usa Claude Opus e revisão usa Codex; pode escolher Codex para
implementar e Claude para revisar. `[provider: claude|codex]` ou
`[provedor: claude|codex]` determina o provedor dos workers. `[level: low|medium|high]`
ou `[nivel: baixo|medio|médio|alto]` determina a complexidade. Após duas rejeições,
o desenvolvedor sobe um nível. Segurança, produção ou perda de dados exigem revisão
avançada independentemente do nível.

Ao detectar limite de uso, o supervisor verifica se o worker parou, remove seu
terminal, registra a troca e reatribui o mesmo arquivo ao perfil equivalente do outro
provedor. Evita o provedor esgotado durante a sessão; se ambos estiverem esgotados,
para e informa o usuário.

Ajuste `cao_profile_efforts` e `cao_profile_models` no inventário ou arquivo de
variáveis, usando os dicionários completos de `ai/vars.example.yml`. Para fixar um
modelo concreto, por exemplo, defina `cao_profile_models.developer_high.claude`
com o identificador desejado e execute novamente o playbook. `null` usa o modelo
padrão do CLI. Codex aceita esforços minimal, low, medium, high e xhigh; Claude
aceita low, medium, high e xhigh.

O supervisor pode escrever arquivos de tarefas; o revisor pode escrever revisões e
executar verificações, sem editar o código revisado. Na migração, `--prune` remove
perfis antigos `ai_stack_*` com a marca de gerenciamento e definições obsoletas
marcadas.
Arquivos sem marca no agent store e links simbólicos são preservados.

```bash
cao launch --agents mala_supervisor_codex --session-name projeto-codex
# Ou:
cao launch --agents mala_supervisor_claude --session-name projeto-claude
```

Isso inclui explicitamente os MCPs no perfil do Claude, mesmo quando o CAO usa
`--strict-mcp-config`. No Codex, os MCPs HTTP continuam usando a URL e a
autenticação da configuração global original. Eles são herdados diretamente pelo
Codex e concedidos em `allowedTools`, sem entrar em `mcpServers` do perfil CAO:
isso evita que o CAO acrescente `env_vars`, opção inválida para HTTP no Codex.
Os MCPs stdio continuam sendo incluídos explicitamente no perfil. Cada cliente usa seus próprios MCPs,
sem mesclar configurações ou tokens de clientes diferentes.

Ao adicionar, alterar ou remover um MCP nos clientes, sincronize novamente:

```bash
ai-stack-sync-mcps --check  # Informa se os perfis precisam ser atualizados.
ai-stack-sync-mcps
# Ou pelo Ansible:
ansible-playbook ai/mcp.yml -K
```

Inicie uma nova sessão do CAO para carregar as mudanças. Arquivos sem a marca de gerenciamento são preservados. Os perfis gerados são arquivos `0600` e
devem ser regenerados, pois podem conter valores de ambiente vindos dos MCPs.
O resumo da sincronização mostra nomes de perfis e servidores, sem credenciais.

São importadas as configurações globais. Configurações apenas de um projeto,
conectores da conta Claude e arquivos de autenticação OAuth não são importados.
O sincronizador não instala os programas dos MCPs. O Chrome DevTools possui o
instalador próprio descrito acima; para outros MCPs, seus comandos e dependências
precisam existir no destino, como no uso direto pelo cliente.
Conclua o OAuth de cada cliente e, se ele pedir novamente na sessão CAO, autorize
pelo fluxo do próprio cliente. Variáveis de ambiente necessárias aos MCPs também
precisam estar no ambiente de `cao-server`; para systemd, use o arquivo
`~/.config/ai-stack/environment` descrito abaixo.

Por exemplo, para registrar o ClickUp diretamente nos clientes:

```bash
codex mcp add clickup --url https://mcp.clickup.com/mcp
claude mcp add --transport http --scope user clickup https://mcp.clickup.com/mcp

ai-stack-sync-mcps
```

O ClickUp requer OAuth; no Codex, use `codex mcp login clickup`. No Claude, abra
`/mcp` para concluir a autenticação. Estes comandos de cadastro são manuais e não
são executados pelo playbook.

## Servidor CAO com systemd (opcional)

Depois de instalar o CAO, em uma máquina Ubuntu com systemd habilite o serviço:

```bash
ansible-playbook ai/cao-service.yml -K -e cao_service_enabled=true
sudo systemctl status cao-server
sudo journalctl -u cao-server -f
```

O serviço inicia no boot como `ai_stack_user`, escutando em `127.0.0.1:9889`.
A unidade chama-se `cao-server` por padrão; `cao_service_name` permite alterá-la.
Para chaves ou tokens necessários ao processo do servidor, crie no destino
`~/.config/ai-stack/environment` com entradas `NOME=valor`, sem `export`, permissão
`0600`, e reinicie o serviço. Variáveis exportadas em um terminal não são
herdadas pelo serviço systemd. Logins dos CLIs ficam no home do mesmo usuário.

Para acessar a interface de uma máquina remota, use um túnel SSH:

```bash
ssh -L 9889:127.0.0.1:9889 ubuntu@seu-servidor
```

Depois abra `http://127.0.0.1:9889`. Se habilitou o serviço anteriormente,
`cao_service_enabled=false` apenas deixa de gerenciá-lo. Para interrompê-lo e
retirá-lo do boot, execute fora de uma sessão CAO (terminal comum ou SSH):
`sudo systemctl disable --now cao-server`.

Ao habilitar o serviço, a role verifica a unidade antiga `cao-server-<usuário>`.
Uma unidade ativa encerra todas as sessões CAO ao ser parada: a migração falha
antes de alterar a stack, salvo se `cao_restart_on_change=true` for informado
em uma janela de manutenção. Essa verificação também é executada no início de `ai/all.yml`.
Unidades legadas não reconhecidas são recusadas.
Em modo `--check`, a role informa a migração prevista sem alterar unidades.
Com `cao_service_enabled=false`, ela não gerencia serviços; para migrar manualmente
em janela de manutenção, execute fora de uma sessão CAO (terminal comum ou SSH),
confira o conteúdo da unidade antiga e execute:

```bash
sudo systemctl cat "cao-server-$(id -un).service"  # Confira antes de parar e remover.
sudo systemctl disable --now "cao-server-$(id -un).service"
sudo rm "/etc/systemd/system/cao-server-$(id -un).service"
sudo systemctl daemon-reload
ansible-playbook ai/cao-service.yml -K -e cao_service_enabled=true
```

## Versões, atualização e configuração

As configurações ficam nos `defaults/main.yml` das roles e podem ser sobrescritas
pelo inventário ou por `-e`. Há um exemplo em `ai/vars.example.yml`:

```bash
ansible-playbook ai/all.yml -K -e @ai/vars.example.yml
```

| Variável | Padrão | Finalidade |
| --- | --- | --- |
| `ai_stack_user` | Usuário conectado/original do sudo | Usuário dos agentes |
| `ai_stack_upgrade` | `false` | Executar novamente os instaladores e atualizar CAO |
| `codex_version` | `latest` | Versão numérica ou `latest` |
| `claude_version` | `stable` | Versão numérica, `stable` ou `latest` |
| `cao_uv_version` | `latest` | Versão do uv: numérica ou `latest` |
| `cao_source` | `git` | Origem do CAO: `git` ou `pypi` |
| `cao_git_url` | `https://github.com/malacration/cli-agent-orchestrator.git` | Fork com os PRs #665 e #1356 |
| `cao_git_ref` | `ab50597f0caddf8efb30a466cb1fe02a1c9809b0` | Merge verificado dos PRs #665 e #1356 no fork; aceita tag/branch/SHA |
| `cao_version` | `latest` | Versão PyPI, usada apenas com `cao_source=pypi` |
| `cao_upgrade` | Valor de `ai_stack_upgrade` | Consultar atualizações apenas do pacote CAO |
| `cao_extras` | `[]` | Acrescentar extras aos já declarados no recibo uv |
| `cao_with_packages` | `[]` | Acrescentar dependências `--with` às já declaradas no recibo uv |
| `cao_install_spec` | Derivado da origem/ref/versão | Override PEP 508 com nome explícito `cli-agent-orchestrator` |
| `cao_python_version` | `3.12` | Python usado pelo ambiente do CAO |
| `cao_service_enabled` | `false` | Habilitar o serviço systemd |
| `cao_service_name` | `cao-server` | Nome da unidade systemd |
| `cao_service_legacy_names` | `[cao-server-<usuário>]` | Nomes antigos a migrar após validação |
| `cao_restart_on_change` | `false` | Permitir o handler de reinício, se o serviço estiver habilitado |
| `herdr_enabled` | `true` | Incluir o herdr em `ai/all.yml` |
| `herdr_version` | `0.9.5` | Pin auditado ou `latest` |
| `herdr_upgrade` | Valor de `ai_stack_upgrade` | Reconsultar e reverificar o release do herdr |
| `herdr_checksum` | vazio | Pin adicional opcional `sha256:HEX` do binário |
| `herdr_pastor_enabled` | `true` | Instalar o comando `herdr-pastor` (`false` o remove) |
| `herdr_pastor_sheep` | `[claude, codex]` | Agentes (ovelhas) à direita do editor, de cima para baixo |
| `cao_terminal_backend` | `herdr-app` | Backend do serviço: `tmux`, `herdr` (TUI) ou `herdr-app` (core), experimentais |
| `herdr_core_binary` | `~/.local/bin/hc` | Executável herdr-core 0.1.21+ exigido pelo backend gráfico |
| `cao_mcp_sync_enabled` | `true` | Gerar perfis CAO com os MCPs dos clientes |
| `cao_mcp_clients` | `[codex, claude_code]` | Clientes cujos MCPs serão reutilizados |
| `cao_mcp_profiles` | Seis perfis da tabela acima | Perfis base a sincronizar |
| `cao_profile_efforts` | Níveis da tabela acima | Esforço por perfil e provedor |
| `cao_mcp_profile_prefix` | `mala` | Prefixo dos perfis gerados |
| `cao_profile_models` | Opus para desenvolvedores Claude; demais `null` | Modelo por perfil e provedor |
| `cao_mcp_prune_prefixes` | `[ai_stack]` | Prefixos legados gerenciados a remover |
| `ai_node_major` | `24` | Linha LTS usada quando falta um Node compatível |
| `chrome_devtools_enabled` | `true` em x86_64 | Incluir Chrome DevTools em `ai/all.yml` |
| `chrome_devtools_install_browser` | `true` | Chamar o subplaybook de instalação do Chrome |
| `chrome_devtools_version` | `latest` | Versão do pacote npm; atualização com `ai_stack_upgrade=true` |
| `chrome_devtools_clients` | `[codex, claude_code]` | Clientes onde registrar o MCP |
| `chrome_devtools_args` | `[]` | Argumentos do servidor, como `--headless` |

Uma reexecução mantém os CLIs instalados quando a versão solicitada já está
presente. Alterar uma versão numérica reinstala o componente. `latest`/`stable`
não consultam novas versões em toda execução. Para atualizar explicitamente:

```bash
ansible-playbook ai/all.yml -K -e ai_stack_upgrade=true
```

Os mecanismos próprios de atualização dos CLIs continuam ativos; fixar uma versão
no playbook define a versão aplicada na execução, sem bloquear atualizações
posteriores feitas pelo próprio CLI.

### Atualizar CAO e escolher a origem

`latest` no PyPI e `main` upstream são canais diferentes. Em 2026-11-16, o PyPI
publicava `2.5.4`; o commit upstream padrão deste playbook também declara `2.5.4`,
mas já transporta esforço decidido no plano de lançamento para agentes efêmeros
com `effort: "auto"`. A release PyPI não tem esse consumidor. Veja a
[documentação no commit fixado](https://github.com/malacration/cli-agent-orchestrator/blob/ab50597f0caddf8efb30a466cb1fe02a1c9809b0/docs/decisions.md).
Lançamentos de perfis instalados continuam sem consultar `effort.route` nesse
commit. Instalar esse core não instala um classificador nem habilita decisões;
uma validação funcional posterior precisa conferir o consumidor e os providers.

O padrão usa um SHA para repetibilidade. Alterar origem, ref, versão ou Python
reconcilia a instalação na próxima execução. Com a mesma solicitação e recibo,
uma execução normal mantém a revisão instalada, inclusive para uma branch móvel.
Para atualizar o CAO explicitamente, execute em uma janela de manutenção:

```bash
# Reaplicar o pin configurado e atualizar dependências dentro das restrições:
ansible-playbook /home/andrew/git/ansible-workstation/ai/cao-update.yml -K
# Acompanhar o main oficial (cada execução explícita consulta a branch):
ansible-playbook /home/andrew/git/ansible-workstation/ai/cao-update.yml -K -e cao_git_ref=main
# Alternativa equivalente sem o subplaybook de atualização:
ansible-playbook /home/andrew/git/ansible-workstation/ai/cao.yml -K -e cao_upgrade=true -e cao_git_ref=main
# Voltar a um commit previamente validado:
ansible-playbook /home/andrew/git/ansible-workstation/ai/cao.yml -K -e cao_git_ref=SHA_VALIDADO
# Última release publicada ou pin de release PyPI:
ansible-playbook /home/andrew/git/ansible-workstation/ai/cao-update.yml -K -e cao_source=pypi
ansible-playbook /home/andrew/git/ansible-workstation/ai/cao.yml -K -e cao_source=pypi -e cao_version=2.5.4
```

Esses comandos reutilizam os pré-requisitos comuns da role (APT e diretórios),
mas não atualizam os outros CLIs ou o uv com `ai_stack_upgrade=false`. Guarde as
variáveis de origem/ref no seu arquivo de inventário/extra vars e use o mesmo
arquivo nas execuções futuras; um `-e` isolado não muda os defaults persistentes.
Um SHA ou uma versão fixa permanece restrito mesmo com `cao_upgrade=true`.

O instalador preserva os extras e requisitos `--with` declarados no
`uv-receipt.toml`, inclusive ao migrar PyPI → Git, e permite acrescentar requisitos
com `cao_extras` e `cao_with_packages`. Pacotes instalados manualmente dentro do
venv sem constar nesse recibo não são declarações gerenciadas. Os requisitos
preservados são aditivos; para trocar/remover um extra ou pin auxiliar, revise
o recibo e planeje uma recriação explícita do ambiente. Formatos de recibo não
suportados falham antes da instalação, sem descartar silenciosamente requisitos.
Plugins de decisões só devem ser declarados com fonte conhecida; este playbook
não inclui nem instala decider hospedado.

The CAO helper uses `packaging>=24.2,<27` in its separate `uv run` environment
to compare normalized PEP 508 requirements, including distribution/extra aliases
and equivalent version specifiers. This parser is not added to CAO's tool
requirements. Receipt-level constraints, overrides and unsupported nonempty
resolution options cause refusal before `uv tool install`, rather than losing
operator pins. The supported `find-links` option is replayed explicitly. Review
unsupported receipt state before planning a replacement environment; the helper
does not remove it automatically.

`cao_restart_on_change=false` impede o handler de reinício, inclusive quando
`cao_service_enabled=true`. A atualização do venv compartilhado deve acontecer
quando não houver sessões em uso: processos existentes podem manter código
antigo em memória ou carregar módulos novos. Após a manutenção, planeje o
reinício separadamente; para permitir o handler em uma execução autorizada, use
`cao_restart_on_change=true` junto de `cao_service_enabled=true`. O subplaybook
de atualização não importa o gerenciamento de serviços nem a sincronização MCP.

Os instaladores oficiais são baixados antes de serem executados. As variáveis
`codex_installer_checksum`, `claude_installer_checksum` e `cao_uv_installer_checksum`
aceitam `sha256:HASH` para conferir também o script baixado.

## Validação

```bash
ansible-playbook ai/all.yml --syntax-check
ansible-playbook ai/all.yml --list-tasks
ansible-playbook ai/all.yml --check --diff -K
```

`--check` inspeciona versões existentes e prevê as alterações de configuração,
sem executar instaladores ou iniciar serviços. A resolução e instalação dos
pacotes do CAO são verificadas na execução real. Em imagens mínimas do Ubuntu,
instale também `python3-apt` antes de usar `--check`; na execução normal, o módulo
APT do Ansible pode instalar essa dependência automaticamente.

Os testes do sincronizador usam o Python do ambiente CAO, que já contém suas
dependências. A partir da raiz de `ansible-workstation`, execute:

```bash
"$(uv tool dir)/cli-agent-orchestrator/bin/python" -m unittest discover -s ai/tests -v
```

Os testes de instalação/upgrade do CAO usam wheels e um Git local descartáveis,
com `UV_TOOL_DIR`, `UV_TOOL_BIN_DIR` e `UV_CACHE_DIR` temporários e uv offline:

```bash
python3 -m unittest discover -s /home/andrew/git/ansible-workstation/ai/tests -p test_install_cao.py -v
```

Para validar o MCP instalado e a abertura do Chrome em um perfil temporário,
isolado e sem interface gráfica:

```bash
"$(uv tool dir)/cli-agent-orchestrator/bin/python" ai/tests/check_chrome_devtools.py
```

## Referências oficiais

- [Codex CLI](https://developers.openai.com/codex/cli/)
- [Instalação do Claude Code](https://code.claude.com/docs/en/setup)
- [Instalação do uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Instalação do CAO](https://awslabs.github.io/cli-agent-orchestrator/docs/getting-started/installation/)
- [CAO com Codex](https://github.com/awslabs/cli-agent-orchestrator/blob/main/docs/codex-cli.md)
- [CAO com Claude Code](https://github.com/awslabs/cli-agent-orchestrator/blob/main/docs/claude-code.md)
- [MCP no Codex](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [MCP no Claude Code](https://code.claude.com/docs/en/mcp)
- [MCP oficial do ClickUp](https://developer.clickup.com/docs/connect-an-ai-assistant-to-clickups-mcp-server)
- [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp)
