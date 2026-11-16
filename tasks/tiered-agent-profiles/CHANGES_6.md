CHANGE REQUEST #6: consolidated REVIEW_3 findings that you own ([A] and [A+B]).

STEP 0: save the full review text below to /home/andrew/git/ansible-workstation/tasks/tiered-agent-profiles/REVIEW_3.md, and this request to CHANGES_6.md.

Verdict was CHANGES REQUESTED. Fix ALL of these.

[MAJOR] A-1: the migration can kill its own ansible run (service.yml:19-27, restart-service.yml).
With the tmux backend, the tmux server started by cao-server lives in the unit's cgroup. `systemctl stop` kills every pane, including an ansible-playbook launched from a CAO session. With cao_restart_on_change=true the play dies after "Parar e desabilitar" and leaves the host with NO CAO server (the legacy unit is disabled, its file is still present, and the new unit is not installed).
Fix:
- In service-preflight.yml, before any change, FAIL when the run is inside a CAO session (`ansible_facts['env']['CAO_TERMINAL_ID'] is defined`, gathered as the invoking user) AND (an active legacy unit would be stopped OR cao_restart_on_change would restart cao_service_name). Message in Portuguese: "execute fora de uma sessão CAO (terminal comum ou SSH)".
- Also add a check for the TMUX env + cao-server parentage, if it is cheap.
- Add the same warning before the manual commands at README:499-507, because `systemctl disable --now` also kills the shell running it.
- Test it.

[MAJOR] A-2: the standalone service run never checks that herdr is installed (ai/cao-service.yml:1-15, README:215-218, 228-233).
Fix:
- Import ai/cao-terminal-backend.yml at the top of ai/cao-service.yml, after the preflight import and before the service play.
- Remove the separate import at ai/all.yml:50-52, so it runs exactly once. If `--tags herdr` must still validate, tag the import in cao-service.yml [cao_service, herdr].
- Update README:225-233.
- Test it: standalone cao-service.yml with backend=herdr and herdr missing must fail before any unit change; a typo such as `herdrr` must fail, not silently render tmux.
Coordinate: do NOT edit ai/roles/herdr/* or ai/cao-terminal-backend.yml (owned by the herdr developer). If the typo must be rejected inside backend.yml and it is not, tell me.

[MINOR] A-3: check mode on a fresh host fails at mcp.yml:49-54, because `uv tool dir` runs with check_mode:false and uv may not exist yet.
Fix: stat `{{ ai_stack_bin_dir }}/uv` first, or use failed_when:false. When uv is unavailable, skip the wrapper template and the preview and emit the "preview unavailable" debug. Test it.

[MINOR] A-5: the preflight's set_facts (ai/cao-service-preflight.yml:8-50) leak into later plays and shadow role defaults.
Fix: replace them with `roles: [{role: cao, when: false}]`, as in herdr.yml, and keep the getent task.

[MINOR] A-6: the real-mode migration order is untested (test_cao_service_migration.py:65-73).
Fix: add a check=False test using the fake systemctl audit, asserting the order: stop/disable legacy → legacy file removed → daemon-reload → new unit written → enable/start cao-server.

[MINOR] A-7: test_cao_service_migration.py:15-21 creates temp dirs under tasks/tiered-agent-profiles.
Fix: use the default tempfile location.

[NIT] Double start on migration (service.yml:65-80 plus the handler).
Fix: skip the restart handler when the legacy unit was just removed, so the new unit is not started and then immediately restarted.

[NIT] README wording:
- README:228-229 has a duplicated lead-in;
- README:496 should read "também é executada no início de `ai/all.yml`";
- README:237 is an over-long line.

[A-4, required] The logs did not certify the tree, because the files changed during the review.
FREEZE PROTOCOL:
- The herdr developer is fixing B-1 in ai/roles/herdr/* in parallel and will create /home/andrew/git/ansible-workstation/tasks/herdr-install/B3_DONE when finished.
- After YOUR fixes are complete, wait until that file exists, polling at most every 60s. Then make NO further edits and produce a fresh -5 log set in tasks/tiered-agent-profiles/:
  - full unit suite (unittest-5.log);
  - syntax-checks for mcp/all/cao-service/herdr/cao-terminal-backend;
  - list-tasks;
  - a TRUE first isolated run in an empty HOME plus a second run, for both the MCP sync and herdr;
  - check mode on a fresh HOME (A-3);
  - visibility logs that print `debug: var=cao_terminal_backend` in each play (herdr, cao-terminal-backend, cao-service). Put the debug in a temporary test-only playbook, not in the shipped playbooks.
- Include in your reply a `git status --porcelain -- ai/` plus `sha256sum` of every changed file, taken right after the logs, so the reviewer can confirm the frozen state.

Same constraints: no real HOME, no real /etc/systemd, no services touched, no commits.
Reply via send_message (Portuguese) with the files changed, the -5 log paths and any deviations.

--- REVIEW_3 FULL TEXT (save verbatim to REVIEW_3.md) ---
CONSOLIDATED REVIEW (round 3): CHANGES REQUESTED. Caveat: the tree changed during the review.
[MAJOR][A] A-1 as above. [MAJOR][A+B] A-2 as above. [MINOR][A] A-3, A-4, A-5, A-6, A-7 as above.
[MINOR][B] B-1: ai/roles/herdr/tasks/release.yml:109-115 `backup: true` leaves a binary copy per upgrade or reconcile, and the cache keeps every version. Keep at most one backup, or delete it after successful revalidation, and prune cache versions other than the resolved one.
[NIT][A] Double start on migration; README wording at 228-229, 496 and 237.
[NIT][B] Unauthenticated GitHub API is limited to 60/h; acceptable. installed_state.py:31-40 rejects symlinked ancestors such as /home → /var/home; document it in roles/herdr/README.md.
VERIFIED OK: REVIEW_2 resolved (N1, D2, D1, m-a..m-e, nits); service rename and migration semantics; single cao_terminal_backend definition and visibility; herdr trust chain fail-closed, idempotent, check mode only predicts; security OK.
Required for approval: A-1, A-2, A-4 (fresh frozen logs). Recommended: A-3, A-5..A-7, B-1.

[Message from terminal 97593bc0. Use send_message MCP tool for any follow-up work.]

## Amendment 1

AMENDMENT to CHANGES_6, from the reviewer's follow-up. Append it to CHANGES_6.md.

A-2 precise fix (it overrides my earlier wording):
1. In ai/cao-service.yml, add as the FIRST import, BEFORE the preflight:
   - name: Validar backend de terminal do CAO
     ansible.builtin.import_playbook: cao-terminal-backend.yml
     tags: [herdr]
2. Delete the separate import at ai/all.yml:50-52. Tags accumulate through nested imports: inside all.yml the cao-service import already carries cao_service, so `--tags herdr` and `--tags cao_service` both still select the validation, which runs exactly once and still comes after herdr.yml.
   Verify with `ansible-playbook ai/all.yml --list-tasks --tags herdr` and `--tags cao_service`, and log both.
3. README:225-233: the separate validation command becomes optional; drop the duplicated lead-in at README:228-229.
4. Test: run the real ai/cao-service.yml in an isolated HOME with cao_service_enabled=true, cao_terminal_backend=herdr, no herdr binary, in real mode with fake systemctl. It must fail BEFORE any unit is written. Also test `herdrr` → fail.
Do not use the set_fact guard-variable alternative.
Everything else in CHANGES_6 is unchanged, including A-1, which is still required, and the freeze protocol that waits for tasks/herdr-install/B3_DONE.

[Message from terminal 97593bc0. Use send_message MCP tool for any follow-up work.]
