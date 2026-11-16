INTEGRATION TASK (CHANGES_5): merge the herdr work into yours before the consolidated review.

STEP 0: save this message verbatim to /home/andrew/git/ansible-workstation/tasks/tiered-agent-profiles/CHANGES_5.md.

The herdr task (report: /home/andrew/git/ansible-workstation/tasks/herdr-install/REPORT.md, read it fully) is done. It found an integration bug with your preflight:
1) ai/cao-service-preflight.yml is the FIRST import in ai/all.yml and runs as a play WITHOUT the ai_stack role defaults. With cao_service_enabled=true it fails with "'cao_terminal_backend' is undefined" (tasks/herdr-install/logs/preflight-undefined-backend.log).
2) The preflight runs BEFORE ai/herdr.yml, so a "herdr installed" check there would fail on a fresh host even with herdr enabled.

Do the following:
a) Review, then apply, /home/andrew/git/ansible-workstation/tasks/herdr-install/PREFLIGHT_FIX.patch. Full proposed files are in tasks/herdr-install/proposed/b/.
   - In the preflight: use default('tmux'), validate the allowed values, and accept "herdr installed OR herdr_enabled".
   - In service.yml, before writing the unit (and outside check mode): require that the herdr command is installed when cao_terminal_backend == 'herdr'.
   Adapt the patch if your files changed since; keep the intent.
b) De-duplicate `cao_terminal_backend`. You added it to ai/roles/cao/defaults/main.yml; the herdr task added it to ai/roles/ai_stack/defaults/main.yml. Keep exactly ONE definition (the herdr report argues for ai_stack/defaults; verify the play/variable visibility) and make the preflight robust via default('tmux'). Make sure the herdr role (ai/roles/herdr) and the cao role resolve the same value.
c) Merge /home/andrew/git/ansible-workstation/tasks/herdr-install/README_SECTION.md into ai/README.md: the component table row, the variables table rows and the herdr section. Merge tasks/herdr-install/VARS_SNIPPET.yml into ai/vars.example.yml. Keep the Portuguese style and remove duplicates.
d) Add a test, or extend test_cao_service_migration.py, covering:
   - the preflight with cao_service_enabled=true and the backend undefined (default tmux works);
   - backend herdr with herdr_enabled=false (fails);
   - backend herdr with herdr_enabled=true on a fresh host (the preflight passes);
   - an invalid value (fails).
e) Do NOT modify ai/roles/herdr/* or cao-server.service.j2 unless strictly needed for the integration; if you do, explain why.
f) Re-run and save logs with the suffix -4: the full unit suite; syntax-checks for ai/mcp.yml, ai/all.yml, ai/cao-service.yml and ai/herdr.yml; the isolated role runs; and `ansible-playbook ai/all.yml --list-tasks`.

Same constraints: no real HOME, no real /etc/systemd, no services touched, no commits.
Reply via send_message (Portuguese) with the files changed, results with log paths, and any deviations.

[Message from terminal 97593bc0. Use send_message MCP tool for any follow-up work.]

## Correction 1

CORRECTION to CHANGES_5. Append it to tasks/tiered-agent-profiles/CHANGES_5.md as "Correction 1". It overrides item (a).

The herdr developer reworked their side. /home/andrew/git/ansible-workstation/tasks/herdr-install/PREFLIGHT_FIX.patch is OBSOLETE: it was moved to tasks/herdr-install/obsolete/. Do NOT apply it.

The new design:
- The herdr backend assertions live in ai/roles/herdr/tasks/backend.yml, run through a new entry point ai/cao-terminal-backend.yml.
- ai/all.yml imports that entry point after herdr.yml and right before cao-service.yml.
- cao-server.service.j2 uses `cao_terminal_backend | default('tmux')`.

What you must do instead, following /home/andrew/git/ansible-workstation/tasks/herdr-install/SERVICE_YML_CHANGE.md (read it):
1. REMOVE the 3 backend-related tasks from ai/roles/cao/tasks/service.yml that were copied from the herdr first version. Your service-preflight.yml must NOT validate the terminal backend; the herdr entry point owns that. If you already applied the obsolete patch, revert those parts.
2. Optionally import ai/cao-terminal-backend.yml in ai/cao-service.yml so a standalone service run validates the backend too. Do it if it keeps ai/all.yml from running it twice (check tags and ordering), and justify the choice.
3. Keep exactly ONE definition of cao_terminal_backend (default tmux), in ai_stack/defaults; remove it from cao/defaults. Verify the visibility in every play that uses it: the herdr play, cao-terminal-backend.yml, cao-service.yml and the preflight, if it still references it at all.
4. Items (b) through (f) of CHANGES_5 still apply. Use the UPDATED tasks/herdr-install/README_SECTION.md. In (d), test the backend scenarios through the new entry point and your preflight's independence from the backend, not the obsolete patch.
Do not edit ai/roles/herdr/* or cao-server.service.j2.

[Message from terminal 97593bc0. Use send_message MCP tool for any follow-up work.]
