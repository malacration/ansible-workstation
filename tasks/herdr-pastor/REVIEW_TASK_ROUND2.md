# Review: herdr-pastor (round 2)

- Level: HIGH → reviewer: mala_reviewer_advanced_codex (same terminal b6a13d4f as round 1).
- Round 1 findings: /tmp/herdr-pastor-review-20261116.md
- Fix spec: /home/satanas/git/ansible-workstation/tasks/herdr-pastor/FIX_ROUND1.md
- Developer report: /home/satanas/git/ansible-workstation/tasks/herdr-pastor/IMPLEMENTATION.md
  (section "Round 1 fixes")
- Repo: /home/satanas/git/ansible-workstation (uncommitted; do NOT modify any file)

## Verify

1. Unexpected herdr failures (workspace create, splits, renames, editor start, agent start,
   pane run fallback, final focus) now exit 1 with a stderr message and no attach; the
   half-built workspace is left with a printed close command. Soft cases stay soft: sheep not on
   PATH, `agent start` exit 2 → pane run, `agent_not_ready`, and `timeout` (developer kept it
   as a warning — judge whether that is correct per `herdr agent start --help`).
2. Duplicate sheep (`[claude, claude]`) get unique names (`claude-wN`, `claude-2-wN`) and labels.
3. Tests: `python3 -m unittest ai/tests/test_herdr_pastor.py -v` (expect 13 OK) and
   `ansible-playbook ai/herdr.yml --syntax-check`.
4. Any regressions or new issues in the same files (ai/roles/herdr/templates/herdr-pastor.j2,
   ai/tests/test_herdr_pastor.py, herdr-pastor sections of ai/roles/herdr/README.md and
   ai/README.md). Ignore unrelated cao changes and ~/.config/herdr/local-plugins.

Do not start herdr servers or touch user herdr sessions.

## Output

Reply with APPROVED or CHANGES_REQUESTED and numbered findings (file:line, severity, fix).
