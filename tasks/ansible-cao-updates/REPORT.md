# RTK shared-default scope correction — final re-review

Status: **implemented and validated; ready for final independent review**. No blocker. No live workstation installation or service/session restart was performed. The CAO P2 corrections remain unchanged and retain their round-two APPROVED status; the current correction addresses only the remaining RTK P1 scope finding.

## Written task and correction

The complete REVIEW_ROUND2.md was read before changes. ROUND3_TASK.md records its P1 correction scope. Git status and applicable AGENTS paths were checked first; no applicable AGENTS.md was present. Round-two implementation files matched their recorded hashes and were checkpointed with their evidence in round2/ before editing.

In /home/andrew/git/ansible-workstation/ai/rtk.yml, the RTK play now explicitly declares the ai_stack role with a constant false task condition before declaring rtk. Ansible exposes this statically declared role's defaults in the RTK play, while its prerequisite tasks remain disabled there. The preceding common.yml import remains responsible for actually preparing prerequisites. This uses role-default precedence, preserving inventory variables and extra vars instead of overriding them with higher-precedence play vars_files.

No ai/roles/rtk file was edited by this task. No approved CAO helper, dependency, handler, source/pin, or update behavior changed. The other nine previously reviewed implementation files remain byte-identical. The only new implementation file is /home/andrew/git/ansible-workstation/ai/tests/test_rtk_entrypoint.py.

## Focused task-free regression

The new test loads the actual rtk.yml and all.yml through Ansible's Playbook loader and VariableManager, selects the actual RTK play, and templates its shared/derived values. It executes no Ansible tasks and performs no installation/download. It uses the interpreter containing Ansible (/usr/bin/python3 here, configurable with ANSIBLE_TEST_PYTHON), independently of the suite interpreter.

Three tests cover six combinations: standalone/all.yml with ordinary defaults, inventory overrides and competing extra-variable overrides. They resolve ai_stack_user/home/bin_dir/cache_dir/environment/upgrade plus rtk_install_dir/binary/upgrade, and confirm that the repeated shared role's tasks remain statically disabled, including the inherited all.yml enable guard. All combinations pass. The default case injects only synthetic account facts; no shared variables are supplied to hide the original scope defect.

## Actual entrypoint in disposable HOME

/usr/bin/python3 /home/andrew/git/ansible-workstation/tasks/rtk-shared-integration/validate_entrypoint_isolated.py executed the real /home/andrew/git/ansible-workstation/ai/rtk.yml twice with --skip-tags ai_common. It used a new disposable HOME and only overrode ai_stack_home among shared variables; user/bin/cache/environment/upgrade therefore came from the corrected entrypoint defaults. Clients were empty to keep authenticated hooks outside this scope.

The fixture seeded RTK from the existing local OSS 1.2.0 archive only after verifying its SHA256 against the audited architecture pin, then created the corresponding public provenance receipt. No release lookup/download was needed; a loopback-only sentinel URL would fail any accidental lookup. Common package/PATH tasks were skipped; the static false role condition also prevented them from rerunning in the RTK play. The role published its wrapper/helper inside the temporary HOME and the second actual invocation reported changed=0. The temporary HOME was removed. ISOLATED_ENTRYPOINT.json contains exact argv, outputs and archive provenance.

This validates entrypoint variable scope and bounded invocation, not a fresh remote release installation, live authentication or real-home hooks. No workstation apply, server/session operation or bounded live RTK installation was performed. Live application remains a separate next step after independent approval.

## Concurrent independently owned RTK changes

During final evidence collection, the RTK owner independently changed /home/andrew/git/ansible-workstation/ai/roles/rtk/README.md and files/configure_rtk.py. These changes were detected by hash comparison, reported to supervisor 14a03d1f and neither edited nor reverted. ROUND3_RTK_ROLE_BASELINE.json preserves this correction's initial role hashes; ROUND3_RTK_ROLE_CURRENT.json records the external deltas/current hashes. The isolated entrypoint was rerun successfully against that current role, which remained stable through final evidence capture. Review/approval of the role implementation remains separate.

## Recorded verification

VALIDATION.json records the already completed final commands and outputs: 22 tests passed (three new task-free tests plus the previous 19), syntax-checks for rtk.yml/all.yml, standalone/tag-selected task listings, git diff --check, Python AST parsing, unchanged approved implementation hashes, and unchanged live CAO receipt. The existing CAO server remains PID 240075 with its original start time. The syntax/list warnings are only the implicit localhost inventory and existing browser/chrome.yml deprecations.

No further tests/features were added after the supervisor's instruction to finalize. The isolated runtime evidence is /home/andrew/git/ansible-workstation/tasks/rtk-shared-integration/ISOLATED_ENTRYPOINT.json. The validation script is an internal reproduction artifact, not an installer entrypoint for real HOME.

## Review artifacts and retained limits

ROUND3_CHANGES.diff contains this correction's two implementation entries. CHANGES.diff covers the full eleven-file combined change; FINAL_STATE.json/FILES.json contain current hashes. REVIEW_TASK.md requests final review in REVIEW_ROUND3.md, preserving the earlier reviews and snapshots. Historical ROUND2_CHANGES.diff and round2/ evidence describe the previous correction stage.

Initial baseline preservation limits remain unchanged: the original cao/tasks/main.yml was reconstructed from its initial full read without an independent initial hash; other preserved originals match their captured hashes. Fifty-five captured baseline files outside declared edits remain unchanged. No central-de-incidentes checkout file was changed. The upstream/PyPI distinction and limitation of effort:auto consumption to ephemeral launches remain as previously documented; no decider or live end-to-end effort behavior is claimed.
