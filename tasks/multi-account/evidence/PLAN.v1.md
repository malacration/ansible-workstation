# PLAN — Multiple accounts per CLI provider in the Ansible AI stack

Status: design only. Nothing outside `tasks/multi-account/` was changed.
Inputs: `SPECIFICATION.md`, including **Update 1**, which overrides the original spec where they conflict:

- no implicit default account in CAO;
- every profile names its account;
- the plain `claude`/`codex` commands stay untouched;
- other accounts are selected by **directory**.

Date of research: 2026-11-16. Installed versions: Claude Code `2.1.325`, codex-cli `0.169.0`. CAO is pinned at `3e30ea3ed6e7fb607b13358d81123afff5a8e69f` (`ai/roles/cao/defaults/main.yml:9`). That commit is also upstream `main` HEAD today.

Abbreviation: `CAO/` = `~/.local/share/uv/tools/cli-agent-orchestrator/lib/python3.12/site-packages/cli_agent_orchestrator/`.
Raw CLI help output is saved under `tasks/multi-account/evidence/`.

---

## 0. Executive summary

| Topic | Decision |
|---|---|
| Account isolation | One binary per CLI. One config dir per account: `CLAUDE_CONFIG_DIR` for Claude Code, `CODEX_HOME` for Codex. Both are documented and verified (§1). |
| Home account | It has a **name** (default `pessoal`) but **no env var**. Setting `CLAUDE_CONFIG_DIR=~/.claude` explicitly would move `.claude.json` from `~/.claude.json` into `~/.claude/` (§1.1). So in profiles, "home" means "env var absent". |
| Terminal UX | Plain `claude`/`codex` are unchanged; there are no aliases and no shadowing. Canonical form: `CLAUDE_CONFIG_DIR=<dir> claude` and `CODEX_HOME=<dir> codex`. Neither CLI has a native config-dir flag (verified). Convenience: one small helper, `ai-as <dir> <claude\|codex> [args…]` (§3). |
| CAO mechanism | **(a) A per-profile `env:` field**, using the same contract as upstream PR #665 (open, maintainer-APPROVED 2026-10-22, needs a rebase). Interim: a minimal local patch on the pinned commit that injects the variable into the launch command line. End state: bump the pin when #665 merges and drop the patch. Profiles do not change between the two (§2). |
| Profile names | `mala_<role>[_<level>]_<provider>_<account>`, e.g. `mala_developer_high_claude_rovema` and `mala_supervisor_codex_pessoal`. No suffix-less profiles. |
| Failover | Same role/level → next account of the same provider, in the configured order → the other provider's accounts → stop and report (§6). |
| Critical safety guard | Unpatched CAO **silently ignores** an unknown `env:` key at runtime. A `_rovema` profile would then run on the home account. `sync_mcps.py` must refuse to render non-home profiles unless the installed `AgentProfile` has an `env` field (§2.5). |

---

## 1. Verified CLI facts

### 1.1 Claude Code — `CLAUDE_CONFIG_DIR`

- Env var reference: *"Override the configuration directory (default: `~/.claude`). All settings, session history, and plugins are stored under this path. … Useful for running multiple accounts side by side: for example, `alias claude-work='CLAUDE_CONFIG_DIR=~/.claude-work claude'`."* — https://code.claude.com/docs/en/env-vars
- Multiple accounts: *"To stay signed in to multiple accounts at once … give each account its own configuration directory. … Each directory has its own settings, session history, and claude.ai login or API key."* — https://code.claude.com/docs/en/authentication#log-in-with-multiple-accounts
  - Caveat from the same page: *"Separate directories don't keep two Claude Console sign-ins without an API key apart"*, because that kind of sign-in is stored outside the config dir. claude.ai subscription logins are fine.
- Credentials: on Linux they live in `~/.claude/.credentials.json`. *"If you've set the `CLAUDE_CONFIG_DIR` environment variable, Claude Code keeps the `.credentials.json` file under that directory instead"* — https://code.claude.com/docs/en/authentication#credential-management
- `.claude.json`: *"If you set `CLAUDE_CONFIG_DIR`, every `~/.claude` path on this page lives under that directory instead. The same applies to `.claude.json`, which otherwise sits at `~/.claude.json`."* — https://code.claude.com/docs/en/claude-directory
  - **Consequence:** for an extra account, the MCP/user-scope config is `$CLAUDE_CONFIG_DIR/.claude.json`. For the home account, `CLAUDE_CONFIG_DIR` must stay **unset**, or `~/.claude.json` stops being read.
- A new directory triggers first-run onboarding and login (authentication page above). Each account therefore needs **one manual interactive run** before CAO can use it. Otherwise the CAO pane would hang in onboarding.
- No config-dir CLI flag. `claude --help` (evidence/claude-help.txt) only has `--settings`, `--setting-sources`, `--mcp-config`, `--strict-mcp-config`, `--plugin-dir` and `--add-dir`. None of them moves auth or state.

### 1.2 Codex — `CODEX_HOME`

- *"Codex stores its local state under `CODEX_HOME` (defaults to `~/.codex`)."* It holds `config.toml`, `auth.json` (file storage) *"or your OS keychain/keyring"*, `history.jsonl`, logs and caches. — https://learn.chatgpt.com/docs/config-file/config-advanced (redirect target of https://developers.openai.com/codex/config-advanced)
- `log_dir` defaults to `$CODEX_HOME/log`. Profile files are `$CODEX_HOME/<name>.config.toml`. — https://learn.chatgpt.com/docs/config-file/config-reference
- `cli_auth_credentials_store = file | keyring | auto | ephemeral` (same page).
- **Keyring isolation (source-verified).** The keyring account key is `cli|<first 16 hex of sha256(canonical CODEX_HOME)>`, under the service `"Codex Auth"`. Separate `CODEX_HOME`s therefore get separate keyring entries. — `compute_store_key` in https://raw.githubusercontent.com/openai/codex/main/codex-rs/login/src/auth/storage.rs
  - Caveat: the same file has a `SecretsKeyringAuthStorage` backend that uses a fixed secret name `CODEX_AUTH`. That would **not** be per-account. **Unverified** when Codex selects that backend.
  - Mitigation: pin `cli_auth_credentials_store = "file"` in each non-home account's `config.toml` (§4.4).
- No config-dir CLI flag. `codex --help` (evidence/codex-help.txt) has:
  - `-c key=value`;
  - `-p/--profile`, which *"Layer $CODEX_HOME/<name>.config.toml on top of the base user config"* (line 85-86). It layers config only, never auth, and the profile file itself lives inside `CODEX_HOME`;
  - `-C/--cd`, the working directory.
- Login status without reading files: `codex login status` (evidence/codex-login-status-help.txt) and `claude auth status [--json|--text]` (evidence/claude-auth-status-help.txt). Their output fields were **not** captured on purpose: no login state was read in this task.

---

## 2. CAO: how a profile can select an account

### 2.1 Why nothing works today without a code change (evidence)

1. **The binaries are hard-coded.**
   - Claude: `CAO/providers/claude_code.py:714,717,719` (`command_parts = ["claude", …]`).
   - Codex: `CAO/providers/codex.py:1740,1773` (`["codex", …]`).
   - The command string is typed into the pane's shell with `send_keys` (`codex.py:2353-2356`; Claude has the same pattern).
2. **The Claude launch actively unsets `CLAUDE*`.** `claude_code.py:873-880` builds `unset $(env | sed -n 's/^\(CLAUDE[A-Z_]*\)=.*/\1/p' | grep -v …USE_/SKIP_…/EFFORT_LEVEL); claude …`. A `CLAUDE_CONFIG_DIR` that reaches the pane, by any route, is removed right before `claude` starts.
3. **CAO filters these variables out of the pane env.**
   - `_BLOCKED_ENV_PREFIXES = ("CLAUDE", "CODEX_", "__MISE_")` at `CAO/clients/tmux.py:1335`.
   - The filter applies to the server env forwarded into new sessions (`_forwarded_server_env`, `tmux.py:1409-1430`) and to operator `--env` values (`_merge_extra_env`, `tmux.py:1384-1406`, which drops them with a warning).
   - So `CODEX_HOME` and `CLAUDE_CONFIG_DIR` can never be passed through `cao launch --env` (`CAO/cli/commands/launch.py:209`) or through the cao-server's own environment.
4. **No per-profile env field.**
   - `AgentProfile` (`CAO/models/agent_profile.py:328-467`) has no `env`.
   - `claudeConfig` only maps `effort` and `fallback_model` (`claude_code.py:774-787`). Other keys are ignored.
   - `codexConfig` keys all become `-c` overrides (`codex.py:1983`), so a "home" key cannot be smuggled in.
   - Upstream `main` is the same; the raw `models/agent_profile.py` on `main` has no `env` field.
5. **Silent-ignore hazard.**
   - `AgentProfile` has no `extra="forbid"`. The only `model_config` in the file is on `ProfileParamDecl` (`agent_profile.py:313`). Verified locally: `AgentProfile(name='x', description='d', env={...})` loads without error and drops `env`.
   - The JSON schema does reject it (`CAO/schemas/agent_profile.schema.json:277`, `"additionalProperties": false`). However, the schema is only used by the validator (`CAO/services/profile_validator.py:119`), not at launch.

### 2.2 Options evaluated

| Option | Feasibility | Evidence | Risk | Maintenance | Verdict |
|---|---|---|---|---|---|
| **(a) Per-profile `env:` field** | High. Upstream already has it: issue #661 and PR #665 *"feat(profiles): per-profile env vars injected into the worker terminal"* | https://github.com/awslabs/cli-agent-orchestrator/issues/661, https://github.com/awslabs/cli-agent-orchestrator/pull/665 (open, `mergeable_state: dirty`, 14 commits, 21 files, +1274/−50; reviews: haofeif COLLABORATOR **APPROVED** 2026-10-22 after earlier CHANGES_REQUESTED; needs a rebase on main) | Low once merged. Interim: we carry a patch | Interim: one small patch, re-checked on each pin bump. After the merge: none | **Recommended** |
| (b) One cao-server per account (`CAO_HOME_DIR`, `CAO_API_PORT`, `assign(target_host=…)`) | Low | `CLAUDE*`/`CODEX_*` are stripped from the forwarded server env (`tmux.py:1335,1409-1430`). Only a different **HOME** (`tmux.py:1352`, an essential key) would reach the pane, and that breaks `~/.local/bin`, git/ssh config, RTK, the agent-store and CAO memory. Separate `CAO_HOME_DIR` (`constants.py:145`) gives separate DBs, agent-stores and memories. Cross-node delegation needs `CAO_ADVERTISED_URL` (`constants.py:514`) plus auth. All servers share one tmux server per uid unless `TMUX_TMPDIR`/`-L` is used. | High: split state, callbacks across nodes, supervisor must pick a host | High | Rejected |
| (c) Wrapper named `claude`/`codex` first on PATH inside CAO panes | Low | It cannot know the **profile** without a patch, because `CAO_*` env is per session, not per profile (`terminal_service.py:3192,3221`). The only hack would be to query the CAO API with `CAO_TERMINAL_ID` and parse the profile-name suffix. PATH order in the pane depends on the user's zsh rc files. | Violates Update 1 ("do not shadow"). Fragile | Medium | Rejected |
| (d1) `codexProfile` | No | It layers `$CODEX_HOME/<name>.config.toml` and cannot move `CODEX_HOME` or auth (`agent_profile.py` comment at the `codexProfile` field; codex-help.txt:85-86) | — | — | Rejected |
| (d2) Command override field | Hermes only | `hermesProfile` names a wrapper command (`CAO/providers/hermes.py:162`). Claude and Codex have no equivalent | — | — | Not applicable |
| (d3) Kiro per-launch home | Precedent only | `_add_kiro_home_to_window_env` (`CAO/services/terminal_service.py:1896-1907`) shows CAO already accepts "per-launch home" designs. It is Kiro-only | — | — | Supports (a) |

### 2.3 Recommended: (a), the upstream-compatible `env:` contract

Profiles carry, for **non-home** accounts only:

```yaml
env:
  CLAUDE_CONFIG_DIR: /home/<user>/.claude-rovema   # claude_code profiles
# or
env:
  CODEX_HOME: /home/<user>/.codex-rovema           # codex profiles
```

Home-account profiles (`…_pessoal`) carry **no** `env` (§1.1).
Values are absolute paths: PR #665 states values are passed verbatim with no `~` expansion.

Two delivery tracks share one profile format:

- **Track U, the end state.** When PR #665 merges, bump `cao_git_ref` to the merge commit and delete the local patch. Re-run the Phase 2 tests.
  - #665 injects env through tmux `-e` (scoped to the window or pane).
  - The Claude `unset` spares the `CLAUDE*` names the profile declares.
  - Profile env bypasses the prefix blocklist (PR body).
  - Codex is not mentioned in the PR body. Pane env should still reach `codex`, but this is **unverified** until tested.
- **Track L, the interim local patch.** The patch is small, kept in the repo, and is a *subset* of #665's contract, so profiles are forward-compatible:
  1. `models/agent_profile.py`: add `env: Optional[Dict[str, str]] = None`, with a validator for POSIX names and string values under the 2048-byte cap (the `tmux.py` constant).
  2. `schemas/agent_profile.schema.json`: add an `env` object with string values.
  3. `providers/claude_code.py` around line 880: `return f"{unset_cmd}; {assignments} {claude_cmd}"`, where `assignments = " ".join(f"{k}={shlex.quote(v)}" for k, v in sorted(profile.env.items()))`.
     - The inline assignment comes **after** the unset, so it survives the unset and any rc-file export.
     - It is scoped to the `claude` process, so it cannot leak session-wide. That leak was one of haofeif's #665 findings.
  4. `providers/codex.py` around line 1989: prefix the same assignments to the `codex` command, before the `developer_instructions` command substitution.
  5. Optional: `claude_code.py:899` (`_ensure_skip_bypass_prompt_setting`) writes only `~/.claude/settings.json`. Either make it honour `env.CLAUDE_CONFIG_DIR`, or leave it and let Ansible seed the key per account (§4.4). **Choose: Ansible seeding** to keep the patch minimal.
  6. Unit tests in the CAO tree:
     - the command string contains the assignment after `unset`;
     - no `env` → no assignment;
     - values are shell-quoted;
     - the field round-trips through `load_agent_profile`.

  Delivery of the patched build, kept pin-verifiable:
  - Ansible clones `cao_git_url` at `cao_git_ref` into `{{ ai_stack_cache_dir }}/cao-src/<sha>`.
  - It verifies `git rev-parse HEAD == cao_git_ref`, then runs `git apply --check` and `git apply` on `ai/roles/cao/files/patches/*.patch`.
  - It installs with `cli-agent-orchestrator @ file://…`.
  - New variable: `cao_source: git_patched`.
  - **Unverified:** whether `ai/roles/cao/files/install_cao.py` replays a `directory` requirement from the uv receipt (it is strict about receipt shapes, `install_cao.py:33-52`, `receipt_options`). The Phase 2 work must test this, and extend the script if needed.
  - Alternative that needs a user decision because it is outward-facing: publish the rebased #665 branch on a personal fork and point `cao_git_url` at it.

### 2.4 Other hard-coded home paths in CAO

| Location | Behaviour | Handling |
|---|---|---|
| `claude_code.py:899` | Writes `skipDangerousModePermissionPrompt: true` to `~/.claude/settings.json` on every Claude init (`claude_code.py:1209`) | Without the key, the first CAO launch on an extra account shows the bypass dialog and blocks. Ansible seeds the key into `$CLAUDE_CONFIG_DIR/settings.json` per account (§4.4) |
| Workspace trust dialog (`claude_code.py:187,965-967`; `codex.py:250-259`) | Dismissed at the TUI level, so it does not depend on the account | — |
| Claude `--mcp-config <tmp> --strict-mcp-config` (`claude_code.py:839-841`) | Inside CAO, the profile's MCP set is authoritative and the account's `.claude.json` MCPs are ignored | Simplifies §5 |
| Codex `-c mcp_servers.*` overrides (`codex.py:1907-1946`) | Layered over `$CODEX_HOME/config.toml`, so the account's own MCPs also load. HTTP MCPs are intentionally inherited from the account config (`ai/roles/cao/files/sync_mcps.py:138-150` at the time of writing; that file is being edited by the in-flight work) | Each Codex account must carry the HTTP MCP entries (§5) |

### 2.5 Mandatory guards

- `sync_mcps.py` must render a profile with `env` only if `'env' in AgentProfile.model_fields` for the installed CAO. Otherwise it fails with a clear message: "installed CAO lacks per-profile env; account profiles would silently run on the home account".
- It must also check the schema's `properties` includes `env`, so `cao profile validate` stays green.
- `env` keys are allow-listed in `sync_mcps.py`: `CLAUDE_CONFIG_DIR` for `claude_code`, `CODEX_HOME` for `codex`. Credentials are never accepted (PR #665 warns that `GET /agents/profiles/{name}` returns `env` to read-scope callers).

---

## 3. Terminal UX (Update 1, item 2)

Requirements: plain `claude`/`codex` behave exactly as today (home account, normal prompt), with no alias or shadowing. Another account is chosen by passing its **directory**.

| Option | Example | Pros | Cons |
|---|---|---|---|
| Native env var | `CLAUDE_CONFIG_DIR=~/.claude-rovema claude`, `CODEX_HOME=~/.codex-rovema codex` | Zero tooling. Officially documented (Anthropic's docs even show the alias pattern). Works in every shell and script | Long to type. A typo silently creates a fresh Claude dir and starts onboarding. Using `~/.claude` explicitly breaks `.claude.json` (§1.1). Behaviour with a non-existent `CODEX_HOME` is **unverified** |
| Native flag | — | — | **Does not exist** in either CLI (§1.1, §1.2) |
| Helper taking a directory | `ai-as ~/.claude-rovema claude`, `ai-as ~/.codex-rovema codex exec "…"` | Short, validated and explicit. Never shadows anything. Handles the home-dir edge case | One more script (Ansible-managed) |
| Per-account wrappers | `claude-rovema` | Shortest | Names an account rather than a directory, so it is against Update 1's "pass the directory". One wrapper per account per CLI |

**Proposal**

1. Document the native env var form as **canonical**.
2. Ship one helper, `~/.local/bin/ai-as` (name open, see §10), templated by Ansible. Behaviour:
   - Usage: `ai-as <dir> <claude|codex> [args…]`. The command must be `claude` or `codex`; anything else is refused. It is resolved through `PATH` exactly as the plain command would be, and the helper `exec`s it.
   - `<dir>` is expanded (`~`) and made absolute. It must exist, be a directory owned by the user, and not be a symlink. The helper warns if the mode is not `0700`.
   - It sets `CLAUDE_CONFIG_DIR` (for `claude`) or `CODEX_HOME` (for `codex`).
   - If `<dir>` resolves to the home default (`~/.claude` or `~/.codex`), it **unsets** the variable instead, which preserves `~/.claude.json`.
   - It refuses a Claude-looking dir passed to `codex` and the reverse, using a simple heuristic: a sentinel file `.ai-stack-account` written by Ansible with `provider=` and `name=`. Home dirs are recognised by path.
   - It does not log in, read or print credentials.
3. Optional zsh named directories, documented only and not managed: `hash -d rovema-claude=~/.claude-rovema` → `CLAUDE_CONFIG_DIR=~rovema-claude claude`.
4. Per-account wrappers are **off** by default (`ai_accounts_shell_wrappers: false`). If enabled, they are thin scripts named `<cli>-<account>` that call `ai-as`, and never `claude` or `codex` themselves.

Directory naming convention, the default for non-home accounts: `~/.claude-<account>` and `~/.codex-<account>`, following Anthropic's `~/.claude-work` example. It can be overridden per account.

---

## 4. Ansible design

### 4.1 Variables (`ai/vars.example.yml`, user-facing)

```yaml
# Order = failover priority inside each provider. Exactly one entry per
# provider may be `home: true` (uses ~/.claude + ~/.claude.json or ~/.codex,
# and gets NO env var). Every account has an explicit name (Update 1).
ai_accounts:
  claude:
    - {name: pessoal, home: true}
    - {name: rovema}                       # dir defaults to ~/.claude-rovema
  codex:
    - {name: pessoal, home: true}
    - {name: rovema, dir: "{{ ai_stack_home }}/.codex-rovema"}
# Optional per account: cao: false  (exclude from CAO profiles, terminal-only)
```

The default, used when the user sets nothing, preserves today's behaviour under an explicit name:
`ai_accounts: {claude: [{name: pessoal, home: true}], codex: [{name: pessoal, home: true}]}`, from `ai_accounts_home_name: pessoal`.

Assertions (with clear `fail_msg`), run in a new `ai_accounts` role or in `ai_stack`:

- the keys are only `claude` and `codex`;
- each list is non-empty;
- names match `^[a-z][a-z0-9]{0,15}$`. There is no `_`, because `_` is the profile-name separator and a suffix must parse unambiguously;
- names are unique per provider;
- at most one `home: true` per provider;
- a non-home `dir` is absolute, lies under `ai_stack_home` (required by RTK's `safe_path`, `ai/roles/rtk/files/configure_rtk.py:26-36`), is not `~/.claude`/`~/.codex`, and is not shared by two accounts;
- the longest generated profile name is ≤ 64 characters. `mala_reviewer_advanced_claude_pessoal` is 37 characters.

The role then derives one fact consumed by every other role:

```yaml
ai_accounts_resolved:
  claude_code:
    - {name: pessoal, home: true,  dir: ~/.claude,         mcp_config: ~/.claude.json,                 env: {}}
    - {name: rovema,  home: false, dir: ~/.claude-rovema,  mcp_config: ~/.claude-rovema/.claude.json,  env: {CLAUDE_CONFIG_DIR: /abs/.claude-rovema}}
  codex:
    - {name: pessoal, home: true,  dir: ~/.codex,          mcp_config: ~/.codex/config.toml,           env: {}}
    - {name: rovema,  home: false, dir: ~/.codex-rovema,   mcp_config: ~/.codex-rovema/config.toml,    env: {CODEX_HOME: /abs/.codex-rovema}}
```

All paths are absolute in the real fact.

### 4.2 Directories and permissions

- For non-home accounts only: `file: state=directory mode=0700 owner=ai_stack_user`, run as the user (same `become_user` pattern as `ai/roles/claude/tasks/main.yml:3-5`).
  - The role refuses a symlink, using `stat` with `follow: false` and failing on `islnk`.
  - It never changes the mode of existing files inside the directory.
  - It never touches `~/.claude` or `~/.codex` permissions.
- It writes the sentinel `<dir>/.ai-stack-account` (`0600`, content `provider=…\nname=…`), used by `ai-as`.
- It writes `~/.local/share/ai-stack/accounts.json` (`0600`). The file holds names, providers, dirs and order only, and is the input for `sync_mcps.py` and `ai-as`.
- **Ansible never creates, reads, copies or templates** `.credentials.json`, `auth.json` or keyring entries.
- The `cache_dir` (`ai_stack_cache_dir`) is untouched.

### 4.3 Authentication (manual, never Ansible)

The README (Portuguese) documents, per extra account, a one-time run:

```sh
ai-as ~/.claude-rovema claude              # first run: onboarding + /login
ai-as ~/.codex-rovema codex login          # or: CODEX_HOME=~/.codex-rovema codex login
```

A status check that reads no files: the generated `ai-stack-accounts status` runs `claude auth status` or `codex login status` with the right env var and prints only `name: logged-in yes/no`.

- It decides from the exit code and, for Claude, a single boolean field. The JSON field name is **unverified**; Phase 1 confirms it.
- The Ansible task that calls it uses `no_log: true` and `changed_when: false`. It **warns** but never fails when an account is not logged in, because login is the user's step.

### 4.4 Per-account seeding (no credentials)

| File | What | Who |
|---|---|---|
| `$CLAUDE_CONFIG_DIR/settings.json` | JSON merge of `skipDangerousModePermissionPrompt: true` (§2.4). All other keys are preserved, symlinks are refused, and the write is atomic with mode `0600` | `cao` role (follow-up phase) |
| `$CLAUDE_CONFIG_DIR/CLAUDE.md` | Optional `@~/.claude/CLAUDE.md` import line in an owned block, so extra accounts share the user's global instructions (Claude memory imports) | `ai_accounts` role, `ai_accounts_share_claude_md: true` |
| `$CODEX_HOME/config.toml` | Top-level `cli_auth_credentials_store = "file"` for non-home accounts (§1.2 caveat), merged TOML-aware. Nothing else is touched | `codex` role |

### 4.5 MCP installers (`chrome_devtools`, `playwright_mcp`)

- Loop over `ai_accounts_resolved[client]`, with `environment: "{{ ai_stack_environment | combine(account.env) }}"`.
  - Claude: `claude mcp add --scope user …` writes to that account's `.claude.json`.
  - Codex: `codex mcp add …` writes to that account's `config.toml`.
- Replace the current read of `~/.claude.json` with a Python one-liner (`ai/roles/chrome_devtools/tasks/claude.yml:2-20`), using `claude mcp get <name>` under the account env.
  - This avoids parsing a file that also holds account details.
  - It keeps idempotence (compare command/args; `changed_when` only on add/remove).
- Check mode stays the same: the same skip semantics as today.

### 4.6 RTK

- `configure_rtk.py` already takes `--claude-dir` and `--codex-dir` (`ai/roles/rtk/files/configure_rtk.py:131-141,227-228`). Both are currently `required=True`.
- Extend it to accept repeated `--claude-dir`/`--codex-dir` values (or one invocation per account with `--clients` narrowed), and drive it from `ai_accounts_resolved`.
- Targets per account:
  - Claude: `settings.json` hooks plus the `CLAUDE.md`/`RTK.md` owned block;
  - Codex: `hooks.json` plus the `AGENTS.md`/`RTK.md` block.
- `safe_path` (inside home, no symlinks) already fits the dir constraints in §4.1.

---

## 5. MCP sync design (`sync_mcps.py`, follow-up to the tiered-profiles work)

Decision: **one shared MCP set per provider, imported from that provider's home account**. All accounts' profiles get the same set.

Reasons:

- Inside CAO, Claude uses `--strict-mcp-config` (`claude_code.py:839-841`), so the profile is the only source and per-account import buys nothing.
- Shared sets keep worker capabilities identical across accounts, which matters for failover: a re-assigned task must see the same tools.
- Interactive use of an extra account still gets the installer-managed MCPs (§4.5).

Exception: **Codex HTTP MCPs** are inherited from the account's own `config.toml` (`ai/roles/cao/files/sync_mcps.py:138-150` at the time of writing; that file is being edited by the in-flight work).

- For every Codex account, `sync_mcps.py` checks that each HTTP MCP from the home account exists with the same `url` in `$CODEX_HOME/config.toml`.
- If one is missing, it fails with the account name and the command to run: `ai-as <dir> codex mcp add …`.
- OAuth-backed HTTP MCPs need a separate `codex mcp login` per account. That is manual and documented.

Changes, on top of the merged tiered-profiles code:

1. New `--accounts-file` option (JSON from §4.2). Without it, behaviour is equivalent to `{claude_code: [{name: pessoal, home: true}], codex: [same]}`.
2. Name: `<prefix>_<definition>_<client_label>_<account>`, keeping the 64-character check.
3. Rendering:
   - `env` comes from §2.3, guarded by §2.5, and is absent for home accounts;
   - tags gain `account-<name>`;
   - the description gets ` (account <name>)` appended;
   - the existing `provider`, model/effort and config-block stripping logic is unchanged.
4. Routes section (§6.2) is generated from the full matrix.
5. Prune: keep the marker-only, no-symlink rules.
   - Candidates are `<prefix>_*_<label>.md`, which are the pre-account names produced by the tiered work (they become stale), plus `<prefix>_*_<label>_*.md` entries that are not in the current set, for example a removed account.
   - Return the `removed` list as today. Old `ai_stack_*` handling is unchanged.
6. `--check` stays a full dry run, including removals.
7. `accounts.json` reading rejects non-allow-listed keys, so no secrets can enter the file.

Profile count = `len(definitions) × Σ_provider len(accounts with cao≠false)`.

| Accounts (claude + codex) | Profiles |
|---|---|
| 1 + 1 (default) | 12 |
| 2 + 2 (`pessoal`, `rovema`) | 24 |
| 3 + 3 | 36 |

Mitigation, if `find_profiles` noise or prompt size becomes a problem: `cao_account_profile_filter` (for example, supervisors only on selected accounts). It is not needed at 24.

---

## 6. Supervisor routing and failover

### 6.1 Policy (extends CHANGES_2 A2; written in English into the supervisor template)

- Task classification (LOW/MEDIUM/HIGH, escalators, `[level:]`/`[nivel:]`) and provider preference are unchanged:
  - development prefers Claude, review prefers Codex;
  - `[provider:]`/`[provedor:]` overrides.
- **Account order**: within a provider, use the accounts in the listed order (the routes section states it).
- New override tag: `[account: <name>]` / `[conta: <name>]`. It applies to that request's workers. If the user also gives `[provider: …]`, both must match an existing profile, or the supervisor asks.
- **Usage-limit failover.** The signals list from CHANGES_2 is unchanged. For worker W on provider P, account A:
  1. Confirm W is not still working (check its state and output) before acting.
  2. `delete_terminal(W)`.
  3. Mark `(P, A)` exhausted in the task file's "Account ledger", with the reset time if the message shows one.
  4. Re-assign the **same task file** to the same role/level on the **next non-exhausted account of P**.
  5. If every account of P is exhausted, use the other provider, again in that provider's account order.
  6. If everything is exhausted, stop and report to the user with the known reset times. Never loop.
  7. Do not reuse an exhausted account until its reset time has passed or the user says it is available.
- Known limitation: the **supervisor's own** account can run out. It cannot fail itself over. The README tells the user to relaunch the supervisor under another account (`cao launch --agents mala_supervisor_claude_rovema`). The task files and the ledger make the hand-over possible.

### 6.2 How the supervisor knows which accounts exist

`sync_mcps.py` appends a generated section (replacing the CHANGES_2 one) built from `accounts.json`, so it is always in sync with Ansible:

```
## AI stack: accounts, providers and delegation
This profile runs on `claude_code`, account `pessoal`.
Account failover order — claude: pessoal → rovema; codex: pessoal → rovema.

| definition | claude/pessoal | claude/rovema | codex/pessoal | codex/rovema |
|---|---|---|---|---|
| developer_low | `mala_developer_low_claude_pessoal` | `mala_developer_low_claude_rovema` | … | … |
| … (all 6 definitions) |
```

---

## 7. Interaction with the in-flight tiered-profiles work

- The files owned by that work are **not edited** by this plan until it is approved: `ai/roles/cao/files/sync_mcps.py`, `templates/profiles/*`, `defaults/main.yml`, `ai/README.md`, `ai/vars.example.yml` and `ai/tests/test_sync_mcps.py` (see `tasks/tiered-agent-profiles/SPECIFICATION.md`, `CHANGES_2.md`).
- This plan starts **after** that work is reviewed and approved (Phase 0 gate). It reuses:
  - its prefix/label naming, extended with `_<account>`;
  - `--base-dir`, prune and markers;
  - `cao_profile_definitions`, efforts and models;
  - the CHANGES_2 routing text, extended with accounts.
- Migration: the 12 `mala_<def>_<label>` profiles become `mala_<def>_<label>_pessoal`. The old ones are pruned as marker-bearing stale files (§5.5). Users must relaunch any running sessions that use the old names.

---

## 8. Security

- No credentials in the repo, in `accounts.json`, in profiles (§2.5 allow-list) or in Ansible output.
  - Status checks use `no_log: true` and print only booleans.
  - No task reads `.credentials.json`, `auth.json`, keyrings or `.env`.
- Dirs are `0700`. The sentinel and `accounts.json` are `0600`. Symlinks are refused everywhere a write happens (dirs, `settings.json`, `config.toml`, RTK files), consistent with the existing roles.
- Profile `env` exposes only directory paths. PR #665 notes that profile env is readable by any API read-scope caller, so this is acceptable for paths and forbidden for secrets.
- **Work-account policy risk.** `rovema` may be a Team/Enterprise login with **server-managed settings**. Those are fetched per login and cached in `<dir>/remote-settings.json` (https://code.claude.com/docs/en/claude-directory). Such settings could, for example, disable bypass-permissions mode. CAO's `--dangerously-skip-permissions` launch would then fail or block in that account. Phase 2 must smoke-test each account. There is also an organisational question (§10.1): whether personal tasks may run on the work account.
- Transcripts and auto-memory are stored per config dir (https://code.claude.com/docs/en/claude-directory). Work done under `rovema` is stored in `~/.claude-rovema/projects/…`. CAO memory (`~/.aws/cli-agent-orchestrator`) stays shared.

---

## 9. Phased implementation and verification

All phases follow these rules:

- no runs against the real home before user approval;
- tests use an isolated HOME under `tasks/multi-account/isolated-home/`;
- logs are saved under `tasks/multi-account/`;
- unit tests run with `"$(uv tool dir)/cli-agent-orchestrator/bin/python" -m unittest discover -s ai/tests -v`;
- syntax checks: `ansible-playbook ai/all.yml --syntax-check` and per-playbook.

| Phase | Scope | Verification |
|---|---|---|
| **0. Gate** | Tiered-profiles work (CHANGES_2) approved by the reviewer. Record a baseline | Existing unit tests and syntax-checks green; log saved |
| **1. Accounts model + terminal UX** | New `ai_accounts` role: vars, assertions, `ai_accounts_resolved`, dirs, sentinel, `accounts.json`, `ai-as` helper, `ai-stack-accounts status`. README (pt-BR) login guide. No CAO change | Assertion tests: an `ansible-playbook` run with bad vars must fail, using a small test playbook. Helper shell tests:<br>• sets the right variable;<br>• **unsets** it for `~/.claude` and `~/.codex`;<br>• refuses a missing dir, a symlink, a wrong provider or an unknown command;<br>• passes args through.<br>Also: `type claude`/`type codex` still resolve to the real binaries, with no alias or function. Idempotence (second run `changed=0`), check mode, and the role run against the isolated HOME |
| **2. CAO per-profile env** | Track L patch + `cao_source: git_patched` install path (or Track U if #665 has merged) | Tests in the patched CAO tree (§2.3.6). The patched CAO's own suite passes for `test_claude_code*`, `test_codex*` and `test_agent_profile*`. Integration with an isolated `CAO_HOME_DIR`, `TMUX_TMPDIR` and a stub `claude`/`codex` **only in the test PATH** that dumps its env: `_rovema` profile → variable = account dir; `_pessoal` → variable absent. Manual smoke test (user-approved): launch `mala_developer_low_claude_rovema`, ask it to run `echo "$CLAUDE_CONFIG_DIR"`, and check `/status` shows the rovema login; same for Codex with `CODEX_HOME` |
| **3. sync_mcps accounts** | `--accounts-file`, naming, `env` rendering, guard §2.5, prune of pre-account names, routes table, Codex HTTP-per-account check | Unit tests for each item, including: the guard fails on unpatched CAO; there is no `env` for home; the allow-list rejects other keys; 64-character limit; invalid account names; prune removes only marker files (symlink kept). Render all 24 into an isolated HOME and validate each with the patched `load_agent_profile` and `cao profile validate` |
| **4. Installers + RTK + seeding** | MCP roles loop per account; `configure_rtk.py` multi-dir; `skipDangerousModePermissionPrompt`; Codex `cli_auth_credentials_store` | Isolated HOME with fake account dirs:<br>• `ai-as <dir> claude mcp get chrome-devtools` and the Codex equivalent succeed;<br>• RTK hooks/blocks are present in every account;<br>• no credential file was created or read (`find` for `.credentials.json`/`auth.json` shows none was created; an `strace -e trace=openat` spot check on the merge scripts is optional);<br>• idempotence and check mode |
| **5. Supervisor policy** | Template text §6.1, generated routes §6.2, README routing/failover section | Render test: the routes table has every account in order. Scenario test with a stub worker reply containing "You've hit your usage limit": the supervisor re-assigns to `…_claude_rovema`, then to `…_codex_pessoal` when rovema is also marked exhausted, then stops. Run once with real CLIs at low effort |
| **6. Rollout** | User applies `ansible-playbook ai/all.yml -K`, logs in per account, relaunches sessions | `ai-stack-accounts status` shows every account logged in. `cao` lists 24 `mala_*_<account>` profiles and no stale ones |

---

## 10. Open questions for the user

1. **Account usage policy.** May personal-project tasks run on the work account `rovema`, and the reverse? If not, add `ai_accounts[].cao: false`, or a per-account path allow-list that the supervisor respects.
2. **Interim patch vs waiting.** Carry the local patch (Track L) now, or wait for PR #665 to merge? Publishing a fork is outward-facing and needs the user's OK.
3. **Helper name**: `ai-as`, or another name.
4. **Shared instructions.** Should extra Claude accounts import `~/.claude/CLAUDE.md` (§4.4)? Codex `AGENTS.md` has no import syntax; it would be copied or left separate.

## 11. Unverified items (to be closed in the named phase)

- Whether PR #665's pane-env injection reaches `codex` (Track U, Phase 2).
- When Codex uses `SecretsKeyringAuthStorage` with the fixed name `CODEX_AUTH` (§1.2). Mitigated by pinning `file` storage.
- Codex behaviour with a non-existent `CODEX_HOME` (Phase 1; `ai-as` validates first anyway).
- The field name of `claude auth status --json` used for the logged-in boolean (Phase 1).
- Whether `install_cao.py` supports a local directory requirement in the uv receipt (Phase 2).
- Whether server-managed settings of a Team/Enterprise account block CAO's bypass launch (Phase 2 smoke test).

## 12. Sources

- Claude Code: https://code.claude.com/docs/en/env-vars · https://code.claude.com/docs/en/authentication · https://code.claude.com/docs/en/claude-directory · https://code.claude.com/docs/en/settings
- Codex: https://learn.chatgpt.com/docs/config-file/config-advanced · https://learn.chatgpt.com/docs/config-file/config-reference · https://raw.githubusercontent.com/openai/codex/main/codex-rs/login/src/auth/storage.rs
- CAO upstream: https://github.com/awslabs/cli-agent-orchestrator/issues/661 · https://github.com/awslabs/cli-agent-orchestrator/pull/665 (reviews: https://api.github.com/repos/awslabs/cli-agent-orchestrator/pulls/665/reviews) · issue #1074 (per-launch `CODEX_HOME` for ephemeral children, a related design): https://github.com/awslabs/cli-agent-orchestrator/issues/1074
- Local CLI help: `tasks/multi-account/evidence/*.txt`
