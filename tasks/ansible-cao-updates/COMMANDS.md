# Final correction commands and evidence

Exact argv/stdout/stderr and exit codes are in VALIDATION.json. All completed checks passed.

`ansible-playbook /home/andrew/git/ansible-workstation/ai/rtk.yml --syntax-check` — exit 0
`ansible-playbook /home/andrew/git/ansible-workstation/ai/all.yml --syntax-check` — exit 0
`ansible-playbook /home/andrew/git/ansible-workstation/ai/rtk.yml --list-tasks` — exit 0
`ansible-playbook /home/andrew/git/ansible-workstation/ai/all.yml --list-tasks --tags rtk` — exit 0
`/home/andrew/.local/share/uv/tools/cli-agent-orchestrator/bin/python -m unittest discover -s /home/andrew/git/ansible-workstation/ai/tests -v` — exit 0
`git diff --check` — exit 0
`ps -p 240075 -o pid=,lstart=,args=` — exit 0
`git status --short` — exit 0

Actual entrypoint fixture (completed twice successfully after current-role snapshot):
`/usr/bin/python3 /home/andrew/git/ansible-workstation/tasks/rtk-shared-integration/validate_entrypoint_isolated.py`

Its nested Ansible argv and outputs are in /home/andrew/git/ansible-workstation/tasks/rtk-shared-integration/ISOLATED_ENTRYPOINT.json. No further testing was started after the supervisor requested finalization.
