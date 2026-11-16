<!--
Trechos para mesclar em ai/README.md depois da tarefa concorrente em ai/roles/cao.
1) Linha da tabela "Arquivo | Responsabilidade" (após ai/rtk.yml).
2) Seção "## herdr e backend de terminal do CAO" (após "## RTK OSS shell filtering").
3) Linhas da tabela de variáveis (após cao_restart_on_change).
4) Exemplo de subplaybook na lista de "## Subplaybooks e tags".
-->

### 1) Tabela de arquivos

| `ai/herdr.yml` | herdr, multiplexador do backend experimental de terminal do CAO |
| `ai/cao-terminal-backend.yml` | Validação de `cao_terminal_backend` e do herdr antes do serviço |

### 4) Subplaybooks e tags

```bash
ansible-playbook ai/herdr.yml -K
```

### 2) Seção

## herdr e backend de terminal do CAO

O CAO usa tmux por padrão. Ele também aceita o backend **herdr**, marcado como
**experimental** pelo próprio CAO: um multiplexador em Rust que informa o estado
dos agentes. `ai/all.yml` instala o herdr por padrão, mas o CAO continua usando
tmux até que você escolha herdr explicitamente.

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

### Escolher o backend do cao-server

A escolha vale para cada processo `cao-server`, nesta ordem:
`cao-server --terminal <tmux|herdr>` > variável `CAO_TERMINAL_BACKEND` >
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
configurações do CAO continuam valendo. Com `herdr`, o `ExecStart` recebe
`--terminal herdr`, que prevalece sobre esses valores. Em `ai/all.yml`,
`ai/cao-terminal-backend.yml` roda antes do serviço: valores diferentes de `tmux`
e `herdr` falham antes de qualquer alteração e, com o serviço habilitado,
`herdr` exige o comando instalado (no `--check`, basta `herdr_enabled=true`).
Para validar isoladamente:

```bash
ansible-playbook ai/cao-terminal-backend.yml -e cao_service_enabled=true -e cao_terminal_backend=herdr
```

O playbook não inicia, para ou reinicia serviços por causa dessa troca. Mesmo
com a unidade atualizada, o servidor em execução mantém o backend anterior até
ser reiniciado. Em uma janela de manutenção, sem sessões abertas, reinicie a
unidade definida em `cao_service_name` (padrão `cao-server`), por exemplo
`sudo systemctl restart cao-server`. Com
`cao_restart_on_change=true`, o handler reinicia o serviço ao mudar a unidade e
encerra as sessões abertas; use somente sem sessões em uso. Processos iniciados
pelo serviço, incluindo o servidor herdr, terminam junto com a unidade.

Para voltar ao tmux pelo playbook, use `-e cao_terminal_backend=tmux` (ou remova
o override) e reinicie o serviço da mesma forma.

### 3) Tabela de variáveis

| `herdr_enabled` | `true` | Incluir o herdr em `ai/all.yml` |
| `herdr_version` | `0.9.5` | Pin auditado ou `latest` |
| `herdr_upgrade` | Valor de `ai_stack_upgrade` | Reconsultar e reverificar o release do herdr |
| `herdr_checksum` | vazio | Pin adicional opcional `sha256:HEX` do binário |
| `cao_terminal_backend` | `tmux` | Backend do `cao-server` no serviço systemd: `tmux` ou `herdr` (experimental) |
