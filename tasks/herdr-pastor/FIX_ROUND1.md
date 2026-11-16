# Fix round 1: herdr-pastor (review CHANGES_REQUESTED)

- Level: HIGH (unchanged; 1st rejection). Developer: mala_developer_high_claude (new terminal,
  because 5767df2f is busy with tasks/herdr-pasture). Reviewer next: mala_reviewer_advanced_codex.
- Spec: /home/satanas/git/ansible-workstation/tasks/herdr-pastor/TASK.md
- Previous report: /home/satanas/git/ansible-workstation/tasks/herdr-pastor/IMPLEMENTATION.md
- Full review: /tmp/herdr-pastor-review-20261116.md (copied summary below)

## Findings to fix

1. `ai/roles/herdr/templates/herdr-pastor.j2:142` (P2): failures of `pane split`, starting the
   editor, and `agent start` are ignored; the script exits 0 and says the workspace is ready.
   Propagate unexpected failures (non-zero exit, clear stderr message). Keep the documented
   intended soft cases: missing sheep binary on PATH → warning/skip; `agent start` exit 2
   (unsupported kind) → fallback to `pane run`; `agent_not_ready` → warning. Add tests for the
   error paths (fake herdr returning failures).
2. Same file `:152` (P2): config `[claude, claude]` makes both sheep use the same agent name
   (`claude-wN`) → name collision. Give each sheep a unique name (e.g. include the sheep index)
   or reject duplicates in the role/script; add a test.

## Constraints

- Only touch herdr-pastor files: ai/roles/herdr/templates/herdr-pastor.j2,
  ai/roles/herdr/tasks/pastor.yml, ai/tests/test_herdr_pastor.py, and the herdr-pastor
  sections of the READMEs/defaults if behaviour docs change. Do not touch
  ~/.config/herdr/local-plugins/ (another worker is building the pasture plugin there),
  ai/roles/cao/*, or unrelated uncommitted hunks. Do not commit.
- Do not start herdr servers or touch real herdr sessions; fake herdr in tests is enough.

## Reporting

Append a "Round 1 fixes" section to IMPLEMENTATION.md (changes + test command/result:
`python3 -m unittest ai/tests/test_herdr_pastor.py -v` and
`ansible-playbook ai/herdr.yml --syntax-check`), then report back.
