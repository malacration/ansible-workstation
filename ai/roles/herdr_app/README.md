# herdr_app (layouts e mods do aplicativo Herdr)

Esta role personaliza o aplicativo gráfico Herdr (`~/.config/herdr-app`). Ela não
instala o app nem o herdr-core (`hc`): eles vêm do instalador do próprio Herdr. Se a
pasta ainda não existir, a role só avisa para abrir o app uma vez e rodar de novo.

O que é instalado:

| Fonte | Conteúdo | Patch local (`files/patches/`) |
| --- | --- | --- |
| [franky5440-afk/herdr-traveler](https://github.com/franky5440-afk/herdr-traveler) | layout `traveler`, tema `traveler-dusk`, mods `traveler-*` e `inbox` | `inbox` portado para Linux: `stat -c`, `xdg-open`, `gio trash`, cópia que nunca sobrescreve, Desktop localizado (`xdg-user-dir`) |
| [kevinpardo/world-of-codecraft](https://github.com/kevinpardo/world-of-codecraft) | layout e tema `World-of-Codecraft`, mod `world-of-codecraft`, teclas do layout | botões de janela no Linux, botão de configurações, mana (cota de 5 horas) dos heróis Claude e Codex (`mana.js`) |
| [mukiwu/herdr-crew-rpg](https://github.com/mukiwu/herdr-crew-rpg) | mod `herdr-crew-rpg` (painel Crew) | cota por conta do Claude Code (`claude-statusline.py`, `quota.py --only`), ícone com letra para cada conta extra, painel de cota compacto (uma linha por IA: barra e % das 5 horas, horário do reset ao passar o mouse; IAs só com limite semanal ou mensal não aparecem), modo `quotaOnly` (só as barras, sem a lista do Crew nem a aba com animação), conta via gateway com gasto do mês em US$ e % do orçamento (R$ e data de renovação no tooltip), `hiddenProviders` no `config.json`, Grok só quando instalado |
| Herdr (mods `agents`, `spaces`, `tabs` da sua instalação) | cópias `agents-titles`, `spaces-titles`, `tabs-titles` | nome pelo título que a IA deu à conversa (Claude Code, Codex) quando ninguém nomeou ou quando foi o CAO (labels `cao.session`/`cao.window`); máquina, espaço, aba e git só no tooltip |
| esta role | layout `mala` (o `main` do Herdr 0.1.16 com as cópias `*-titles` e as barras de cota no lugar do Crew) | — |

Cada fonte é baixada de `codeload.github.com` num commit fixo e conferida pelo SHA256
do tar.gz (`herdr_app_sources`) antes de qualquer extração. Nenhum script remoto é
executado e as artes de terceiros não ficam neste repositório.

## Como funciona

`files/herdr_app.py` recebe uma especificação JSON e:

1. confere o SHA256 de cada arquivo no cache (`~/.cache/ai-stack/herdr-app`);
2. extrai só os caminhos listados, recusando links, caminhos absolutos ou com `..`;
3. aplica o patch local com `git apply` numa pasta temporária. Todas as fontes são
   preparadas antes da primeira gravação: um pin ou patch inválido não altera nada;
4. grava no Herdr home somente os arquivos cujo conteúdo mudou (escrita atômica), para
   que o app não recarregue mods sem motivo. Nada é apagado;
5. mescla o que é seu sem sobrescrever:
   - `keys.json`: adiciona as seções/teclas dos layouts; uma tecla que você já usa com
     outra ação é mantida e aparece como aviso;
   - `mods/herdr-crew-rpg/config.json`: só `claudeAccounts` (idioma e Cursor ficam como
     você deixou);
   - `mods/herdr-crew-rpg/config.json`: o orçamento de `herdr_app_claude_budgets`
     (`budgetUsd`, `budgetPeriod`) e as chaves que você acrescentar numa conta são mantidas;
   - `<codex home>/config.toml`: `[tui] terminal_title`, só se ainda não houver um
     (backup como abaixo);
   - `<config_dir>/settings.json` de cada conta do Claude: `statusLine`, só se não houver
     uma ou se já for a deste mod. Uma status line diferente é mantida (e a conta fica sem
     cota). A primeira alteração guarda `settings.json.herdr-app-backup.<sha256>`. Valores
     das configurações nunca são impressos.

`--check` (e `ansible-playbook --check`) só informa o que mudaria. Sem os arquivos
no cache, informa que eles ainda serão baixados.

## Contas do Claude Code

`herdr_app_claude_accounts` vale por padrão `home` (`~/.claude`) mais as contas de
`cao_claude_accounts` (padrão `b` em `~/.claude-b`). Cada conta recebe uma `statusLine`
que roda `claude-statusline.py <conta>` a cada `herdr_app_statusline_refresh` segundos.
O script grava só porcentagens e horários de reset em
`~/.cache/agent-crew/claude-<conta>.json` e marca o próprio terminal com
`hc label <terminal> claude.account=<conta>`. Ele não imprime nada, então a status line
do Claude Code continua vazia.

A conta é decidida pelo `CLAUDE_CONFIG_DIR` do processo, comparado com o `configDir` de
cada conta em `config.json`. O argumento `<conta>` é só o último recurso, porque uma
sessão aberta em `~` também carrega `~/.claude/settings.json` como settings de projeto e
rodaria a status line da conta `home`. Várias sessões da mesma conta gravam no mesmo
arquivo: dentro de uma janela vale o maior uso (uma sessão parada reenvia números
antigos), uma janela com reset mais novo substitui a anterior e uma atualização sem a
janela mantém a que já existia.

## Variáveis

| Variável | Padrão | Comportamento |
| --- | --- | --- |
| `herdr_app_enabled` | `true` | Incluir a role em `ai/all.yml` |
| `herdr_app_home` | `~/.config/herdr-app` | Herdr home do app |
| `herdr_app_cache_dir` | `~/.cache/ai-stack/herdr-app` | Arquivos baixados e área temporária |
| `herdr_app_sources` | as três fontes acima | Repositório, commit, SHA256, caminhos, patch e arquivo de teclas |
| `herdr_app_mala_layout` | `true` | Instalar `layouts/mala.json` e as cópias `*-titles` (quando a fonte `crew` está na lista) |
| `herdr_app_claude_budgets` | `{gw: {usd: 100, period: month}}` | Orçamento mensal (US$) das contas cobradas por token |
| `herdr_app_codex_terminal_title` | `[thread-title]` | Título do terminal do Codex; `[]` não mexe no `config.toml` |
| `herdr_app_claude_accounts` | `home` + `cao_claude_accounts` | Contas com status line de cota |
| `herdr_app_statusline_refresh` | `60` | Intervalo da status line, em segundos |

Remover uma fonte da lista para de gerenciá-la; os arquivos já instalados ficam.
Uma instalação anterior com o layout `main-crew` mantém `layouts/main-crew.json`; apague-o
à mão se não quiser mais (o `mala` o substitui).

## Cópias `*-titles` e atualizações do Herdr

O Herdr reescreve os próprios mods a cada início, por isso as mudanças da barra lateral
e da barra de abas vivem em cópias (`agents-titles`, `spaces-titles`, `tabs-titles`),
feitas a partir do mod da sua instalação mais o patch `files/patches/<cópia>.patch`. Se
uma versão nova do Herdr mudar o mod e o patch deixar de aplicar, a role só avisa e deixa
a cópia instalada como está. Para atualizar, clone de novo (`herdr-app do mod.clone`),
reaplique as mudanças e gere o patch com `git diff --no-index` entre o mod original
copiado para `mods/<cópia>/` e a cópia nova.

## Atualizar uma fonte

1. Escolha o novo commit e calcule o SHA256:
   `curl -fsSL https://codeload.github.com/<repo>/tar.gz/<commit> | sha256sum`.
2. Leia o código novo (README e RECIPE de cada projeto listam o que ele executa).
3. Confira que o patch ainda aplica: extraia o tar.gz e rode
   `git apply --check -p1 files/patches/<fonte>.patch` na raiz extraída.
   Se não aplicar, refaça o patch a partir da instalação atual
   (`git diff --no-index original instalado`).
4. Atualize `commit` e `sha256` em `defaults/main.yml` e rode os testes.

## Testes

```bash
python3 -m unittest ai/tests/test_herdr_app.py
```

Os testes usam um HOME isolado e arquivos falsos (sem rede). Para validar as fontes
reais sem tocar na sua instalação:

```bash
ansible-playbook ai/herdr-app.yml --skip-tags ai_common -e ai_stack_home=/tmp/herdr-home
```

com `/tmp/herdr-home/.config/herdr-app/keys.json` e as pastas `.claude*` criadas antes.
