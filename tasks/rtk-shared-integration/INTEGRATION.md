# Shared-file integration handoff

Owner of the shared CAO integration: terminal `ff025942`, coordinated by
supervisor `14a03d1f`. The RTK worker changed only:

- `/home/andrew/git/ansible-workstation/ai/roles/rtk/`
- `/home/andrew/git/ansible-workstation/tasks/rtk-install/`

The role did not exist at preflight. Existing tracked and untracked work was
preserved. No AGENTS.md was found in the target repo or the inspected ancestor
chain. The supplied coordination rules governed the implementation. There is
no `ai/playbook.yml` in the current checkout; the existing entrypoint is
`/home/andrew/git/ansible-workstation/ai/all.yml`.

After reviewing the RTK role, the shared-file owner should:

1. Create `/home/andrew/git/ansible-workstation/ai/rtk.yml` using the content of
   `/home/andrew/git/ansible-workstation/tasks/rtk-install/rtk.yml.example`.
   Importing common.yml supplies the existing stack defaults, prerequisite tools
   and PATH initialization. Do not apply the isolated fixture as a real installer.
2. Add an `import_playbook: rtk.yml` entry to
   `/home/andrew/git/ansible-workstation/ai/all.yml`, after the client installers
   and before launching/syncing CAO if convenient, with `tags: [rtk]` and optional
   `when: rtk_enabled | default(true) | bool`. RTK does not require changes to
   CAO providers, MCP synchronization, ai_stack, systemd or client authentication.
3. Document the component in `/home/andrew/git/ansible-workstation/ai/README.md`
   and optionally `/home/andrew/git/ansible-workstation/ai/vars.example.yml`:
   the OSS release is pinned to 1.2.0, clients default to `[claude_code, codex]`,
   `rtk_upgrade` inherits `ai_stack_upgrade`, native hooks cover only shell tools,
   and RTK never changes provider URLs, MCPs or sandbox permissions.
4. Validate syntax/tasks for `ai/rtk.yml` and `ai/all.yml` after integration.
   Review generated hook changes before applying to the actual workstation.

Commands after integration and review (not executed on the real HOME):

```bash
cd /home/andrew/git/ansible-workstation
ansible-playbook ai/rtk.yml --syntax-check
ansible-playbook ai/all.yml --list-tasks --tags rtk
ansible-playbook ai/rtk.yml --check --diff -K
# Real application is reserved for the supervisor after review:
ansible-playbook ai/rtk.yml -K
# Change to a new reviewed pin, or explicitly refresh latest:
ansible-playbook ai/rtk.yml -K -e rtk_version=latest -e rtk_upgrade=true
# Stack-wide upgrade flag also refreshes RTK:
ansible-playbook ai/rtk.yml -K -e rtk_version=latest -e ai_stack_upgrade=true
```

Do not restart active client/CAO sessions as part of this handoff. New sessions
load the merged hooks. Existing unselected hooks and instructions are retained.
The native hooks' replacement commands use `rtk` from PATH; ensure CAO/client
launch environments include the stack's bin directory. No live authenticated
agent end-to-end test has been performed; isolated payload and local shell
filter tests passed.
