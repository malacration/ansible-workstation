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
| `ai/node.yml` | Reaproveitar Node.js compatível ou instalar uma cópia local LTS |
| `ai/chrome-devtools.yml` | Dependências, pacote e registro do Chrome DevTools MCP |
| `browser/chrome.yml` | Navegador Chrome, reutilizado pelo componente Chrome DevTools |
| `ai/uv.yml` | Gerenciador uv |
| `ai/cao.yml` | CAO e seu ambiente Python isolado |
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
cao install code_supervisor --provider claude_code
cao launch --agents code_supervisor --provider claude_code --session-name projeto-claude

# Ou Codex
cao install code_supervisor --provider codex
cao launch --agents code_supervisor --provider codex --session-name projeto-codex
```

Informe `--provider` para selecionar Claude ou Codex, pois o padrão do CAO é Kiro.
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

Os arquivos dos clientes são apenas lidos. Para cada cliente, são geradas cópias
dos perfis `code_supervisor`, `developer` e `reviewer` no agent store do CAO, com
os respectivos MCPs e com o MCP interno `cao-mcp-server` preservado:

| Cliente | Supervisor | Workers |
| --- | --- | --- |
| Codex | `ai_stack_codex_code_supervisor` | `ai_stack_codex_developer`, `ai_stack_codex_reviewer` |
| Claude | `ai_stack_claude_code_supervisor` | `ai_stack_claude_developer`, `ai_stack_claude_reviewer` |

Use esses perfis para compartilhar os MCPs, inclusive com os workers. Cada perfil
define seu provedor e orienta o supervisor a delegar para os workers correspondentes:

```bash
# Primeiro, mantenha cao-server em execução.
cd /caminho/do/projeto
cao launch --agents ai_stack_codex_code_supervisor --session-name projeto-codex
# Ou:
cao launch --agents ai_stack_claude_code_supervisor --session-name projeto-claude
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

Inicie uma nova sessão do CAO para carregar as mudanças. Perfis já existentes sem
o prefixo `ai_stack_` são preservados. Os perfis gerados são arquivos `0600` e
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
sudo systemctl status "cao-server-$(id -un)"
sudo journalctl -u "cao-server-$(id -un)" -f
```

O serviço inicia no boot como `ai_stack_user`, escutando em `127.0.0.1:9889`.
O nome da unidade usa esse usuário: `cao-server-ubuntu`, por exemplo.
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
retirá-lo do boot, execute `sudo systemctl disable --now cao-server-ubuntu`.

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
| `cao_version` | `latest` | Versão do pacote PyPI ou `latest` |
| `cao_python_version` | `3.12` | Python usado pelo ambiente do CAO |
| `cao_service_enabled` | `false` | Habilitar o serviço systemd |
| `cao_mcp_sync_enabled` | `true` | Gerar perfis CAO com os MCPs dos clientes |
| `cao_mcp_clients` | `[codex, claude_code]` | Clientes cujos MCPs serão reutilizados |
| `cao_mcp_profiles` | `[code_supervisor, developer, reviewer]` | Perfis base locais ou do pacote CAO |
| `cao_mcp_profile_prefix` | `ai_stack` | Prefixo dos perfis gerados |
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
