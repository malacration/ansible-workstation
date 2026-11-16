# RTK shared integration — scope correction complete

Ready for final independent review. The written remaining P1 was /home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/REVIEW_ROUND2.md. The RTK play now statically declares ai_stack with its tasks disabled, exposing role defaults at their normal low precedence while common.yml remains responsible for prerequisites. Inventory and extra-variable overrides are preserved.

The new /home/andrew/git/ansible-workstation/ai/tests/test_rtk_entrypoint.py executes no Ansible tasks: it resolves both actual standalone/all.yml RTK plays under defaults/inventory/extra-vars. All six combinations pass. The already completed suite has 22 passing tests, plus syntax/task-list checks. The real standalone entrypoint also passed initial publication and repeat changed=0 in disposable HOME, with common tasks skipped, no selected clients and a locally seeded checksum-verified archive; see ISOLATED_ENTRYPOINT.json and validate_entrypoint_isolated.py.

No RTK role file was edited by the shared integration developer. The independent role owner changed README.md/configure_rtk.py concurrently; the combined task records before/current hashes and reran the isolated fixture successfully against that stable current state. No live installation or server/session restart occurred.

Final written review request: /home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/REVIEW_TASK.md.
Detailed report/evidence: /home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/REPORT.md and VALIDATION.json.
