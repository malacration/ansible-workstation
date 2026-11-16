# herdr-install — relatório

## Arquivos
Criados:
- /home/andrew/git/ansible-workstation/ai/herdr.yml
- /home/andrew/git/ansible-workstation/ai/roles/herdr/defaults/main.yml
- /home/andrew/git/ansible-workstation/ai/roles/herdr/meta/main.yml
- /home/andrew/git/ansible-workstation/ai/roles/herdr/tasks/main.yml
- /home/andrew/git/ansible-workstation/ai/roles/herdr/tasks/install.yml
- /home/andrew/git/ansible-workstation/ai/roles/herdr/tasks/release.yml
- /home/andrew/git/ansible-workstation/ai/roles/herdr/files/installed_state.py
- /home/andrew/git/ansible-workstation/ai/roles/herdr/templates/herdr.j2
- /home/andrew/git/ansible-workstation/ai/roles/herdr/README.md
- tasks/herdr-install/: SPECIFICATION.md, README_SECTION.md, VARS_SNIPPET.yml, PREFLIGHT_FIX.patch,
  isolated.yml, render-unit.yml, baseline/, proposed/, render/, logs/, ansible-home/ (HOME isolado)

Alterados:
- ai/all.yml — somente o import_playbook herdr.yml (tag herdr, when herdr_enabled|default(true))
- ai/roles/ai_stack/defaults/main.yml — cao_terminal_backend: tmux
- ai/roles/cao/templates/cao-server.service.j2 — ExecStart com `{{ '' if tmux else ' --terminal ' ~ backend }}`
- ai/roles/cao/tasks/service.yml — minhas asserções foram MOVIDAS pelo outro desenvolvedor para
  ai/roles/cao/tasks/service-preflight.yml (arquivo dele); ver "Problema de integração".

## Fontes oficiais
- Repo: https://github.com/herdrdev/herdr (ogulcancelik/herdr redireciona; org, Apache-2.0, homepage herdr.dev)
- Release: https://github.com/herdrdev/herdr/releases/tag/v0.9.5
- Binários: https://github.com/herdrdev/herdr/releases/download/v0.9.5/herdr-linux-{x86_64,aarch64}
- Manifesto SHA256: https://herdr.dev/latest.json (releases.<v>.sha256.linux-<arch>)
- Gerador do manifesto: https://github.com/herdrdev/herdr/blob/v0.9.5/.github/workflows/release.yml (job update-latest-json → distribution/latest.json)
- Instalador oficial (verifica o mesmo manifesto): https://herdr.dev/install.sh
- CLI: https://github.com/herdrdev/herdr/blob/v0.9.5/docs/next/website/src/content/docs/cli-reference.mdx

SHA256 v0.9.5 (manifesto == digest GitHub == repo master distribution/latest.json):
- x86_64  14d9e8bc8b4a9e0118d77c32266f76d461f09b40342eb23752960bd89f59929d
- aarch64 17d7536f2da50859523680ef279dffcac8e4a235f4e46fe8da6c2ec44141897c

## Verificação (logs em tasks/herdr-install/logs/)
- syntax-herdr.log, syntax-all.log, syntax-cao-service.log: rc=0
- list-tasks-herdr.log: rc=0
- isolated-check-empty.log: check em HOME vazio, changed=3 (previsões), rc=0
- isolated-first.log: changed=8; isolated-second.log: changed=0; isolated-check-installed.log: changed=0
- negative-operator-pin.log / negative-audited-pin.log: falham na asserção antes do download (rc=2)
- negative-download-checksum.log: manifesto fixture com SHA errado, sem digest/pin → get_url recusa (rc=2)
- installed-before/after-negative.sha256: payload instalado intacto após falhas
- tamper-check.log / tamper-reconcile.log: binário alterado detectado e restaurado (backup mantido)
- explicit-upgrade-latest.log: latest+upgrade resolve 0.9.5 (changed=3 só staging)
- latest-no-upgrade-offline-path.log: latest sem upgrade não consulta a rede (changed=0)
- isolated-final-idempotence.log: changed=0
- cli-probe.log, cli-probe-subcommands.log: --version/--help dos comandos usados pelo CAO, rc=0
- render-unit-diff.log: tmux byte-idêntico ao baseline; herdr só acrescenta ` --terminal herdr`
- cao-server-help.log: `--terminal {tmux,herdr}` existe no CAO instalado
- resolve-vars.log: cao_terminal_backend=tmux no play do serviço; <undefined> no play de preflight
- preflight-undefined-backend.log: preflight atual falha (cao_terminal_backend undefined) com service habilitado
- preflight-proposed.log: patch proposto: tmux ok, herdr ok, herdr+herdr_enabled=false falha, valor inválido falha
- test-rtk-entrypoint.log: teste existente OK
- real-home-untouched.log: nada criado no HOME real

## Update 1 (coordenação: service.yml pertence ao outro desenvolvedor)
- Validações de cao_terminal_backend movidas para ai/roles/herdr/tasks/backend.yml, executadas pelo
  novo entry point ai/cao-terminal-backend.yml; ai/all.yml o importa depois de herdr.yml e antes de
  cao-service.yml, com tags [cao_service, herdr].
- Template: `{{ ' --terminal herdr' if cao_terminal_backend | default('tmux') == 'herdr' else '' }}`.
  tmux, indefinido e inválido renderizam a unidade atual byte a byte; herdr só acrescenta --terminal herdr.
- service.yml/restart-service.yml não foram editados por mim. A remoção das 3 tarefas duplicadas que estão
  hoje em service.yml está descrita em SERVICE_YML_CHANGE.md, junto com o import opcional em cao-service.yml.
- PREFLIGHT_FIX.patch e proposed/ foram movidos para obsolete/ (substituídos).
- Logs novos: logs/backend-check-entrypoint.log, logs/render-unit-diff.log, logs/syntax-update1.log,
  logs/list-tasks-herdr.log, logs/test-rtk-entrypoint.log.

## REVIEW_3 [B] (logs com sufixo -5)
- B-1: release.yml remove do cache os downloads de outras versões após publicação bem-sucedida.
  install.yml remove os backups Ansible do binário/recibo após a revalidação pós-publicação. Ambos usam
  find: arquivos regulares, regex exata, follow=false, sem recursão. Backups do comando público em
  ai_stack_bin_dir são preservados de propósito.
  Logs: prune-run{1..7}-*-5.log e prune-state-5.log (ASSERT OK em todas as execuções).
- B-2/B-3: documentados em ai/roles/herdr/README.md.
- Pergunta sobre backend.yml: typo herdrr é rejeitado; herdr ausente com serviço habilitado em modo real
  falha. Logs: backend-check-5.log e cao-service-import-typo-5.log. backend.yml não precisou de mudança.
- Outros logs: syntax-5.log, list-tasks-herdr-5.log, real-home-untouched-5.log.
