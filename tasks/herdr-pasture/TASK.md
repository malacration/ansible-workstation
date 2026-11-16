# Task: herdr "Pasture" plugin (local only) — agents as sheep

- Level: HIGH — new UI plugin against an unfamiliar plugin API (herdr 0.9.5 plugins);
  MEDIUM raised one level for unfamiliar territory.
- Developer: mala_developer_high_claude (Claude, preferred for development) — reusing
  terminal 5767df2f, which already explored the herdr CLI for the superseded herdr-pastor task.
- Reviewer: mala_reviewer_advanced_codex (Codex, cross-model; HIGH level).
- Supersedes: /home/satanas/git/ansible-workstation/tasks/herdr-pastor/TASK.md (cancelled by the user).

## Goal

Recreate locally the "Pasture" idea the user saw on herdr's site (screenshot:
/tmp/claude-1001/-home-satanas-git-ansible-workstation/69ea8815-242f-4464-a231-1cd97cfc799a/images/1.png):
a herdr plugin pane where each detected agent is drawn as a sheep in a pasture.

- Header: "The pasture", subtitle "N sheep, one happy herd.", counters at the top right:
  "X wandering" (working), "Y need you" (blocked), "Z resting" (idle/done). Unknown → resting.
- Sheep: one per agent (`herdr agent list` / API), labelled with the pane/agent name (or the
  tab label), a small badge for the agent kind (claude/codex/…). Resting sheep show `zzz`;
  working sheep wander (simple animation, low CPU, e.g. ≤4 fps or only on events);
  blocked sheep show a `(!) <Agent>` speech balloon.
- A wooden sign on the left with the current workspace label ("WELCOME TO / <workspace>").
  If several workspaces have agents, group by workspace or let the user cycle with Tab.
- Fence across the screen; below it "THE WORKSHED": breadcrumb `<workspace> / <sheep name>` and
  a framed box with the agent kind + state and the last lines of the selected agent's output
  (`herdr agent read <target> --source recent --lines N`).
- Keys: arrows/hjkl select a sheep, Enter focuses that agent (`herdr agent focus`), q/Esc closes.
  Mouse click to select if the plugin API makes it easy.
- Render with Unicode text + 24-bit colors (sky, hills, fence) — it must work in a normal
  terminal. Kitty graphics are optional; do not depend on them.

## Where it lives (user choice: local only, NOT in the repo/Ansible)

- Plugin source: `/home/satanas/.config/herdr/local-plugins/pasture/` (manifest
  `herdr-plugin.toml` + entrypoint). Do not add files to the ansible-workstation repo except
  the reports under this tasks/ dir.
- Register it with `herdr plugin link <path>`; open it with
  `herdr plugin pane open --plugin <id> --entrypoint <id> --placement zoomed` (or tab). If the
  manifest supports a keybinding/action, add one and document it.
- Implementation language: whatever the herdr 0.9.5 plugin runtime supports best and is
  already available on the machine (python3 or POSIX sh preferred; no new system packages,
  no network installs). Determine the manifest format and runtime contract from the installed
  binary only: `herdr plugin --help`, `herdr api schema`, the plugin error messages. Do not
  fetch URLs.

## Constraints

- Do not modify `~/.config/herdr/config.toml` unless strictly required for a keybinding; if so,
  show the exact diff in the report.
- Do not disturb running herdr sessions (default and `cao`); test in a throwaway session
  (e.g. `herdr --session pasture-dev …`) and stop/delete it afterwards.
- Do not read secrets (~/.ssh, ~/.aws, .env, *.pem). Do not commit anything.
- Include a small automated check (e.g. unit tests for the state→counter/sheep mapping and
  layout math, runnable with `python3 -m unittest` from the plugin dir) and a headless
  verification: open the plugin pane in the throwaway session and capture it with
  `herdr pane read <id> --format text` to prove it renders.

## Reporting

Write `/home/satanas/git/ansible-workstation/tasks/herdr-pasture/IMPLEMENTATION.md`: files
created, manifest/runtime contract discovered (commands + observed output), how to open it,
test command + result, the captured render. Then report back.

## Log

- 2026-11-16: created after the user picked "Pasture, local only"; herdr-pastor cancelled.
- 2026-11-16: user later chose to KEEP herdr-pastor (review round 1 sent to Codex, terminal b6a13d4f).
- 2026-11-16: supervisor hit usage limit; worker 5767df2f told to save progress in
  IMPLEMENTATION.md and pause. Resume from there; not reviewed yet.
- 2026-11-16: Claude limit reset; worker 5767df2f told to resume pasture (same provider, limit
  was temporary). Review of herdr-pastor resent to b6a13d4f (first message was not picked up).
- 2026-11-16: pasture done by 5767df2f (18 tests OK, headless render verified in throwaway
  session). Review round 1 sent to a new mala_reviewer_advanced_codex terminal (REVIEW_TASK.md).
- 2026-11-16: round 1 CHANGES_REQUESTED by d7aeeccf (1 HIGH escape-injection, 3 MEDIUM).
  Fixes sent to 5767df2f per FIX_ROUND1.md.
- 2026-11-16: fixes done (32 tests OK). Review round 2 sent to d7aeeccf (REVIEW_TASK_ROUND2.md).
- 2026-11-16: APPROVED in round 2 (/tmp/herdr-pasture-review-round2-33107b13.md).
  Terminals d7aeeccf and 5767df2f deleted. Task complete.
