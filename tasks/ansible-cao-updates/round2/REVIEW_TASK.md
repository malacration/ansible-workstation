# Independent re-review request — round two

Repository: /home/andrew/git/ansible-workstation.
Read applicable AGENTS.md and git status before acting. No applicable AGENTS.md was found in the edited paths. Use absolute paths; preserve preexisting changes. Do not apply any live installation/playbook, restart servers/sessions, launch workers, edit ai/roles/rtk, or change central-de-incidentes. Never read/output prohibited credentials, SSH files, .env or PEM files.

## Written task and scope

Read REVIEW.md completely: its two P2 findings are the written correction task. Then read ROUND2_TASK.md, REPORT.md, ROUND2_CHANGES.diff, CHANGES.diff, VALIDATION.json, FINAL_STATE.json, PRESERVATION.json and FILES.json in this directory. Round-one files and evidence are checkpointed in round1/; its historical manifests describe the earlier files. Check current hashes against the current manifests.

The ten implementation paths in FINAL_STATE.json are in scope. The six round-two paths are:
- /home/andrew/git/ansible-workstation/ai/roles/cao/files/install_cao.py
- /home/andrew/git/ansible-workstation/ai/roles/cao/tasks/main.yml
- /home/andrew/git/ansible-workstation/ai/tests/test_install_cao.py
- /home/andrew/git/ansible-workstation/ai/README.md
- /home/andrew/git/ansible-workstation/ai/all.yml
- /home/andrew/git/ansible-workstation/ai/rtk.yml

## Required review

1. Verify semantic normalization/deduplication of configured and receipt requirements: distribution/extra aliases, specifier equivalence and mutable Git refs. Confirm the persistent underscore-alias regression proves ordinary calls preserve the first module revision after the branch advances, and explicit upgrade installs the next revision.
2. Verify receipt-level constraints/overrides/unknown resolution options fail before uv tool install, including when source or upgrade changes. Verify supported find-links is replayed. Check the stored UV_CONSTRAINT regression asserts unchanged receipt/environment and no install call. No transitive freeze is substituted for this behavior.
3. Check the explicit packaging>=24.2,<27 dependency in the separate uv-run interpreter, Python >=3.11 behavior, and the offline parser-wheel fixture. It must not alter CAO tool requirements.
4. Review the shared RTK integration against /home/andrew/git/ansible-workstation/tasks/rtk-shared-integration/specification.md and its report. Verify ai/rtk.yml imports common prerequisites, all.yml imports it after clients with the rtk tag/optional enable guard, and README commands/source/version policy are accurate. Role implementation/review is separate; do not edit ai/roles/rtk. Match its hashes against ROLE_BASELINE.json.
5. Retain the source/effort and initial-baseline limitations documented in REPORT.md. Approval concerns validated code, not live installation or end-to-end effort. The original cao/tasks/main.yml baseline was reconstructed from an initial read and lacks an independent initial hash.
6. Write REVIEW_ROUND2.md here with explicit APPROVED or concrete findings/severity/paths/evidence; preserve REVIEW.md as the first-round review.

## Safe reproduction

```bash
ansible-playbook /home/andrew/git/ansible-workstation/ai/cao.yml --syntax-check
ansible-playbook /home/andrew/git/ansible-workstation/ai/cao-update.yml --syntax-check
ansible-playbook /home/andrew/git/ansible-workstation/ai/rtk.yml --syntax-check
ansible-playbook /home/andrew/git/ansible-workstation/ai/all.yml --syntax-check
ansible-playbook /home/andrew/git/ansible-workstation/ai/rtk.yml --list-tasks
ansible-playbook /home/andrew/git/ansible-workstation/ai/all.yml --list-tasks --tags rtk
/home/andrew/.local/share/uv/tools/cli-agent-orchestrator/bin/python -m unittest discover -s /home/andrew/git/ansible-workstation/ai/tests -v
```

The recorded final run passed all 19 tests. Do not run the full workstation playbook or a real-home RTK fixture. No user-facing document translation was undertaken; new internal records/instructions are in English.
