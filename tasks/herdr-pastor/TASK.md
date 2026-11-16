# Task: herdr-pastor — $EDITOR as the "shepherd" pane with agent "sheep" around it

- Level: HIGH — new feature with a clear spec, but it spans 4+ files (template, role tasks/defaults, tests, README); MEDIUM raised one level for 3+ files.
- Developer: mala_developer_high_claude (provider: Claude, preferred for development)
- Reviewer: mala_reviewer_advanced_codex (provider: Codex, cross-model review; HIGH level)
- Repo: /home/satanas/git/ansible-workstation
- Language: code/comments may follow repo style; user-facing docs (README, task names, messages) in Portuguese, like the rest of `ai/`.

## Goal (user request)

The user wants their editor to be the "shepherd" (pastor) in herdr, with AI agents as "sheep"
around it. Chosen layout:

```
┌──────────────────┬──────────┐
│                  │ 🐑 claude│
│  🧑‍🌾 pastor        ├──────────┤
│  ($EDITOR)       │ 🐑 codex │
└──────────────────┴──────────┘
```

## Deliverable

1. A command `herdr-pastor [DIR]` installed by the existing `herdr` role
   (`ai/roles/herdr/`) into `{{ ai_stack_bin_dir }}/herdr-pastor` (mode 0755), as a template
   (e.g. `ai/roles/herdr/templates/herdr-pastor.j2`), POSIX sh or bash.
   - Creates a new herdr workspace with cwd = DIR (default: `$PWD`), label `🧑‍🌾 pastor`
     (or `🧑‍🌾 <basename DIR>` — pick one and document it), focused.
   - Main (left) pane: renamed `🧑‍🌾 pastor`, runs `${VISUAL:-${EDITOR:-vi}}` in DIR.
   - Splits right (editor keeps the larger share, e.g. ratio ~0.35 for the right column)
     for the first sheep, then splits that pane down for the next sheep(s).
   - Each sheep pane is renamed `🐑 <agent>` and starts the agent. Prefer
     `herdr agent start <name> --kind <kind> --pane <id>` if it works for claude/codex in
     0.9.5; otherwise `herdr pane run <id> <cmd>`. Verify which is correct.
   - Sheep list comes from a role var, default `herdr_pastor_sheep: [claude, codex]`
     (rendered into the template). A sheep whose command is not on PATH is skipped with a
     warning to stderr, not a failure.
   - Focus returns to the editor pane at the end.
   - Options: `--session NAME` (passes herdr's `--session`), `-h/--help`.
   - If no herdr server is running for that session, start/handle it the way herdr expects
     (check `herdr status`), and when not already inside herdr (`HERDR_PANE_ID` unset),
     attach to the session at the end so the user lands in the layout.
   - Must NOT use the CAO session `cao` by default and must NOT touch `~/.config/herdr`
     (role principle: the role never starts a herdr server or edits herdr config at install time).
2. Role wiring: `herdr_pastor_enabled: true` and `herdr_pastor_sheep` in
   `ai/roles/herdr/defaults/main.yml`; install task in the role (respect `ai_stack_user`
   become pattern used in `tasks/install.yml`, check mode friendly); removed (state absent)
   when `herdr_pastor_enabled=false`. Mirror the vars (commented) in `ai/vars.example.yml`.
3. Docs: short section in `ai/roles/herdr/README.md` and `ai/README.md` (Portuguese) with usage.
4. Tests in `ai/tests/` following the existing unittest style: render/run the script against a
   fake `herdr` executable on PATH that records argv and returns plausible ids/JSON, asserting
   the command sequence (workspace create, renames, splits, runs, final focus), the skip of a
   missing sheep, and `--session` propagation. Also an ansible `--syntax-check` /
   `--check` level test if the existing tests do that for the role.

## Constraints

- Verify real CLI output formats against the installed binary
  `/home/satanas/.local/share/ai-stack/herdr/bin/herdr` (v0.9.5): use `--help`,
  `herdr api schema`, and if needed a throwaway session (e.g. `--session pastor-dev-test`)
  that you stop/delete afterwards. Never disturb the user's existing sessions (default and `cao`).
- The working tree already has unrelated uncommitted changes in `ai/README.md`,
  `ai/roles/cao/*`, `ai/tests/test_sync_mcps.py`, `ai/vars.example.yml`. Do not revert or
  reformat them; only add your edits. Do not commit.
- Do not read secrets (~/.ssh, ~/.aws, .env, *.pem).

## Reporting

Write a summary to `/home/satanas/git/ansible-workstation/tasks/herdr-pastor/IMPLEMENTATION.md`:
files changed, how the herdr CLI behavior was verified (commands + observed output), test
command and its result. Then report back.

## Log

- 2026-11-16: created by supervisor; delegated to mala_developer_high_claude.
- 2026-11-16: user says upstream page shows a ready-made layout; worker told to prefer
  `layout.apply` / official plugin if it fits, over manual split/run.
- 2026-11-16: CANCELLED — user wanted the herdr "Pasture" view instead; see
  /home/satanas/git/ansible-workstation/tasks/herdr-pasture/TASK.md. Worker told to revert
  only its own herdr-pastor edits.
- 2026-11-16: worker had already finished (10 tests OK, syntax-check OK) before the cancel
  arrived. Revert put ON HOLD pending user decision; not reviewed yet.
- 2026-11-16: user chose to keep it. Review round 1 (Codex b6a13d4f): CHANGES_REQUESTED
  (2× P2). Fixes delegated per FIX_ROUND1.md to a new mala_developer_high_claude terminal.
- 2026-11-16: fixes done by 66cd2d67 (13 tests OK, syntax-check OK). Review round 2 sent
  to b6a13d4f (REVIEW_TASK_ROUND2.md).
- 2026-11-16: APPROVED in round 2 (report /tmp/herdr-pastor-review-round2-20261116.md).
  Terminals b6a13d4f and 66cd2d67 deleted. Uncommitted; awaiting user to commit/apply.
