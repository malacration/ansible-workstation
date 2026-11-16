# Review: herdr-pastor (round 1)

- Level: HIGH → reviewer: mala_reviewer_advanced_codex (Codex, cross-model review).
- Spec: /home/satanas/git/ansible-workstation/tasks/herdr-pastor/TASK.md
- Developer report: /home/satanas/git/ansible-workstation/tasks/herdr-pastor/IMPLEMENTATION.md
- Repo: /home/satanas/git/ansible-workstation (uncommitted; do NOT modify any file)

## Scope (only these changes)

New: ai/roles/herdr/templates/herdr-pastor.j2, ai/roles/herdr/tasks/pastor.yml,
ai/tests/test_herdr_pastor.py.
Additions in: ai/roles/herdr/defaults/main.yml, ai/roles/herdr/tasks/main.yml,
ai/roles/herdr/README.md, ai/README.md, ai/vars.example.yml.
Ignore pre-existing unrelated uncommitted changes in ai/roles/cao/*, ai/tests/test_sync_mcps.py
and the cao-related hunks of ai/README.md / ai/vars.example.yml.

## Focus

- Shell correctness/quoting of the POSIX sh script (paths with spaces, $EDITOR with args,
  emoji labels, locale, set -e pitfalls), herdr CLI usage vs spec, session selection (never `cao`
  by default), background server start, attach behaviour, exit codes.
- Ansible: become/user pattern consistent with tasks/install.yml, check mode, removal when
  herdr_pastor_enabled=false, idempotence.
- Tests meaningful; run `python3 -m unittest ai/tests/test_herdr_pastor.py -v` and
  `ansible-playbook ai/herdr.yml --syntax-check` if your tools allow.
- Do NOT start herdr servers or touch user herdr sessions.

## Output

Reply with verdict APPROVED or CHANGES_REQUESTED and a numbered list of findings
(file:line, severity, fix). If you can write files, also save it to
/home/satanas/git/ansible-workstation/tasks/herdr-pastor/REVIEW.md.
