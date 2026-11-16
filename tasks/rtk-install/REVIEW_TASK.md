# Final independent re-review: RTK corrections, round two

Status: implementation and focused validation complete; ready for independent
review. The original written correction task is preserved unchanged at:
`/home/andrew/git/ansible-workstation/tasks/rtk-install/REVIEW.md`.

Review only the RTK changes under these authorized directories:

- `/home/andrew/git/ansible-workstation/ai/roles/rtk/`
- `/home/andrew/git/ansible-workstation/tasks/rtk-install/`

Do not apply anything to the real HOME, alter shared files, run the workstation
playbook or restart sessions. The next step is final independent review;
bounded live RTK installation belongs to the supervisor only after that review.
Supervisor: terminal `14a03d1f`; shared integration owner: `ff025942`.

## Corrections to verify

1. **Execution gate:** inspect
   `/home/andrew/git/ansible-workstation/ai/roles/rtk/files/installed_state.py`,
   `/home/andrew/git/ansible-workstation/ai/roles/rtk/tasks/main.yml` and
   `/home/andrew/git/ansible-workstation/ai/roles/rtk/tasks/release.yml`.
   The installed --version probe requires a supported regular nonsymlink receipt
   and regular nonsymlink executable matching its SHA256, including in check
   mode. Invalid state skips execution and requires reconciliation; skipped
   command results use safe defaults. Published integrity is checked again before
   init. Candidates must be regular nonsymlink executables after archive validation.
   Nonregular destinations are preserved by rename without following targets;
   unsafe directory ancestors fail before filesystem writes. Valid installed
   releases still support offline retention and version probing.
2. **Prior native hook paths:** inspect
   `/home/andrew/git/ansible-workstation/ai/roles/rtk/files/configure_rtk.py`.
   Exact bare/current/native absolute */rtk hook commands migrate to the current
   wrapper. Duplicate and matcher guards span those paths. Arbitrarily named
   old path-shaped wrappers and customized native commands are explicitly
   rejected before client configuration writes. Unrelated hooks/events/settings
   remain intact. Relocation is idempotent and ambiguous second-client input
   prevents partial writes to either client.

## Current evidence

- `/home/andrew/git/ansible-workstation/tasks/rtk-install/REPORT.md`
- `/home/andrew/git/ansible-workstation/tasks/rtk-install/ROUND2_EVIDENCE.json`
- `/home/andrew/git/ansible-workstation/tasks/rtk-install/IMPLEMENTATION.diff`
- `/home/andrew/git/ansible-workstation/tasks/rtk-install/ROUND2.diff`
- `/home/andrew/git/ansible-workstation/tasks/rtk-install/IMPLEMENTATION.round1.diff`
- `/home/andrew/git/ansible-workstation/tasks/rtk-install/DELIVERABLES.txt`
- `/home/andrew/git/ansible-workstation/tasks/rtk-install/ALL_PATHS.txt`

Focused checks are sufficient per the supervisor's latest direction; no broader
testing or features are requested before review. Completed evidence:

- 29 passing unit/integration tests:
  `/home/andrew/git/ansible-workstation/tasks/rtk-install/all-tests-round2.log`.
- 20 offline runs of the actual inspection/probe/release-decision tasks in
  normal/check modes (18 invalid cases never execute; two verified controls do):
  `/home/andrew/git/ansible-workstation/tasks/rtk-install/EXECUTION_GATE_RESULTS.json`.
- Existing official-release syntax, upgrade, offline retention, idempotence and
  checksum-rejection checks rerun successfully:
  `/home/andrew/git/ansible-workstation/tasks/rtk-install/ansible-validation-round2.log`
  and `/home/andrew/git/ansible-workstation/tasks/rtk-install/VALIDATION_RESULTS.json`.
- Full-role invalid-state recovery and final changed=0:
  `/home/andrew/git/ansible-workstation/tasks/rtk-install/recovery-validation-round2.log`
  and `/home/andrew/git/ansible-workstation/tasks/rtk-install/RECOVERY_RESULTS.json`.
- Final source idempotence/check mode:
  `/home/andrew/git/ansible-workstation/tasks/rtk-install/ansible-final-round2-idempotence.log`
  and `/home/andrew/git/ansible-workstation/tasks/rtk-install/ansible-final-round2-check.log`.
- Clean-install check mode:
  `/home/andrew/git/ansible-workstation/tasks/rtk-install/ansible-check-empty-round2.log`.

The first networked symlink recovery attempt hit GitHub's public API quota after
skipping the invalid executable. Its failure log is retained. Recovery checks
then passed using a temporary localhost fixture serving the previously retained,
digest-verified official artifacts; no production endpoints were changed.
No authenticated agent session, ARM64 execution or live installation was added.
Ansible-lint remains unavailable. These limits are separate from the two fixes.

Reviewable test sources:

- `/home/andrew/git/ansible-workstation/tasks/rtk-install/test_installed_state.py`
- `/home/andrew/git/ansible-workstation/tasks/rtk-install/test_configure_rtk.py`
- `/home/andrew/git/ansible-workstation/tasks/rtk-install/validate_recovery.py`
- `/home/andrew/git/ansible-workstation/tasks/rtk-install/validate_ansible.py`

Return the final verdict and any remaining findings with absolute file/line
references. Keep technical records and agent instructions in English; communicate
with the user in Portuguese. Do not install live as part of the review.
