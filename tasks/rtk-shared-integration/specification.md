# task-ansible-rtk-shared-integration
<!-- id: 466b796c-ed77-49a4-91be-76da099ffddc | scope: session | type: project | tags:  -->

## 2026-11-16T13:57:12Z
After fixing the CAO review findings, integrate the completed RTK role in /home/andrew/git/ansible-workstation using /home/andrew/git/ansible-workstation/tasks/rtk-install/INTEGRATION.md and rtk.yml.example: create the standalone ai/rtk.yml entry point, add its import to ai/all.yml, and update user-facing ai/README.md with install/update commands and source/version policy without changing the independently reviewed RTK role. Preserve existing changes and CAO fixes, validate syntax/list-tasks and isolated invocation as appropriate, create a concise integration report and REVIEW_TASK.md with absolute paths, never read or output prohibited secret files or run forbidden commands, and do not apply live installation or restart active sessions.
