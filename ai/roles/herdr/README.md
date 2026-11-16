# herdr (backend experimental de terminal do CAO)

Esta role instala o binário oficial do [herdr](https://github.com/herdrdev/herdr)
para Linux x86_64 ou aarch64, no home de `ai_stack_user`, sem root. O SHA256 é
conferido antes de qualquer execução. A role não inicia servidor herdr, não grava
`~/.config/herdr`, não executa `herdr integration install` e não altera o CAO.
A seleção do backend do `cao-server` fica em `cao_terminal_backend` (role
`ai_stack`) e é aplicada somente pela unidade systemd opcional da role `cao`.

Importe `ai/common.yml` antes, como faz `ai/herdr.yml`. A role usa
`ai_stack_user`, `ai_stack_home`, `ai_stack_bin_dir`, `ai_stack_cache_dir` e
`ai_stack_environment`, e não tem dependências implícitas, permitindo validação
em HOME isolado.

| Variável | Padrão | Comportamento |
| --- | --- | --- |
| `herdr_version` | `'0.9.5'` | Pin auditado, ou `latest` |
| `herdr_upgrade` | `ai_stack_upgrade`, senão `false` | Reconsultar e reverificar o release |
| `herdr_install_dir` | `{{ ai_stack_home }}/.local/share/ai-stack/herdr` | Binário privado e recibo |
| `herdr_binary` | `{{ ai_stack_bin_dir }}/herdr` | Comando público (wrapper `exec`) |
| `herdr_checksum` | vazio | Pin adicional opcional `sha256:HEX` |
| `herdr_audited_checksums` | v0.9.5 x86_64/aarch64 | Pins revisados, conferidos com o manifesto |
| `herdr_release_api` | API de releases de `herdrdev/herdr` | Metadados; altere só para mirror/fixture confiável |
| `herdr_release_download_url` | Download oficial dos releases GitHub | Base dos binários |
| `herdr_manifest_url` | `https://herdr.dev/latest.json` | Manifesto oficial de SHA256 |

`tasks/backend.yml` (via `ai/cao-terminal-backend.yml`) valida
`cao_terminal_backend` em `tmux|herdr` e, com `cao_service_enabled=true` e
`herdr`, exige `herdr_binary` executável (no check mode basta `herdr_enabled`).
É somente leitura; `ai/all.yml` o executa depois de `ai/herdr.yml` e antes do
serviço.

## Cadeia de confiança

O upstream não anexa um arquivo de checksums aos releases. Os SHA256 oficiais
ficam no manifesto `https://herdr.dev/latest.json`, o mesmo usado pelo instalador
oficial (`https://herdr.dev/install.sh`) e por `herdr update`. O workflow
`.github/workflows/release.yml` do upstream gera esse arquivo em
`distribution/latest.json`, com histórico por versão em
`releases.<versão>.sha256.linux-<arch>`. Um pin antigo continua verificável depois
de novos releases.

Antes de baixar, a role exige que todas as fontes presentes concordem:

1. release estável (não draft/prerelease) com o asset `herdr-linux-<arch>`;
2. SHA256 do manifesto oficial para essa versão e arquitetura (obrigatório);
3. `digest` do asset na API do GitHub, quando presente;
4. `herdr_audited_checksums` para a versão, quando houver;
5. `herdr_checksum`, quando informado.

O download (`get_url` com checksum) falha se os bytes divergirem. O candidato é
copiado para um diretório temporário, precisa ser arquivo regular executável sem
symlink, com o mesmo SHA256, e `--version` deve responder `herdr <versão>` antes da
publicação atômica em `bin/herdr`. O recibo `release.json` registra versão,
asset, SHA256, origem e manifesto. Nenhum script remoto é executado.

## Reexecução, atualização e check mode

`installed_state.py` valida recibo e binário sem executar nem seguir symlinks.
Somente um binário cujo SHA256 confere com o recibo recebe `--version`. Recibo
ausente, inválido ou binário alterado força reconciliação para o pin. Destinos
não regulares são renomeados para `ARQUIVO.herdr-invalid-UUID` e preservados.

Ancestrais symlink falham antes de qualquer escrita, inclusive diretórios do
sistema: em hosts onde, por exemplo, `/home` é um link para `/var/home`, os
caminhos derivados de `ai_stack_home` são recusados. Nesse caso, informe o
caminho real (`readlink -f`) em `ai_stack_home` e `ai_stack_bin_dir`, ou em
`herdr_install_dir`, `herdr_binary` e `ai_stack_cache_dir`.

Arquivos regulares sobrescritos recebem backup do Ansible
(`ARQUIVO.PID.AAAA-MM-DD@HH:MM:SS~`). Depois que o release publicado é revalidado,
os backups do binário e do recibo em `herdr_install_dir` são removidos, para que
atualizações e reconciliações não acumulem cópias do binário. Se a revalidação
falhar, eles permanecem. Backups do comando público em `ai_stack_bin_dir` são
preservados, pois podem conter um herdr instalado antes desta role. No cache
(`ai_stack_cache_dir/herdr`), após uma publicação bem-sucedida, fica apenas o
download da versão instalada. São removidos somente arquivos regulares com os
nomes exatos acima, sem seguir symlinks e sem recursão.

Uma versão fixa diferente da instalada é reconciliada na próxima execução.
`latest` mantém a versão instalada sem acesso à rede até `herdr_upgrade=true` ou
`ai_stack_upgrade=true`. Uma atualização explícita pode reportar mudanças nas
tarefas temporárias, mesmo sem release novo.

`herdr update` e `herdr channel set` substituem o binário privado fora do Ansible.
A próxima execução detecta o SHA256 diferente e restaura o pin configurado. Para
mudar de versão, use as variáveis acima.

`--check` inspeciona o estado e prevê a instalação sem consultar a rede ou
executar binários novos.

A API do GitHub é consultada sem autenticação, com limite de 60 requisições por
hora por IP. Ela só é usada quando há instalação, reconciliação ou atualização
explícita (uma requisição de release por execução), então execuções normais não
a consultam. Ao exceder o limite, a tarefa falha sem alterar a instalação;
tente novamente mais tarde.

Arquiteturas sem binário Linux oficial (diferentes de x86_64 e aarch64) são
omitidas com mensagem explícita, sem falha.

## Compatibilidade com o CAO

O CAO instalado (`backends/herdr_backend.py`, `services/herdr_inbox_service.py`)
chama `herdr --session <nome>` com `workspace list|create|close|focus`,
`tab create|rename|list|focus`, `pane list|get|close|send-text|send-keys|run|read|process-info`,
`api snapshot`, `server`, as flags `--cwd --env --format --label --lines --pane
--source --workspace`, e usa o socket `events.subscribe`. Esses comandos existem
na referência de CLI da v0.9.5 e foram conferidos com `--help` no binário
instalado. `constants.py` do CAO documenta o comportamento da v0.9.5
(`pane read` limitado a 1000 linhas), e o serviço de inbox foi ajustado para a
mudança de replay da v0.9.0. Por isso o pin é 0.9.5.

Referências oficiais:

- https://github.com/herdrdev/herdr
- https://github.com/herdrdev/herdr/releases/tag/v0.9.5
- https://herdr.dev/latest.json
- https://herdr.dev/install.sh
- https://github.com/herdrdev/herdr/blob/v0.9.5/.github/workflows/release.yml
- https://github.com/herdrdev/herdr/blob/v0.9.5/docs/next/website/src/content/docs/cli-reference.mdx
- https://github.com/herdrdev/herdr/blob/v0.9.5/docs/next/website/src/content/docs/install.mdx
