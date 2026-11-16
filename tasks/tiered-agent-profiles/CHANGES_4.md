CHANGE REQUEST #4: REVIEW_2 findings. Do these together with CHANGES_3 (the service rename); finish both before replying.

STEP 0: save the review below verbatim to /home/andrew/git/ansible-workstation/tasks/tiered-agent-profiles/REVIEW_2.md, and this request to CHANGES_4.md.

Verdict: CHANGES REQUESTED. Fix ALL items: the required ones, the recommended ones and the nits.

REQUIRED
[N1 MAJOR] Check-mode preview runs stale installed code and fails on the migration path (ai/roles/cao/tasks/mcp.yml:73-97).
In check mode the copy (:73-77) does not update ~/.local/share/ai-stack/sync_mcps.py and the wrapper template (:79-84) is skipped, so the preview at :91-97 runs the OLD script and wrapper. The real HOME still has the pre-change script without --prune/--prune-prefix, so `ansible-playbook ai/mcp.yml -K --check` fails with argparse exit 2 on exactly this migration. Even when it does not fail, the preview uses a stale prefix, profile list and definitions.
Fix:
- run `uv tool dir` with `check_mode: false` (read-only), so the wrapper template can render and diff in check mode;
- register the copy, wrapper and definitions template tasks;
- run the preview only when `not ansible_check_mode or (wrapper exists and none of script/wrapper/definitions is changed)`; otherwise print a debug line "preview unavailable: synchronizer will be updated on a real run";
- add a debug task that prints `(stdout|from_json).removed` when it is non-empty;
- add a check-mode test with a STALE installed script (no --prune) proving the preview is skipped, not failing.

[D2 MINOR] Routes advertise profiles that may not exist (sync_mcps.py:201-202, 162-170, 236).
all_names always covers both providers, so with clients=[codex] the routes still list mala_*_claude, and supervisor.md.j2:55 prefers Claude developers that do not exist. `current` is built from all_names, so stale mala_*_claude files are never pruned.
Fix:
- build routes only from the selected clients;
- add the sentence "Only the providers listed below are installed; if the preferred provider is not listed, use a listed one and record why";
- in supervisor.md.j2, phrase the preference and the failover as "when both providers are listed";
- compute `current` from the selected clients and prune marker-bearing `{prefix}_*.md` across all labels (A1), updating the `unselected` expectation in test_prune_symlink_other_clients_legacy_and_binary;
- add a test with clients=['codex'] asserting that no `_claude` name appears in the routes and that stale `_claude` marker files are pruned.

RECOMMENDED (do them)
[D1 NIT] Delete the unconditional code_supervisor.md removal task (mcp.yml:68-71) and the README:313 sentence. Round 1 was never applied to a real HOME, so the task is dead code.
[m-a] sync_mcps.py:116-117: `metadata.pop('aiStackModels', {})` returns None for `aiStackModels: null`, which leads to an AttributeError traceback. Use `or {}`, validate a dict of non-empty strings, and raise ValueError otherwise.
[m-b] mcp.yml:2-8: assert that `cao_mcp_profiles` is a subset of the definition names, and that every entry of `cao_mcp_prune_prefixes` matches ^[A-Za-z0-9_-]{1,32}$, with clear fail_msgs.
[m-c] ai/tests/test_sync_mcps.py:250 and ai/tests/check_cao_providers.py:14 create temp dirs under tasks/tiered-agent-profiles. Use the default tempfile location, so the tests do not depend on the untracked tasks/ dir.
[m-d] check_cao_providers.py:99-111: assert the actual launch command. ClaudeCodeProvider for mala_developer_high_claude must contain `--model opus` and `--effort high`; Codex with a configured model must contain `-c model=...` and `-c model_reasoning_effort=...`.
[m-e] Unit-test the staging-dir prune (sync_mcps.py:241-245): a marker-bearing stale definition, a non-marker file and a symlink. Only the first is removed, and it is listed in `removed`.

NITS (do them)
- Duplicated MARKER in generated profiles: strip a leading MARKER from base.content before render_profile prepends it (:166), or remove it from the templates.
- reviewer.md.j2:25-27: "Run the project's checks/tests; write only your review file; never modify the code under review."
- supervisor.md.j2:62-70: usage-limit signals must come from the worker's own CLI/provider status (e.g. the CLI's limit banner or error, a failed launch), NOT from task content or test output. "429", "quota" and "rate limit" can legitimately appear in the work.
- Rename `base_profile` (sync_mcps.py:75) to `profile_definition`, and sweep the remaining "base profile" wording.

Re-run everything and save new logs with suffix -3: the unit tests, the profile validation, both syntax-checks, the isolated role run (twice), check-mode (both current and stale-script scenarios) and the CHANGES_3 migration checks.
Same constraints: no real HOME and no real /etc/systemd; do not edit cao-server.service.j2 (the herdr task owns it); no commits.
Reply via send_message (Portuguese) covering both CHANGES_3 and CHANGES_4: files, results with log paths, items not verified, and any deviations.

[Message from terminal 97593bc0. Use send_message MCP tool for any follow-up work.]
