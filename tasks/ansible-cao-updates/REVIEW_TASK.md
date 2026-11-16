# Final independent re-review request — RTK shared defaults

Repository: /home/andrew/git/ansible-workstation.
Read applicable AGENTS.md and git status first. Preserve preexisting work. Do not apply any real-home installation/playbook, restart services/sessions, launch workers, edit ai/roles/rtk or alter central-de-incidentes. Never read/output prohibited credential, SSH, .env or PEM files.

Read REVIEW_ROUND2.md completely as the written P1 correction task. Its CAO P2 corrections were APPROVED and are unchanged. Then read ROUND3_TASK.md, REPORT.md, ROUND3_CHANGES.diff, VALIDATION.json, FINAL_STATE.json, PRESERVATION.json and FILES.json. Historical round-two implementation/evidence is checkpointed under round2/.

The only implementation delta for this final correction is:
- /home/andrew/git/ansible-workstation/ai/rtk.yml
- /home/andrew/git/ansible-workstation/ai/tests/test_rtk_entrypoint.py

Verify that the actual RTK play exposes ai_stack role defaults while statically disabling its repeated prerequisite tasks, retaining common.yml execution and inventory/extra-variable precedence. Inspect the task-free regression for both actual entrypoints under defaults/inventory/extra-vars, including derived paths/environment/upgrade values. It must not run tasks or inject the shared variables in the ordinary-default case.

Inspect /home/andrew/git/ansible-workstation/tasks/rtk-shared-integration/ISOLATED_ENTRYPOINT.json and validate_entrypoint_isolated.py. The already completed actual entrypoint fixture used disposable HOME, a checksum-verified existing archive, no selected clients, skipped shared prerequisites and no release lookup; repeat invocation reported changed=0. Do not run it against real HOME. The focused checks already passed and the supervisor requested finalization; no broader testing or feature work is necessary.

The independently owned role changed concurrently in README.md and files/configure_rtk.py. ROUND3_RTK_ROLE_BASELINE.json and ROUND3_RTK_ROLE_CURRENT.json explicitly record those external changes. They were not edited/reverted by this task; the current role was stable during the successful isolated rerun/final capture. Do not treat this entrypoint review as approval of the separate role implementation.

The recorded final suite has 22 passing tests; syntax/list checks also passed. Verify current hashes, the nine unchanged previously reviewed implementation files, and retained initial-baseline/source/effort limitations. CHANGES.diff covers eleven combined files; ROUND3_CHANGES.diff isolates two current deltas. Historical manifests describe their own stages.

Write REVIEW_ROUND3.md in this directory with explicit APPROVED or concrete findings, severity, paths and evidence. Preserve REVIEW.md and REVIEW_ROUND2.md. Approval applies to code and bounded fixture evidence, not live installation or authenticated end-to-end behavior. The next live RTK installation is reserved for the supervisor after independent approval.

If a focused reproduction is necessary, the task-free regression is:

```bash
/home/andrew/.local/share/uv/tools/cli-agent-orchestrator/bin/python -m unittest discover -s /home/andrew/git/ansible-workstation/ai/tests -p test_rtk_entrypoint.py -v
```
