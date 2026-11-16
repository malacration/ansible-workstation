# CAO herdr-core backend integration

Date: 2026-11-16

Integrated awslabs/cli-agent-orchestrator PR #1356, head
`9224f3e04310cc251a8e242f15e2467b87fc56ea`, into the existing fork branch
`malacration/cli-agent-orchestrator:profile-env-sync-main`.

Published merge: `ab50597f0caddf8efb30a466cb1fe02a1c9809b0`.
Its parents are the prior fork head `17ffbce6f03737756990d6840126ed21da297fcb`
and the original PR head. Upstream history is preserved.

The PR's backend lacked the `trusted_env` arguments already required by this
fork's terminal service. Added profile-env forwarding to both public creation
methods and reused the shared env merge, value-cap and runtime-identity helpers.
Regression tests cover separate Claude accounts, literal values, profile
precedence, cross-terminal isolation, invalid names/oversized values and
runtime-owned identities.

Ansible changes:

- Pin the published merge in role defaults and the variable example.
- Accept `cao_terminal_backend=herdr-app` and render its service argument.
- Require executable `herdr_core_binary` (default `~/.local/bin/hc`) at version
  0.1.21 or later before service changes. Probe only `--version`, including in
  check mode; no session starts. The existing desktop application supplies this
  dependency. The legacy `herdr` role still installs only the TUI.
- Document the dedicated core session and app machine connection.
- Keep backend `tmux` and automatic restart disabled by default.

Validation:

- 711 CAO tests passed: backends, RPC, inbox, config, API wiring/endpoints,
  shared environment policy and session-env behavior.
- The sandbox rejects socketpair sends (`EPERM`), preventing normal asyncio
  thread wakeups. Tests used a temporary external runner bounding selector
  waits to 1 ms. Product scheduling and source code were not changed for this.
- Upstream migration script `--self-test` passed.
- Ruff over `src/` and `test/`, Black/isort on integration edits and
  `git diff --check` passed.
- The required mypy ratchet was run. Missing local optional packages/stubs
  keep it red relative to the committed baseline. A separate archive of the
  original fork head produced the identical 117 errors in the same environment:
  no new per-file/error-code counts. The baseline was not changed.
- 10 backend entrypoint tests and 12 isolated systemd migration tests passed.
- Backend and service playbook syntax checks passed.
- Real-host backend preflight in check mode passed with `changed=0` and the
  installed `hc 0.1.21`.
- Live core execution and graphical rendering were not validated because the
  sandbox blocks the user's sockets and display.

No installed CAO package, running service, live session, app machine entry,
agent template or mala-agent definition was changed by this integration.
The Ansible worktree remains uncommitted so the user's concurrent agent edits
are not included in a commit.
