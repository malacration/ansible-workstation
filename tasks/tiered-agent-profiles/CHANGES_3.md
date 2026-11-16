CHANGE REQUEST #3: rename the CAO systemd unit. This is in addition to the pending re-review of CHANGES_2; the reviewer will see both.

STEP 0: save this message verbatim to /home/andrew/git/ansible-workstation/tasks/tiered-agent-profiles/CHANGES_3.md.

User request: the service must be named `cao-server`, not `cao-server-<user>`. Today ai/roles/cao/defaults/main.yml:24 has `cao_service_name: "cao-server-{{ ai_stack_user }}"`. The host ALREADY has /etc/systemd/system/cao-server-andrew.service installed by this role, and it may be running the CAO server that this very orchestration session uses.

Requirements:
1. Default `cao_service_name: cao-server`. It stays overridable.
2. Safe migration from the legacy per-user unit, with a variable such as `cao_service_legacy_names: ["cao-server-{{ ai_stack_user }}"]`. Only when `cao_service_enabled` is true, and only for legacy names that differ from cao_service_name:
   - Detect whether /etc/systemd/system/<legacy>.service exists. Do not follow symlinks.
   - Only touch it if it was provably created by this role. Compare it with what cao-server.service.j2 renders or with distinctive lines (ExecStart pointing at the stack's cao-server, User=ai_stack_user). Otherwise FAIL with a clear message and change nothing.
   - If the legacy unit is active, stopping it kills every open CAO session. So: when `cao_restart_on_change` is false, FAIL early, before changing anything, with a Portuguese message telling the user to re-run in a maintenance window with `-e cao_restart_on_change=true`. When it is true: stop and disable the legacy unit, remove its file, run daemon-reload, and only then install, enable and start `cao-server`. The order prevents two units fighting over port 9889.
   - If the legacy unit is inactive: disable it, remove it and daemon-reload without needing cao_restart_on_change.
   - Check mode: report what would happen; change nothing.
   - When `cao_service_enabled` is false, do not touch any unit. Document the manual migration commands in the README.
3. Update every reference: tasks/service.yml, tasks/restart-service.yml, ai/README.md (lines ~370-391: systemctl/journalctl examples, "cao-server-ubuntu" text, disable command) and vars.example.yml if relevant.
4. COORDINATION: another developer (herdr task) may edit ai/roles/cao/templates/cao-server.service.j2 to add a terminal-backend option. Do NOT edit that template. Re-read service.yml right before editing it. You own service.yml, restart-service.yml, defaults/main.yml and README.md.
5. Verification, with logs under tasks/tiered-agent-profiles/:
   - syntax-check;
   - in an isolated setup, exercise the migration logic as far as feasible without systemd on the real host. For example, test the "provably created by this role" detection by rendering the template, and the cao_restart_on_change gate with assert-only runs.
   - Do NOT run anything against the real /etc/systemd. Do NOT stop, start or restart any real service. No commits.

Reply via send_message (Portuguese) with the files changed, results with log paths, what was not verified, and any deviations.

[Message from terminal 97593bc0. Use send_message MCP tool for any follow-up work.]
