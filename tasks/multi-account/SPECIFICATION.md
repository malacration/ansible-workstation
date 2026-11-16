DESIGN / PLANNING TASK (no implementation). Output only into /home/andrew/git/ansible-workstation/tasks/multi-account/.

STEP 0: save this message verbatim to /home/andrew/git/ansible-workstation/tasks/multi-account/SPECIFICATION.md.

## User goal
The user wants the Ansible AI stack (/home/andrew/git/ansible-workstation/ai/, see ai/README.md) to support MULTIPLE ACCOUNTS per CLI provider, to spread token/usage limits:
- Claude Code: e.g. accounts "pessoal" (personal) and "rovema" (work). Each account gets its own isolated config/auth directory.
- Codex: same idea. The DEFAULT account of each provider stays in the user's home (~/.claude, ~/.codex); extra accounts live in separate directories.
- One binary per CLI is enough. Separate config dirs are what matter: Claude Code `CLAUDE_CONFIG_DIR`, Codex `CODEX_HOME`. Verify both against the official docs and the installed CLIs. Read-only checks only: `claude --help`, `codex --help` and the docs. Do NOT log in, do NOT read existing auth/credential files.
- CAO must be able to launch each agent profile under a specific account. Profile naming follows the convention already decided: `mala_<role>[_<level>]_<provider>`, extended with the account, e.g. `mala_developer_high_claude_rovema`. The default account could have no suffix; propose and justify.
- The supervisor then fails over across accounts when one hits its usage limit: first another account of the same provider, then the other provider.

## Key technical problem (investigate first)
The installed CAO (pinned commit) hard-codes the binaries. Look at
/home/andrew/.local/share/uv/tools/cli-agent-orchestrator/lib/python3.12/site-packages/cli_agent_orchestrator/providers/claude_code.py (~line 714: command_parts = ["claude", ...]) and providers/codex.py (~lines 1740/1773).
AgentProfile (models/agent_profile.py) has no per-profile env field. tmux.py sets per-terminal env (CAO_TERMINAL_ID via window_env/pane_env, `-e` flags, ~lines 1459, 1653, 1836, 2262).
Evaluate concrete mechanisms, with evidence (file:line), feasibility, risks and maintenance cost:
 (a) A small local CAO patch or upstream PR adding a per-profile launch env (e.g. `env: {CLAUDE_CONFIG_DIR: ...}`) passed into the tmux pane env. Check whether upstream main already has something like this; look at github.com/awslabs/cli-agent-orchestrator and its issues and PRs.
 (b) Multiple cao-server instances, one per account, each with its own env and/or HOME, plus `assign(..., target_host=...)` for cross-node delegation (needs CAO_ADVERTISED_URL). Check the caveats: the shared ~/.aws/cli-agent-orchestrator DB and agent-store, and tmux server env inheritance (one tmux server per uid; new sessions inherit the tmux server's global env, not the client's). TMUX_TMPDIR or `-L` may be needed.
 (c) A wrapper-on-PATH approach, if per-terminal env can select the account.
 (d) Anything else you find, e.g. CAO settings, providers that accept a command override, or `codexProfile` (note: codexProfile only layers config, not auth).
Recommend ONE approach.

## Also cover in the plan
- Ansible design: inventory/vars shape (e.g. `ai_accounts: {claude: [{name: pessoal, default: true}, {name: rovema, config_dir: ...}], codex: [...]}`), directory creation and permissions (0700), how auth is done per account (manual `claude`/`codex login` with the env var set, never by Ansible), and convenience shell wrappers such as `claude-rovema` / `codex-rovema`.
- MCP sync: sync_mcps.py reads ~/.codex/config.toml and ~/.claude.json. With separate dirs, each account has its own MCP config ($CLAUDE_CONFIG_DIR/.claude.json, $CODEX_HOME/config.toml). Decide whether to import per account or share one MCP set, and how the MCP installers (chrome_devtools, playwright_mcp roles) register into every account.
- RTK hooks (ai/roles/rtk) currently configure ~/.claude and ~/.codex. Extra accounts need them too.
- Profile count growth (6 roles × provider-accounts) and the routing/failover rules for the supervisor, including how the supervisor knows which accounts exist (the generated routes section).
- Interaction with the in-flight work: another developer is implementing the mala_* profile set in ai/roles/cao (sync_mcps.py, templates/profiles, defaults, README) — see /home/andrew/git/ansible-workstation/tasks/tiered-agent-profiles/SPECIFICATION.md and CHANGES_2.md. Do NOT edit those files. The plan must build on top of that work as a follow-up phase.
- Security: credentials never in the repo or the Ansible logs. Ansible must not read token files.
- A phased implementation plan with a test/verification strategy for each phase.

## Rules
- Read-only outside /home/andrew/git/ansible-workstation/tasks/multi-account/. No commits, no playbook runs against the real home.
- Do not read ~/.aws/credentials, ~/.ssh/*, .env, *.pem, ~/.claude/.credentials.json, ~/.codex/auth.json, or any other auth file.
- Do not send local paths, usernames or emails in web searches.
- Cite exact URLs and file:line for every claim about CAO, Claude Code or Codex behaviour. Mark anything unverified as such.

## Deliverable
/home/andrew/git/ansible-workstation/tasks/multi-account/PLAN.md, written in English. Then send_message to me with a concise summary in Portuguese: the recommended approach, the main risks, the phases, and the absolute path of the plan.

[Assigned by terminal 97593bc0. When done, send results back to terminal 97593bc0 using send_message]

## Update 1

REQUIREMENT UPDATE from the user. It overrides the original where they conflict.

1. NO implicit "default" account in CAO. Every CAO profile must name its account explicitly. That includes the account that lives in the user's home (~/.claude, ~/.codex), which also gets a name, e.g. `pessoal`. So: no suffix-less profiles. Names look like `mala_developer_high_codex_pessoal` and `mala_developer_high_codex_rovema`. Drop the "default account has no suffix" proposal.
2. Terminal behaviour: typing plain `codex` (or `claude`) must keep working exactly as today, with the normal prompt and the home account, and no wrapper changing it. To use another account, the user passes that account's DIRECTORY. Evaluate and propose the most natural UX for this. For example:
   - the native env var (`CODEX_HOME=<dir> codex`, `CLAUDE_CONFIG_DIR=<dir> claude`);
   - a small helper that takes a directory argument;
   - whether the CLIs have a native flag for a config dir. Verify with --help and the docs.
   Do not shadow or alias the plain `codex`/`claude` commands.
3. Applies to both Codex and Claude Code.
