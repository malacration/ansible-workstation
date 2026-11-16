<!-- cao-memory:begin -->
<cao-memory>
## Context from CAO Memory
- [project] cao-role-tool-limits-reviewer-supervisor: CAO role defaults (constants.ROLE_TOOL_DEFAULTS): supervisor = @cao-mcp-server+fs_read+fs_list, reviewer = @builtin+fs_read+fs_list+@cao-mcp-server (no fs_write/execute_bash), so reviewer/supervisor sessions cannot write task/review files or run tests unless the profile sets explicit allowedTools.
- [project] tiered-agent-profiles-design: Decision (2026-11-16): CAO agent profiles are managed by the ansible-workstation ai/ stack (role cao, sync_mcps.py). Design: generalist developer_low/medium/high (reasoning effort low/medium/high), reviewer_basic (lowest effort, simple tasks) and reviewer_advanced (high effort, high tasks); the supervisor classifies each task and routes accordingly; workers stay on the supervisor's provider.
- [global] mala-profiles-provider-routing: User's own CAO profiles are named mala_<role>_<level>_<codex|claude> (e.g. mala_supervisor_codex, mala_developer_medium_claude, mala_reviewer_basic_codex). The supervisor chooses the provider: development preferably on Claude Opus, review preferably on Codex, Codex developers allowed at any level, and it fails over to the other provider when one hits a usage/token limit.
- [global] ansible-self-contained-dependencies: The user expects Ansible to install and refresh required repository signing keys and resolve its own dependencies, rather than requiring manual host repair. The current authorized change is the Chrome APT playbook in /home/andrew/git/ansible-workstation; previously cancelled CAO/RTK work must not be resumed.
</cao-memory>
<!-- cao-memory:end -->
