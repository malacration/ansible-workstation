<cao-memory>
## Context from CAO Memory
- [project] cao-role-tool-limits-reviewer-supervisor: CAO role defaults (constants.ROLE_TOOL_DEFAULTS): supervisor = @cao-mcp-server+fs_read+fs_list, reviewer = @builtin+fs_read+fs_list+@cao-mcp-server (no fs_write/execute_bash), so reviewer/supervisor sessions cannot write task/review files or run tests unless the profile sets explicit allowedTools.
- [project] tiered-agent-profiles-design: Decision (2026-11-16): CAO agent profiles are managed by the ansible-workstation ai/ stack (role cao, sync_mcps.py). Design: generalist developer_low/medium/high (reasoning effort low/medium/high), reviewer_basic (lowest effort, simple tasks) and reviewer_advanced (high effort, high tasks); the supervisor classifies each task and routes accordingly; workers stay on the supervisor's provider.
- [global] mala-profiles-provider-routing: User's own CAO profiles are named mala_<role>_<level>_<codex|claude> (e.g. mala_supervisor_codex, mala_developer_medium_claude, mala_reviewer_basic_codex). The supervisor chooses the provider: development preferably on Claude Opus, review preferably on Codex, Codex developers allowed at any level, and it fails over to the other provider when one hits a usage/token limit.
- [global] ansible-self-contained-dependencies: The user expects Ansible to install and refresh required repository signing keys and resolve its own dependencies, rather than requiring manual host repair. The current authorized change is the Chrome APT playbook in /home/andrew/git/ansible-workstation; previously cancelled CAO/RTK work must not be resumed.
</cao-memory>

IMPLEMENTATION TASK — install herdr via the Ansible AI stack and make the CAO terminal backend selectable.

STEP 0: save this message verbatim to /home/andrew/git/ansible-workstation/tasks/herdr-install/SPECIFICATION.md. Keep notes, logs and any isolated HOME under /home/andrew/git/ansible-workstation/tasks/herdr-install/.

## Context
Repo: /home/andrew/git/ansible-workstation. The AI stack is in ai/ (read ai/README.md fully). CAO supports two terminal backends, verified in the installed package /home/andrew/.local/share/uv/tools/cli-agent-orchestrator/lib/python3.12/site-packages/cli_agent_orchestrator/:
- tmux (default);
- herdr (EXPERIMENTAL, a Rust terminal multiplexer). See backends/factory.py and backends/herdr_backend.py; constants.py mentions herdr v0.9.5.
Backend selection is per cao-server process, in this order: `cao-server --terminal <tmux|herdr>` > env `CAO_TERMINAL_BACKEND` > CAO settings `terminal.backend` > "tmux".

## Goal
1. A new optional component that installs the herdr CLI for `ai_stack_user`, following the conventions of the existing roles. Use ai/roles/rtk as the model for a pinned, checksum-verified binary release: ai/roles/rtk/tasks/release.yml, defaults, README.
   - Find the OFFICIAL herdr source/release channel (web search) and record exact URLs. Pin a version compatible with the installed CAO: check what herdr_backend.py expects (CLI subcommands, flags, version notes) and state why the pin is compatible.
   - Verify checksums against officially published checksums. If upstream publishes none, stop and report instead of inventing a trust path. Never pipe a remote script into a shell without checksum verification.
   - Install into the stack's layout (~/.local/bin for the command, ~/.local/share/ai-stack/... for payloads), as the non-root user. Idempotent, check-mode friendly, with an explicit upgrade path (the `ai_stack_upgrade` / `herdr_version=latest` pattern used by the other roles).
   - Supported architectures: x86_64 and ARM64 if upstream ships them; otherwise skip clearly.
   - New entry point ai/herdr.yml, imported into ai/all.yml with a tag `herdr`, behind `herdr_enabled`. Default: install (true), mirroring rtk; reason about it and state your choice.
2. A selectable CAO backend that does NOT change today's behaviour by default:
   - Variable `cao_terminal_backend: tmux` (allowed: tmux, herdr), validated with assert.
   - When the optional systemd service is enabled (ai/roles/cao/templates/cao-server.service.j2), pass the backend to cao-server (`--terminal` or `CAO_TERMINAL_BACKEND`). Choose one and justify it. With the default `tmux` the rendered unit should stay byte-identical to today, if possible.
   - Assert that herdr is installed or enabled when `cao_terminal_backend == 'herdr'`.
   - Do not start, stop or restart any service. Keep `cao_restart_on_change` semantics.
3. Document how to switch manually (`cao-server --terminal herdr` / back to tmux). Note that switching requires restarting cao-server with no open sessions, that sessions do not migrate between backends, that you must not run two servers sharing the same CAO home, and that herdr is experimental.

## CONCURRENCY — another developer is editing files in ai/roles/cao right now
Do NOT edit any of these:
- ai/roles/cao/defaults/main.yml
- ai/roles/cao/tasks/mcp.yml
- ai/roles/cao/files/sync_mcps.py
- ai/roles/cao/templates/ai-stack-sync-mcps.j2
- ai/roles/cao/templates/profiles/*
- ai/tests/test_sync_mcps.py
- ai/tests/check_cao_providers.py
- ai/README.md
- ai/vars.example.yml
Instead:
- Put `cao_terminal_backend` and the herdr variables in the new herdr role's defaults or in ai/roles/ai_stack/defaults/main.yml, whichever is cleaner, and justify the choice. You may edit ai/roles/cao/templates/cao-server.service.j2 and ai/roles/cao/tasks/service.yml if needed. Keep those edits minimal.
- Write the README section (Portuguese, matching ai/README.md style, including a row for the components table and the variables table) to /home/andrew/git/ansible-workstation/tasks/herdr-install/README_SECTION.md, and the vars.example.yml snippet to tasks/herdr-install/VARS_SNIPPET.yml. They will be merged after the other task lands.
- You may edit ai/all.yml (add the import only).

## Verification (required, logs saved under tasks/herdr-install/)
- `ansible-playbook ai/herdr.yml --syntax-check` and `ansible-playbook ai/all.yml --syntax-check`.
- `ansible-playbook ai/all.yml --list-tasks --tags herdr`.
- Run the herdr role against an ISOLATED temporary HOME (see tasks/rtk-install/isolated.yml for the pattern used before). Run it twice to prove idempotence. Also do a check-mode run, and test that a bad checksum fails.
- Render cao-server.service.j2 for tmux and for herdr and diff them against the current output.
- If feasible, confirm the installed binary answers the commands herdr_backend.py uses (e.g. `--version`/`--help`), without starting a CAO server against the real home.
- Do NOT apply anything to the real HOME. Do NOT touch the real ~/.local/bin, the CAO settings or the systemd units. No commits.
- Do not read credentials, .env, SSH keys or PEM files. Do not put local paths, usernames or emails in web searches.

## Deliverable
send_message to me in Portuguese with: changed/created files (absolute paths), the official herdr source URLs, the pinned version with its compatibility rationale, verification results with log paths, anything not verified, and any deviation from this spec with the reason.

[Assigned by terminal 97593bc0. When done, send results back to terminal 97593bc0 using send_message]

## Update 1

COORDINATION UPDATE for the herdr task. Append it to /home/andrew/git/ansible-workstation/tasks/herdr-install/SPECIFICATION.md as "Update 1".

Another developer is now renaming the CAO systemd unit from `cao-server-<user>` to `cao-server`, with migration logic. They own ai/roles/cao/tasks/service.yml, ai/roles/cao/tasks/restart-service.yml, ai/roles/cao/defaults/main.yml and ai/README.md.
- Do NOT edit service.yml or restart-service.yml. The only cao-role file you may edit is ai/roles/cao/templates/cao-server.service.j2, and only for the terminal-backend option.
- Put any cao_terminal_backend assert in your own role or entry point. Do not put it in service.yml.
- If you truly need a change in service.yml, describe it in tasks/herdr-install/SERVICE_YML_CHANGE.md and I will merge it.
- Refer to the unit name only via `{{ cao_service_name }}`, whose default will be `cao-server`.
No reply needed; continue.

[Message from terminal 97593bc0. Use send_message MCP tool for any follow-up work.]
