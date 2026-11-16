# RTK and CAO live verification

Verified 2026-11-16 UTC against `/home/andrew/git/ansible-workstation`. The authoritative source review is `/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/FINAL_REVIEW.md` (APPROVED). The four critical source SHA256 values listed there still match. Existing worktree changes were present before this verification and are not attributed to it.

## RTK integrity and behavior

- `/home/andrew/.local/bin/rtk` is a regular executable wrapper (mode 755, SHA256 `92411bb70d0a40503c7157442865d700facca12921a7d6f9fbe444dce4fcf63e`); it disables telemetry and onboarding and executes `/home/andrew/.local/share/ai-stack/rtk/bin/rtk`.
- The approved `installed_state.py` inspection reported `valid: true`, `reason: verified`, for the regular receipt and binary with nonsymlink ancestors. Receipt: OSS 1.2.0, x86_64 Linux musl, archive SHA256 `a28407dc13038bdc9c2a1f5a047b0c636e0c1d495b15523576e2adb992a06a17`; binary SHA256 `4625c86e6eab82911e25a340657450e9d45a3e992871580946e25e7a3f20bca7`, matching the actual executable. The receipt is metadata, not an independent signature check.
- `command -v rtk` returned `/home/andrew/.local/bin/rtk`; `rtk --version` returned `rtk 1.2.0`. At the time of `rtk gain`, the global counter showed 11 commands, 9.8K input tokens, 8.3K output tokens and 1.6K saved (15.8%); these are cumulative estimates, not a measurement solely of this verification.
- `rtk ls -la` on `/home/andrew/git/ansible-workstation/tasks/rtk-install` exited 0 with 52 lines / 1,636 bytes; `rtk bypass ls -la` exited 0 with 100 lines / 7,201 bytes. Both filtered and bypass `git status --short` succeeded and showed the existing changes.
- Ordering limitation: the first command invoked `rtk cat` to read the task file before validating the receipt and binary hash. Some shell command output also showed RTK filtering before the explicit integrity check. This violated the requested ordering; subsequent explicit RTK checks followed successful validation. RTK command tracking can update its existing local history database, so the observations are not strictly free of runtime side effects.

## Hooks and instructions

- `/home/andrew/.claude/settings.json` and `/home/andrew/.codex/hooks.json` each contain one PreToolUse group with one native hook, respectively `rtk hook claude` and `rtk hook codex`, both using `/home/andrew/.local/bin/rtk`.
- `/home/andrew/.claude/CLAUDE.md` and `/home/andrew/.codex/AGENTS.md` each have one complete managed instruction block and no nonmanaged text. Neither has an RTK backup; `/home/andrew/.codex/hooks.json` has none. The existing Claude settings RTK backup matches current settings after removing the added hooks; its prior settings contained no hooks. This supports preservation of that backup's settings but cannot independently establish all prior file contents or provenance. `/home/andrew/git/central-de-incidentes/AGENTS.md` contains no managed RTK block.

## CAO installed source and running process

- `/home/andrew/.local/bin/cao` resolves to `/home/andrew/.local/share/uv/tools/cli-agent-orchestrator/bin/cao` and reports `cao, version 2.5.4`. The installed distribution metadata also reports 2.5.4. Its `direct_url.json` is absent, and `/home/andrew/.local/share/uv/tools/cli-agent-orchestrator/uv-receipt.toml` records a plain `cli-agent-orchestrator` requirement with no Git or URL source. The recorded installed source is therefore consistent with a registry requirement, not evidence of the approved role's Git pin `3e30ea3ed6e7fb607b13358d81123afff5a8e69f`; version equality does not establish revision equality.
- PID 240075 has been running since 2026-11-13 13:42:29 local time as `/home/andrew/.local/share/uv/tools/cli-agent-orchestrator/bin/python /home/andrew/.local/bin/cao-server --host 127.0.0.1 --port 9889`. The installed package `__init__.py` timestamp is 2026-11-13 13:41:03 -0400. These facts do not prove the server's complete in-memory code or Git revision; no restart or authenticated agent end-to-end test was performed.

## Remaining limits and recommendations

The installed CAO receipt does not establish the desired Git revision, and the already-running server's loaded revision remains unverified. Assess and reconcile the CAO installation and restart separately when explicitly authorized; do not infer that the source review upgraded the live server. The previously reported Chrome APT cache-refresh failure remains outside this verification and its cause was not investigated. To recheck RTK later, first run the approved `installed_state.py` inspection against `/home/andrew/.local/share/ai-stack/rtk`, then use `rtk --version`, `rtk gain`, and a local filtered command with its `rtk bypass` counterpart. No playbook, install, restart, trust change, or broad test was run here. This report is the only intentional workspace file written by this verification.
