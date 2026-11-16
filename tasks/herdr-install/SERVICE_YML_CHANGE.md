# Mudança solicitada em ai/roles/cao/tasks/service.yml (para o dono do arquivo mesclar)

Conforme a Update 1, as validações de `cao_terminal_backend` não ficam mais no
serviço. Elas estão na role herdr (`ai/roles/herdr/tasks/backend.yml`), executadas
por um entry point próprio (`ai/cao-terminal-backend.yml`). `ai/all.yml` importa
esse entry point depois de `ai/herdr.yml` e imediatamente antes de
`ai/cao-service.yml`, com tags `[cao_service, herdr]`.

## 1. Remover de service.yml (obrigatório)

O arquivo atual ainda contém três tarefas copiadas da minha primeira versão,
logo após `import_tasks: service-preflight.yml`. Remova-as inteiras:

- `Validar backend de terminal do CAO`
- `Verificar comando herdr para o backend herdr`
- `Exigir herdr instalado, ou habilitado no check mode, para o backend herdr`

Elas duplicam `backend.yml`. Além disso, a primeira usa `cao_terminal_backend` sem
`default`, o que quebra se a variável deixar de existir nos defaults do cao.
Depois da remoção, `service.yml` não precisa referenciar `cao_terminal_backend`;
o template trata o valor sozinho.

## 2. Opcional: validar também em `ansible-playbook ai/cao-service.yml` avulso

`ai/cao-service.yml` executado sozinho não passa por `ai/all.yml`. Para manter a
validação nesse caminho, acrescente no início de `ai/cao-service.yml`:

```yaml
- name: Validar backend de terminal do CAO
  ansible.builtin.import_playbook: cao-terminal-backend.yml
```

Sem isso, o comportamento ainda é seguro: o template só emite `--terminal herdr`
quando o valor é exatamente `herdr`; qualquer outro valor (inclusive inválido ou
indefinido) gera a unidade tmux atual, byte a byte. Um valor inválido apenas não
seria reportado nesse caminho avulso.

## 3. Definição duplicada de cao_terminal_backend

`cao_terminal_backend: tmux` agora existe em `ai/roles/ai_stack/defaults/main.yml`
(local indicado na especificação) e em `ai/roles/cao/defaults/main.yml` (adicionado
pelo outro desenvolvedor). O valor é o mesmo, então não há conflito. Sugestão:
manter só um. Meu código (template e `backend.yml`) usa `| default('tmux')` e
funciona com qualquer um deles, ou com nenhum.

## Nada mais

O template `cao-server.service.j2` usa somente:

```jinja
ExecStart={{ ai_stack_bin_dir }}/cao-server --host 127.0.0.1 --port 9889{{ ' --terminal herdr' if cao_terminal_backend | default('tmux') == 'herdr' else '' }}
```

Não depende do nome da unidade, de restart-service.yml nem do handler. As
validações de identidade das unidades legadas em service-preflight.yml continuam
corretas: unidades antigas nunca tiveram `--terminal`.
