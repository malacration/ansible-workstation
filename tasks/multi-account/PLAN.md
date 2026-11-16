# PLAN — Multiple accounts per CLI provider in the Ansible AI stack

Status: design only. Nothing outside `tasks/multi-account/` was changed. Implementation starts after the tiered-agent-profiles work is approved (Phase 0 gate).

Inputs:
- `SPECIFICATION.md`, including **Update 1**: no implicit default account in CAO, every profile names its account, plain `claude`/`codex` stay untouched, and another account is selected by **directory**.
- The user decisions in §D below.

The previous revision of this plan is kept at `evidence/PLAN.v1.md`.

Research facts:
- Research date: 2026-11-16.
- Installed versions: Claude Code `2.1.325`, codex-cli `0.169.0`, uv `0.13.8`.
- CAO is pinned at `3e30ea3ed6e7fb607b13358d81123afff5a8e69f` (`ai/roles/cao/defaults/main.yml:9`). That commit is also upstream `main` HEAD today.

Conventions:
- `CAO/` means `~/.local/share/uv/tools/cli-agent-orchestrator/lib/python3.12/site-packages/cli_agent_orchestrator/`.
- Raw CLI help output is in `tasks/multi-account/evidence/`.
- Account names in this document (`pessoal`, `<name>`, `work`) are **examples only**. All account names are free-form variables (§D4).

---

## D. Decisions (2026-11-16)

| # | Decision | Effect on this plan |
|---|---|---|
| D1 | **CAO env support uses the LOCAL PATCH now (Track L).** The patch is shaped exactly like upstream PR #665, so it can be dropped when #665 merges. | §2.3 now describes the patch as a rebase of #665 itself (same `env:` field, schema, validation, tmux injection, `CLAUDE*` unset exemption), not a different design. The earlier "inline command assignment" variant is withdrawn. §2.6 resolves the install risk with read-only evidence: install from a **local git repository with a deterministic patched commit** (`git+file://…@<sha>`), which works with `install_cao.py` unchanged. |
| D2 | **No terminal helper.** `ai-as` is removed. The user uses the native form only: `CLAUDE_CONFIG_DIR=<dir> claude` and `CODEX_HOME=<dir> codex`. | §3 now covers the native form and the README text (§3.2). The sentinel file and the per-account wrappers are removed. The standalone `ai-stack-accounts status` command is **dropped**. Only a read-only login check inside the playbook remains, as a warning (§4.3, with the reason). |
| D3 | **Extra Claude accounts inherit the global instructions.** Ansible creates in each extra account a `CLAUDE.md` that imports the home account's `~/.claude/CLAUDE.md`, so `RTK.md` and the rest still apply. | §4.4 defines the mechanism: an `@` import of the absolute path inside an Ansible-owned block, managed with `blockinfile`, which is idempotent. §4.6 changes RTK for extra Claude accounts to **hooks only**, so `RTK.md` is not loaded twice. |
| D4 | **The account-policy question is dropped.** "rovema" was only an example name; account names are free-form variables. | The policy question in §10 is removed. Examples use placeholders. Nothing in the code or templates may hard-code an account name. The home account's name is also a variable (default `pessoal`). |

---

## 0. Executive summary

| Topic | Decision |
|---|---|
| Account isolation | One binary per CLI. One config directory per account: `CLAUDE_CONFIG_DIR` for Claude Code, `CODEX_HOME` for Codex. Both are documented and verified (§1). |
| Home account | It has a **name**, set by a variable (default `pessoal`), but **no env var**. Setting `CLAUDE_CONFIG_DIR=~/.claude` explicitly would move `.claude.json` from `~/.claude.json` into `~/.claude/` (§1.1). In profiles, "home" therefore means "env var absent". |
| Terminal | Plain `claude`/`codex` are unchanged. For another account the user types `CLAUDE_CONFIG_DIR=<dir> claude` or `CODEX_HOME=<dir> codex`. There is no helper, alias or wrapper (D2). Neither CLI has a config-dir flag (verified). |
| CAO mechanism | A per-profile `env:` field. Now: a local patch that is a rebase of upstream PR #665 (D1). Later: bump the pin when #665 merges and delete the patch. Profiles stay identical across the two (§2). |
| Install of the patched CAO | Local git repo plus a deterministic patched commit, installed as `cli-agent-orchestrator @ git+file://<cache>/cao-src@<sha>`. `install_cao.py` needs no change (verified offline, §2.6). |
| Profile names | `<prefix>_<definition>_<provider>_<account>`. Examples: `mala_developer_high_claude_<name>`, `mala_supervisor_codex_pessoal`. There are no suffix-less profiles. |
| Instructions | Each extra Claude account's `CLAUDE.md` imports `@<home>/.claude/CLAUDE.md` (D3). |
| Failover | Same role/level → next account of the same provider (configured order) → the other provider's accounts → stop and report (§6). |
| Critical guard | Unpatched CAO **silently ignores** an unknown `env:` key at runtime. `sync_mcps.py` must refuse to render non-home profiles unless the installed `AgentProfile` has `env` (§2.5). |

---

## 1. Verified CLI facts

### 1.1 Claude Code — `CLAUDE_CONFIG_DIR`

- Env var reference: *"Override the configuration directory (default: `~/.claude`). All settings, session history, and plugins are stored under this path. … Useful for running multiple accounts side by side: for example, `alias claude-work='CLAUDE_CONFIG_DIR=~/.claude-work claude'`."* — https://code.claude.com/docs/en/env-vars
- Multiple accounts: *"To stay signed in to multiple accounts at once … give each account its own configuration directory. … Each directory has its own settings, session history, and claude.ai login or API key."* — https://code.claude.com/docs/en/authentication#log-in-with-multiple-accounts
  - Caveat from the same page: *"Separate directories don't keep two Claude Console sign-ins without an API key apart."* claude.ai logins are fine.
- Credentials: on Linux they are in `~/.claude/.credentials.json`. *"If you've set the `CLAUDE_CONFIG_DIR` environment variable, Claude Code keeps the `.credentials.json` file under that directory instead."* — https://code.claude.com/docs/en/authentication#credential-management
- `.claude.json`: *"If you set `CLAUDE_CONFIG_DIR`, every `~/.claude` path on this page lives under that directory instead. The same applies to `.claude.json`, which otherwise sits at `~/.claude.json`."* — https://code.claude.com/docs/en/claude-directory
  - **Consequence:** an extra account's MCP/user config is `$CLAUDE_CONFIG_DIR/.claude.json`. For the home account the variable must stay **unset**.
- User instructions: the user-level `CLAUDE.md` is `~/.claude/CLAUDE.md` (https://code.claude.com/docs/en/memory). By the rule quoted above it moves to `$CLAUDE_CONFIG_DIR/CLAUDE.md` for an extra account. This is why D3 is needed.
- A new directory triggers first-run onboarding and login (authentication page). Each account needs **one manual interactive run** before CAO can use it.
- No config-dir CLI flag. `claude --help` (evidence/claude-help.txt) only has `--settings`, `--setting-sources`, `--mcp-config`, `--strict-mcp-config`, `--plugin-dir` and `--add-dir`.

### 1.2 Codex — `CODEX_HOME`

- *"Codex stores its local state under `CODEX_HOME` (defaults to `~/.codex`)."* That covers `config.toml`, `auth.json` *"or your OS keychain/keyring"*, `history.jsonl`, logs and caches. — https://learn.chatgpt.com/docs/config-file/config-advanced (the redirect target of https://developers.openai.com/codex/config-advanced)
- `log_dir` defaults to `$CODEX_HOME/log`. Profile files are `$CODEX_HOME/<name>.config.toml`. `cli_auth_credentials_store = file | keyring | auto | ephemeral`. — https://learn.chatgpt.com/docs/config-file/config-reference
- **Keyring isolation (verified in source).** The keyring account key is `cli|<first 16 hex of sha256(canonical CODEX_HOME)>`, under the service `"Codex Auth"` (`compute_store_key`). — https://raw.githubusercontent.com/openai/codex/main/codex-rs/login/src/auth/storage.rs
  - Caveat: `SecretsKeyringAuthStorage` uses a fixed name, `CODEX_AUTH`. When Codex selects that backend is **unverified**.
  - Mitigation: pin `cli_auth_credentials_store = "file"` for non-home accounts (§4.5).
- No config-dir CLI flag. `codex --help` (evidence/codex-help.txt) has:
  - `-c key=value`;
  - `-p/--profile`, which *"Layer $CODEX_HOME/<name>.config.toml on top of the base user config"* (lines 85-86). It layers config only, never auth;
  - `-C/--cd`, which sets the working directory.
- Login status without reading files: `codex login status` (evidence/codex-login-status-help.txt) and `claude auth status [--json|--text]` (evidence/claude-auth-status-help.txt). Their outputs were **not** captured: no login state was read.

---

## 2. CAO: how a profile selects an account

### 2.1 Why the current pin cannot do it (evidence)

1. **Binaries are hard-coded.**
   - `CAO/providers/claude_code.py:714,717,719` (`["claude", …]`) and `CAO/providers/codex.py:1740,1773` (`["codex", …]`).
   - The launch string is typed into the pane shell with `send_keys` (`codex.py:2353-2356`).
2. **Claude's launch unsets `CLAUDE*`.** `claude_code.py:873-880` builds `unset $(env | sed -n 's/^\(CLAUDE[A-Z_]*\)=.*/\1/p' | grep -v …); claude …`.
3. **The pane env filters these variables.**
   - `_BLOCKED_ENV_PREFIXES = ("CLAUDE", "CODEX_", "__MISE_")` at `CAO/clients/tmux.py:1335`.
   - The filter applies to the forwarded server env (`tmux.py:1409-1430`) and to `cao launch --env` (`tmux.py:1384-1406`; `CAO/cli/commands/launch.py:209`).
4. **No `env` field.**
   - `AgentProfile` (`CAO/models/agent_profile.py:328-467`) has none, and upstream `main` has none either.
   - `claudeConfig` maps only `effort` and `fallback_model` (`claude_code.py:774-787`).
   - Every `codexConfig` key becomes a `-c` override (`codex.py:1983`).
5. **The unknown key is silently ignored.**
   - `AgentProfile` does not set `extra="forbid"`. The only `model_config` in the file is on `ProfileParamDecl` (`agent_profile.py:313`).
   - Verified locally: `AgentProfile(name='x', description='d', env={...})` loads and drops `env`.
   - The schema rejects it (`CAO/schemas/agent_profile.schema.json:277`, `additionalProperties: false`), but only the validator uses the schema (`CAO/services/profile_validator.py:119`).

### 2.2 Options evaluated (unchanged from v1)

| Option | Verdict | Key evidence |
|---|---|---|
| **(a) Per-profile `env:` field** | **Chosen** (D1) | Upstream issue #661 and PR #665: open, `mergeable_state: dirty`, 14 commits, 21 files, +1274/−50. The maintainer haofeif **APPROVED** on 2026-10-22; the PR still needs a rebase. https://github.com/awslabs/cli-agent-orchestrator/pull/665 |
| (b) One cao-server per account | Rejected | `CLAUDE*`/`CODEX_*` are stripped from the forwarded env (`tmux.py:1335,1409-1430`). Only a different HOME would reach the pane (`tmux.py:1352`), and that breaks everything else. Separate `CAO_HOME_DIR` (`constants.py:145`) means split databases, stores and memory. Cross-node `target_host` needs `CAO_ADVERTISED_URL` (`constants.py:514`). |
| (c) PATH wrapper named `claude`/`codex` | Rejected | It cannot tell which profile launched it (`terminal_service.py:3192,3221`), and it would violate Update 1. |
| (d) `codexProfile` / `hermesProfile` / Kiro home | Not applicable | `codexProfile` layers config only, and its file lives inside `CODEX_HOME`. `hermesProfile` is Hermes-only (`CAO/providers/hermes.py:162`). The Kiro per-launch home (`terminal_service.py:1896-1907`) is a precedent only. |

### 2.3 Track L: the local patch, shaped exactly like PR #665 (D1)

**Profile contract** (identical under Track L and after #665 merges):

```yaml
env:
  CLAUDE_CONFIG_DIR: /home/<user>/.claude-<name>   # claude_code, non-home accounts only
# or
env:
  CODEX_HOME: /home/<user>/.codex-<name>           # codex, non-home accounts only
```

- Home-account profiles carry **no** `env`.
- Values are absolute paths. #665 passes values verbatim, with no `~` expansion.

**What the patch is.** It is the content of PR #665 at its reviewed head (`62a4bf6ec944c93454cd541a14f4c681d5bd21c0`, branch `feature/profile-env` on the contributor's fork), rebased onto `cao_git_ref`. It is not a re-implementation. The patch therefore carries #665's behaviour as described in the PR body and reviews:

- An optional `env:` mapping on `AgentProfile`, declared in `agent_profile.schema.json` with a `propertyNames` pattern.
- Validation: POSIX names and a per-value byte cap. Runtime-owned keys (`CAO_TERMINAL_ID`, `CAO_SESSION_NAME`, `CAO_WORKFLOW_*`, `CAO_CALLBACK_URL`) are dropped with a warning.
- Injection order in `utils/terminal_env.py`: operator `--env` → profile `env` (`merge_profile_env`) → runtime identity (`apply_runtime_identity`, last).
- Profile env bypasses the forwarded-env prefix blocklist, because profiles are trusted installed configuration.
- tmux:
  - a new session restores the session env after creation, and the session is killed if the restore fails (this fixes haofeif's "leaks session-wide" finding);
  - a new window or pane gets a scoped `-e`.
- The `claude_code` nested-session `unset` spares the `CLAUDE*` names the agent's own profile declares.
- The herdr backend changes come along unchanged.

**Producing the patch** (a Phase 2 development step in a scratch clone, never in the user's repo):

1. Fetch `refs/pull/665/head` and check that the head matches `62a4bf6e…`. If it moved, review the delta first.
2. Rebase onto `cao_git_ref`. gutosantos82's review mentions a conflict with #823.
3. Run #665's own tests and the CAO suite for the touched modules.
4. `git format-patch` → `ai/roles/cao/files/patches/0001-pr665-profile-env.patch`, with a header that records the upstream PR number, the PR head SHA and the base SHA.
5. If the rebase needs non-trivial conflict resolution that changes behaviour, **stop and report**. Do not diverge from #665 silently.

**Codex under #665.** Pane env is inherited by the `codex` process. The PR body does not mention Codex, so this is **unverified** until the Phase 2 test.

**Seeding that stays outside the patch.** `claude_code.py:899` writes `skipDangerousModePermissionPrompt` only to `~/.claude/settings.json`. #665 does not change that, so Ansible seeds the key per account (§4.5).

**Dropping the patch.** `cao_patches` lists each patch with `{file, upstream_pr, pr_head}`. During install:

- `git apply --check` fails → the task fails with "patch no longer applies; check whether PR #665 merged".
- `git apply --reverse --check` succeeds → the change is already upstream. The patch is skipped with a warning to remove it from `cao_patches`.
- When #665 merges: set `cao_git_ref` to a commit that contains it, set `cao_patches: []` and `cao_source: git`, then re-run the Phase 2 tests. Profiles need no change.

### 2.4 Other hard-coded home paths in CAO

| Location | Behaviour | Handling |
|---|---|---|
| `claude_code.py:899` (called at `:1209`) | Writes `skipDangerousModePermissionPrompt` only to `~/.claude/settings.json` | Ansible seeds it per account (§4.5) |
| Trust dialogs (`claude_code.py:187,965-967`; `codex.py:250-259`) | Dismissed in the TUI | Nothing needed |
| `--mcp-config <tmp> --strict-mcp-config` (`claude_code.py:839-841`) | Inside CAO the profile is the only MCP source | Simplifies §5 |
| Codex `-c mcp_servers.*` (`codex.py:1907-1946`) | Layered over `$CODEX_HOME/config.toml`. HTTP MCPs are inherited from the account (`ai/roles/cao/files/sync_mcps.py:138-150`, a file the in-flight work is currently editing) | Each Codex account must carry the HTTP MCP entries (§5) |

### 2.5 Mandatory guards (in `sync_mcps.py`)

- Render `env` only when `'env' in AgentProfile.model_fields` **and** the packaged schema's `properties` contains `env`. Otherwise fail with: "installed CAO lacks per-profile env; account profiles would silently run on the home account". This protects against `cao_source` being switched back to unpatched `git`.
- Allow-list the `env` keys: `CLAUDE_CONFIG_DIR` for `claude_code`, `CODEX_HOME` for `codex`. #665 notes that `GET /agents/profiles/{name}` returns `env` to read-scope callers, so secrets must never go there.

### 2.6 Installing the patched CAO — risk resolved (read-only verification)

What was checked. No install was run.

1. **`install_cao.py` rejects a plain local directory.**
   - `requirement_text` only knows `name, extras, specifier, url, git, path, marker` (`ai/roles/cao/files/install_cao.py:62-65`).
   - uv records a local directory in the receipt as `directory = "<abs path>"`. Evidence: `RequirementSourceWire::Directory { directory }` in https://raw.githubusercontent.com/astral-sh/uv/main/crates/uv-distribution-types/src/requirement.rs. A non-editable `RequirementSource::Directory` maps to the `directory` variant.
   - Offline test with the CAO venv's Python: `requirement_text({'name': 'cli-agent-orchestrator', 'directory': '/x'})` raises `Unsupported uv receipt fields: ['directory']`.
   - Consequence: a `file://<dir>` install would succeed **once**, and every later playbook run would fail while reading the receipt.
2. **`install_cao.py` accepts a local git repository unchanged.**
   - The receipt shape `git = "file:///…/cao-src?rev=<sha>"` renders as `cli-agent-orchestrator @ git+file:///…/cao-src@<sha>`.
   - Offline test: `normalized_requirement` of that string equals the normalized install spec → `True`. So the "receipt matches → no reinstall" idempotence path (`install_cao.py`, the `requested == installed` check) works as-is.
3. **uv supports `git+file://`.** The uv 0.6.3 changelog says Git `file:` URLs are kept supported (https://github.com/astral-sh/uv/pull/11514). Absolute file URLs are required.
   - **Still unverified:** the exact receipt string uv 0.13.8 writes for `git+file://`. Phase 2 checks it with an isolated `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` before anything touches the real tool directory.

**Mechanism (recommended):** a local git repository with a **deterministic** patched commit.

1. The `cao` role keeps a working clone at `{{ ai_stack_cache_dir }}/cao-src` (mode `0700`):
   - fetch `cao_git_url`;
   - `git checkout --detach {{ cao_git_ref }}`;
   - assert `git rev-parse HEAD == cao_git_ref`.
2. For each entry in `cao_patches`, run the §2.3 forward/reverse `--check` logic, then `git apply` (index-only, then commit).
3. Commit with fixed metadata so the SHA depends only on base + patches:
   - `GIT_AUTHOR_NAME`/`GIT_COMMITTER_NAME=ai-stack`;
   - `GIT_AUTHOR_EMAIL`/`GIT_COMMITTER_EMAIL=ai-stack@localhost`;
   - `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` = the base commit's committer date;
   - message: `ai-stack: apply <patch names>`.
   Then tag it `ai-stack/patched-<base12>-<patchset12>`.
4. `cao_install_spec` for `cao_source: git_patched` is `cli-agent-orchestrator @ git+file://{{ ai_stack_cache_dir }}/cao-src@<patched sha>`.
5. `install_cao.py` runs unchanged.
   - Same base and patches → same SHA → the receipt matches → no reinstall.
   - A changed patch or base → a new SHA → reinstall.
   - The installed tool does not depend on the clone afterwards. If the cache is deleted, the next run re-creates the identical SHA (network fetch required).
6. Role assertions grow `cao_source in ['pypi', 'git', 'git_patched']`. `git_patched` requires a non-empty `cao_patches`, and each patch file must exist in the role.

**Alternatives considered:**

| Alternative | Verdict |
|---|---|
| (B) Plain local directory, extending `install_cao.py` to accept `directory` (as with `path`) | Works, but needs a code change and a content-addressed directory name, because uv does not detect content changes in a same-path directory. Fallback if (A) fails in Phase 2. |
| (C) A personal fork hosting the rebased #665 branch | No local machinery, but outward-facing and an extra repository to maintain. Not chosen. |
| (D) Patching `site-packages` after install, with a receipt check | Rejected. Any `uv tool install`/`upgrade` silently reverts it, the receipt cannot express it, and there is no integrity anchor. |

---

## 3. Terminal usage (Update 1 item 2, D2)

### 3.1 Rule

- Plain `claude` and `codex` stay exactly as today: home account, normal prompt.
- Ansible installs **no** helper, alias, shell function or wrapper, and does not edit shell rc files.
- Another account is chosen with the native environment variable, passing that account's **directory**:

```sh
CLAUDE_CONFIG_DIR=<dir> claude [args…]
CODEX_HOME=<dir> codex [args…]
```

- Both CLIs lack a config-dir flag (§1.1, §1.2). The env var is the only native mechanism.
- Ansible's only shell-visible artefact is the account directories it creates (§4.2).

### 3.2 README section (draft, Portuguese, for `ai/README.md` in Phase 1)

> ### Várias contas por CLI
>
> Cada conta tem o próprio diretório de configuração. A conta da home (`~/.claude`, `~/.codex`) continua sendo usada pelos comandos normais:
>
> ```sh
> claude          # conta da home
> codex           # conta da home
> ```
>
> Para usar outra conta, passe o diretório dela na variável nativa da CLI:
>
> ```sh
> CLAUDE_CONFIG_DIR=~/.claude-<nome> claude
> CODEX_HOME=~/.codex-<nome> codex
> ```
>
> Primeiro login de uma conta nova (uma vez, manual; o Ansible nunca faz login nem lê credenciais):
>
> ```sh
> CLAUDE_CONFIG_DIR=~/.claude-<nome> claude          # onboarding + /login
> CODEX_HOME=~/.codex-<nome> codex login
> ```
>
> Conferir o login:
>
> ```sh
> CLAUDE_CONFIG_DIR=~/.claude-<nome> claude auth status --text
> CODEX_HOME=~/.codex-<nome> codex login status
> ```
>
> Cuidados:
> - Nunca use `CLAUDE_CONFIG_DIR=~/.claude` para a conta da home: o Claude passaria a procurar o `.claude.json` dentro de `~/.claude/`. Para a conta da home, rode `claude` sem a variável.
> - Um caminho digitado errado no `CLAUDE_CONFIG_DIR` cria uma configuração nova e vazia e abre o onboarding. Confira o diretório.
> - Os diretórios das contas são criados pelo Ansible (`0700`), conforme `ai_accounts` em `vars.yml`.

### 3.3 Login check (replaces `ai-stack-accounts status`)

The standalone command is **dropped**. It only wrapped two native one-liners (§3.2), and D2 rules out helper scripts.

What remains is a **read-only task in the playbook**, for one reason: a CAO profile for an account that is not logged in, or never onboarded, makes the worker pane hang at startup. Warning at provisioning time is cheaper than discovering it during failover.

- For each account it runs `claude auth status` or `codex login status` with `environment` set to that account's env (§4.1). Both are CLI calls; Ansible opens no credential file.
- Settings: `no_log: true`, `changed_when: false`, `failed_when: false`, and `check_mode: false` (it is read-only).
- It emits only `debug`/`warn` lines of the form `<provider>/<name>: logged in = yes|no`. It never fails the play.
- The logged-in decision uses the exit code, plus one boolean from `claude auth status --json`. That field's name is **unverified** and confirmed in Phase 1. If no reliable boolean exists, the exit code alone is used.

---

## 4. Ansible design

### 4.1 Variables (`ai/vars.example.yml`)

```yaml
# Names are free-form (lowercase letters/digits). List order = failover
# priority inside each provider. At most one `home: true` per provider: it
# uses ~/.claude (+ ~/.claude.json) or ~/.codex and gets NO env var.
ai_accounts:
  claude:
    - {name: pessoal, home: true}
    - {name: work}                         # dir defaults to ~/.claude-work
  codex:
    - {name: pessoal, home: true}
    - {name: work, dir: "{{ ai_stack_home }}/.codex-work"}
# Optional per account: cao: false   (directory managed, no CAO profiles)
```

- **Default when unset:** `{claude: [{name: "{{ ai_accounts_home_name }}", home: true}], codex: [same]}`, with `ai_accounts_home_name: pessoal`. This keeps today's behaviour under an explicit, overridable name.
- No account name is hard-coded in any role, template or script (D4).

**Assertions** in a new `ai_accounts` role, each with a clear `fail_msg`:

- keys are only `claude` and `codex`;
- each list is non-empty;
- names match `^[a-z][a-z0-9]{0,15}$` (no `_`, which is the profile-name separator);
- names are unique per provider;
- at most one `home: true` per provider;
- a non-home `dir` is absolute and under `ai_stack_home` (RTK `safe_path` requires this, `ai/roles/rtk/files/configure_rtk.py:26-36`);
- a non-home `dir` is not `~/.claude`/`~/.codex` and is not shared between accounts;
- the longest generated profile name is ≤ 64 characters.

**Derived fact** for all roles (paths absolute in reality):

```yaml
ai_accounts_resolved:
  claude_code:
    - {name: pessoal, home: true,  dir: ~/.claude,       mcp_config: ~/.claude.json,               instructions: ~/.claude/CLAUDE.md,       env: {}}
    - {name: work,    home: false, dir: ~/.claude-work,  mcp_config: ~/.claude-work/.claude.json,  instructions: ~/.claude-work/CLAUDE.md,  env: {CLAUDE_CONFIG_DIR: /abs/.claude-work}}
  codex:
    - {name: pessoal, home: true,  dir: ~/.codex,        mcp_config: ~/.codex/config.toml,         env: {}}
    - {name: work,    home: false, dir: ~/.codex-work,   mcp_config: ~/.codex-work/config.toml,    env: {CODEX_HOME: /abs/.codex-work}}
```

### 4.2 Directories and permissions

- Non-home accounts only: `file: state=directory mode=0700`, run as `ai_stack_user` (the `become_user` pattern of `ai/roles/claude/tasks/main.yml:3-5`).
- A symlinked directory is refused (`stat` with `follow: false`).
- The modes of existing files inside the directory are never changed. `~/.claude` and `~/.codex` are never touched.
- `~/.local/share/ai-stack/accounts.json` (`0600`) holds names, providers, dirs and order only. It is the input for `sync_mcps.py`. *(The v1 sentinel file `.ai-stack-account` is removed with `ai-as`.)*
- Ansible never creates, reads, copies or templates `.credentials.json`, `auth.json` or keyring entries.

### 4.3 Authentication

- Manual only, using the commands in §3.2.
- The playbook does the read-only check in §3.3.

### 4.4 Inherited Claude instructions (D3)

Each **extra** Claude account gets `$CLAUDE_CONFIG_DIR/CLAUDE.md` (its user-level instructions file, §1.1) with an Ansible-owned block:

```markdown
<!-- BEGIN ANSIBLE AI-ACCOUNTS -->
@/home/<user>/.claude/CLAUDE.md
<!-- END ANSIBLE AI-ACCOUNTS -->
```

**Why an `@` import and not a copy.** Claude Code's memory docs (https://code.claude.com/docs/en/memory#import-additional-files) state:

- *"CLAUDE.md files can import additional files using `@path/to/import` syntax."*
- *"Both relative and absolute paths are allowed. Relative paths resolve relative to the file containing the import"*
- *"maximum depth of four hops"*
- user-scope memory files such as `~/.claude/CLAUDE.md` load their imports *"without the dialog"*;
- *"Import parsing skips Markdown code spans and fenced code blocks"*, so the import must be a bare line, as above.

Comparison:

| | Import (chosen) | Copy |
|---|---|---|
| Freshness | Always the live home file. Edits apply on the next session without re-running Ansible | Drifts until the next playbook run |
| Nested imports | The home file's own `@RTK.md` resolves relative to the home file → `~/.claude/RTK.md`. RTK still applies | A copied `@RTK.md` would resolve to `$CLAUDE_CONFIG_DIR/RTK.md`, a different file that would need its own copy |
| Reads by Ansible | None (writes a path only) | Must read the user's file |
| Symlink alternative | — | A symlinked `CLAUDE.md` is skipped in Cowork sessions (memory docs), and the RTK merger refuses symlinks |

- An **absolute** path is used instead of `@~/…`. It is unambiguous, rendered from `ai_stack_home`, and independent of how `~` is expanded.
- Depth budget: account `CLAUDE.md` → home `CLAUDE.md` (hop 1) → `RTK.md` (hop 2). Two hops remain for the user's own nested imports.

**Implementation and idempotence:**

- `ansible.builtin.blockinfile` with:
  - `path: <account>/CLAUDE.md`;
  - `block: "@{{ ai_stack_home }}/.claude/CLAUDE.md"`;
  - `marker: "<!-- {mark} ANSIBLE AI-ACCOUNTS -->"`;
  - `insertbefore: BOF`, `create: true`, `mode: '0600'`;
  - run as the user.
- Text outside the markers is preserved byte for byte. The user can add account-specific instructions below the block, and they load after the inherited ones.
- A second run is `changed=0`. Check mode reports the diff. Removing an account from `ai_accounts` does **not** delete its directory or files.
- Preconditions:
  - refuse if `<account>/CLAUDE.md` is a symlink (`stat`, `follow: false`);
  - if `~/.claude/CLAUDE.md` does not exist, still write the block and emit a warning. Ansible never creates the home file. What Claude Code does with a missing import is **unverified** (Phase 4 test).
- Codex is not covered by D3. `AGENTS.md` has no import syntax. Extra Codex accounts get only the RTK block in `$CODEX_HOME/AGENTS.md` (§4.6). Sharing the home `~/.codex/AGENTS.md` would need a copy and is out of scope unless requested.

### 4.5 Other per-account seeding (no credentials)

| File | What | Role |
|---|---|---|
| `$CLAUDE_CONFIG_DIR/settings.json` | JSON merge of `skipDangerousModePermissionPrompt: true` (§2.4). Other keys are preserved, symlinks are refused, and the write is atomic with mode `0600` | `cao` (follow-up) |
| `$CODEX_HOME/config.toml` | Top-level `cli_auth_credentials_store = "file"` (§1.2), merged with TOML awareness; nothing else changes | `codex` |

### 4.6 RTK

- `configure_rtk.py` takes `--claude-dir`/`--codex-dir` (`ai/roles/rtk/files/configure_rtk.py:131-141,227-228`). Both are `required=True` today. It will be extended to run once per account.
- Home account: unchanged. Hooks go in `settings.json`/`hooks.json`, and the instruction block plus `RTK.md` go in `CLAUDE.md`/`AGENTS.md`.
- **Extra Claude accounts: hooks only.** The new `--claude-instructions none` option means only `settings.json` hooks are merged. `RTK.md` arrives through the §4.4 import. Writing a second RTK block would load `RTK.md` twice.
- **Extra Codex accounts:** hooks in `hooks.json` plus the RTK block in `$CODEX_HOME/AGENTS.md`, because there is no import mechanism.

### 4.7 MCP installers (`chrome_devtools`, `playwright_mcp`)

- Loop over `ai_accounts_resolved[client]` with `environment: "{{ ai_stack_environment | combine(account.env) }}"`:
  - Claude: `claude mcp add --scope user` writes to that account's `.claude.json`;
  - Codex: `codex mcp add` writes to that account's `config.toml`.
- Replace the inline Python read of `~/.claude.json` (`ai/roles/chrome_devtools/tasks/claude.yml:2-20`) with `claude mcp get <name>` under the account env. Idempotence: `changed_when` only on add/remove.

---

## 5. MCP sync (`sync_mcps.py`, follow-up to the tiered-profiles work)

Decision: **one shared MCP set per provider, imported from the home account.** Every account's profiles get the same set.

- Claude in CAO uses `--strict-mcp-config` (`claude_code.py:839-841`).
- Identical toolsets keep failover transparent.

Codex HTTP MCPs are inherited from each account's `config.toml` (`sync_mcps.py:138-150`). For every Codex account, `sync_mcps.py` checks that each home-account HTTP MCP exists there with the same `url`. Otherwise it fails with the account name and the native command to run: `CODEX_HOME=<dir> codex mcp add …`. OAuth-backed HTTP MCPs need a manual `CODEX_HOME=<dir> codex mcp login <server>` per account.

Changes, on top of the merged tiered-profiles code:

1. `--accounts-file` (the JSON from §4.2). Its absence is equivalent to the default single home account per provider.
2. Name: `<prefix>_<definition>_<client_label>_<account>`, keeping the 64-character check.
3. Rendering:
   - `env` per §2.3, guarded by §2.5, absent for home accounts;
   - an `account-<name>` tag;
   - ` (account <name>)` appended to the description;
   - existing model/effort/config-block logic unchanged.
4. Routes section from the full matrix (§6.2).
5. Prune:
   - marker-only, no symlinks;
   - candidates are the pre-account names `<prefix>_*_<label>.md` and any `<prefix>_*_<label>_*.md` not in the current set (for example, a removed account);
   - returns `removed`.
6. `--check` remains a full dry run.
7. `accounts.json` parsing rejects unknown keys.

Profile count = `definitions × Σ accounts(cao ≠ false)`: 1+1 accounts → 12 profiles, 2+2 → 24, 3+3 → 36.

---

## 6. Supervisor routing and failover

### 6.1 Policy (extends CHANGES_2 A2; English, in the supervisor template)

Unchanged:
- task classification and `[level:]`/`[nivel:]`;
- provider preference (development → Claude, review → Codex);
- `[provider:]`/`[provedor:]`.

New:
- **Account order:** within a provider, the order of `ai_accounts`, as stated in the routes section.
- **Override:** `[account: <name>]` / `[conta: <name>]`. If combined with `[provider:]`, it must match an existing profile, or the supervisor asks.
- **Usage-limit failover** (CHANGES_2 signals). For worker W on provider P, account A:
  1. Confirm W is not still working.
  2. `delete_terminal(W)`.
  3. Mark `(P, A)` exhausted in the task file's "Account ledger", with the reset time if shown.
  4. Re-assign the same task file to the same role/level on the next non-exhausted account of P.
  5. Then try the other provider's accounts, in order.
  6. If all are exhausted, stop and report the reset times. Never loop.
  7. Never reuse an exhausted account before its reset time, unless the user says so.
- **Limitation:** the supervisor cannot fail over its own account. The README tells the user to relaunch it with another `mala_supervisor_<provider>_<name>`.

### 6.2 Generated routes section

```
## AI stack: accounts, providers and delegation
This profile runs on `claude_code`, account `<name>`.
Account failover order — claude: <a1> → <a2>; codex: <b1> → <b2>.

| definition | claude/<a1> | claude/<a2> | codex/<b1> | codex/<b2> |
|---|---|---|---|---|
| developer_low | `mala_developer_low_claude_<a1>` | … | … | … |
| … (all definitions) |
```

---

## 7. Interaction with the in-flight tiered-profiles work

- These files are **not edited** until that work is approved: `ai/roles/cao/files/sync_mcps.py`, `ai/roles/cao/templates/profiles/*`, `ai/roles/cao/defaults/main.yml`, `ai/README.md`, `ai/vars.example.yml` and `ai/tests/test_sync_mcps.py` (`tasks/tiered-agent-profiles/SPECIFICATION.md`, `CHANGES_2.md`).
- `ai/roles/cao/files/install_cao.py` needs **no** change under §2.6 (A).
- After the gate, this plan reuses that work's prefix/label naming, `--base-dir`, prune and markers, profile definitions, efforts/models, and the routing text.
- Migration: `mala_<def>_<label>` becomes `mala_<def>_<label>_<home name>`. The old files are pruned (§5), and running sessions must be relaunched.

---

## 8. Security

- No credentials in the repo, in `accounts.json`, in profiles (§2.5 allow-list) or in Ansible output.
  - The login check uses `no_log` and booleans only.
  - No task reads `.credentials.json`, `auth.json`, keyrings or `.env`.
- Account directories are `0700`. `accounts.json` and the managed `CLAUDE.md`/settings files are `0600`. Every write refuses symlinks.
- Profile `env` contains directory paths only. #665 notes it is visible to read-scope API callers.
- The patched CAO is built from a verified base SHA (`rev-parse` assertion) plus repo-tracked patches. The resulting SHA is deterministic and auditable.
- **Server-managed settings risk.** A Team/Enterprise login can bring server-managed settings, cached per account in `<dir>/remote-settings.json` (https://code.claude.com/docs/en/claude-directory). Those settings could block CAO's `--dangerously-skip-permissions` launch. Phase 2 smoke-tests every configured account.
- Transcripts and auto-memory are per config directory. CAO memory (`~/.aws/cli-agent-orchestrator`) stays shared.

---

## 9. Phased implementation and verification

Rules for every phase:
- No run against the real home before user approval.
- Isolated HOME under `tasks/multi-account/isolated-home/`.
- Logs under `tasks/multi-account/`.
- Unit tests: `"$(uv tool dir)/cli-agent-orchestrator/bin/python" -m unittest discover -s ai/tests -v`.
- Syntax checks: `ansible-playbook ai/all.yml --syntax-check` plus each playbook.

| Phase | Scope | Verification |
|---|---|---|
| **0. Gate** | Tiered-profiles work (CHANGES_2) approved. Record a baseline | Existing tests and syntax checks green; log saved |
| **1. Accounts model** | `ai_accounts` role: vars, assertions, `ai_accounts_resolved`, directories, `accounts.json`, the read-only login check (§3.3). README section §3.2. **No helper, no wrappers, no rc edits** | • Bad-vars test playbooks fail with the expected `fail_msg`.<br>• Idempotence (`changed=0` on the second run) and check mode against the isolated HOME.<br>• `type claude`/`type codex` unchanged before and after (still the real binaries, no alias or function), and no new files under `~/.local/bin` except those the existing roles already install.<br>• The login check prints only booleans and the playbook log contains no account email (grep).<br>• Confirm the `claude auth status --json` boolean field and Codex behaviour with a missing `CODEX_HOME`, against throwaway empty directories |
| **2. CAO per-profile env (Track L)** | Produce `0001-pr665-profile-env.patch` (§2.3). Add `cao_source: git_patched`, `cao_patches`, the deterministic local commit and the install spec (§2.6) | • Patch generation: rebase is clean; #665's tests and CAO's `test_claude_code*`, `test_codex*`, `test_agent_profile*` and terminal-env tests pass in the scratch clone.<br>• Determinism: building the patched commit twice from scratch gives the same SHA.<br>• Install, with isolated `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` only: record the receipt's `git = "file://…?rev=…"` string; `install_cao.py` reports `changed: true`, then `false` on the second run.<br>• Forward/reverse `--check` logic: a stale patch fails; an "already upstream" patch is skipped.<br>• Behaviour with isolated `CAO_HOME_DIR` and `TMUX_TMPDIR`, using stub `claude`/`codex` executables in the **test** PATH only that dump their env: a non-home profile sees its directory variable; a home profile has it absent; a second window in the same session does not inherit it.<br>• Manual smoke test (user-approved): one worker per configured non-home account runs `echo "$CLAUDE_CONFIG_DIR"` / `echo "$CODEX_HOME"`; the login shown matches the account. This also exposes server-managed settings that block bypass |
| **3. sync_mcps accounts** | `--accounts-file`, names, `env`, guard §2.5, prune, routes, Codex HTTP-per-account check | Unit tests per item: the guard fails on unpatched CAO; no `env` for home; the allow-list; 64-character limit; invalid names; marker-only prune. Render the full matrix into an isolated HOME and validate each profile with the patched `load_agent_profile` and `cao profile validate` |
| **4. Installers, RTK, instructions, seeding** | MCP roles per account; `configure_rtk.py` per account with `--claude-instructions none` for extra Claude accounts; the §4.4 `CLAUDE.md` block; §4.5 seeding | Isolated HOME with fake account directories:<br>• `CLAUDE_CONFIG_DIR=<dir> claude mcp get chrome-devtools` and the Codex equivalent succeed.<br>• Extra Claude accounts have hooks but **no** RTK instruction block; Codex accounts have both.<br>• The §4.4 block exists exactly once; user text outside it survives; a second run is `changed=0`; a symlinked `CLAUDE.md` is refused.<br>• Check with a throwaway account that `/memory` (or `/status`) lists the imported home `CLAUDE.md` and `RTK.md`; also test a missing home `CLAUDE.md`.<br>• No credential file is created or read |
| **5. Supervisor policy** | §6.1 text, §6.2 routes, README routing/failover | • Render test for account order.<br>• Scenario with a stub worker reply containing a usage-limit message: re-assign to the next account, then the other provider, then stop.<br>• One real low-effort run |
| **6. Rollout** | The user applies `ansible-playbook ai/all.yml -K`, logs in each account with the native commands, and relaunches sessions | The playbook's login check reports every account as logged in. `cao` lists the expected `mala_*_<account>` profiles and none of the stale ones |

---

## 10. Open questions

None blocking. D1–D4 resolved the v1 questions.

## 11. Unverified items (closed in the named phase)

- Whether #665's pane env reaches `codex` (Phase 2).
- The receipt string uv 0.13.8 writes for a `git+file://` install (Phase 2, isolated `UV_TOOL_DIR`).
- Whether the #665 rebase onto the pin is clean (Phase 2; stop and report if not).
- When Codex uses `SecretsKeyringAuthStorage`/`CODEX_AUTH` (§1.2; mitigated by `file` storage).
- Codex behaviour with a non-existent `CODEX_HOME` (Phase 1).
- The boolean field in `claude auth status --json` (Phase 1).
- Claude Code's behaviour when an imported file is missing (Phase 4).
- Whether server-managed settings of an organisation account block the bypass launch (Phase 2 smoke test).

## 12. Sources

- Claude Code:
  - https://code.claude.com/docs/en/env-vars
  - https://code.claude.com/docs/en/authentication
  - https://code.claude.com/docs/en/claude-directory
  - https://code.claude.com/docs/en/settings
  - https://code.claude.com/docs/en/memory
- Codex:
  - https://learn.chatgpt.com/docs/config-file/config-advanced
  - https://learn.chatgpt.com/docs/config-file/config-reference
  - https://raw.githubusercontent.com/openai/codex/main/codex-rs/login/src/auth/storage.rs
- CAO upstream:
  - https://github.com/awslabs/cli-agent-orchestrator/issues/661
  - https://github.com/awslabs/cli-agent-orchestrator/pull/665 (reviews: https://api.github.com/repos/awslabs/cli-agent-orchestrator/pulls/665/reviews)
  - https://github.com/awslabs/cli-agent-orchestrator/issues/1074
- uv:
  - https://raw.githubusercontent.com/astral-sh/uv/main/crates/uv-distribution-types/src/requirement.rs
  - https://github.com/astral-sh/uv/pull/11514
- Local:
  - `tasks/multi-account/evidence/*.txt` (CLI help)
  - `ai/roles/cao/files/install_cao.py` (offline receipt tests, §2.6)
