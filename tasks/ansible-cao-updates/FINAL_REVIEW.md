# Final independent CAO and RTK review

**APPROVED.** All three outstanding findings are resolved. No remaining actionable issue was identified in the reviewed corrections or final shared integration. The reviewed source is ready for the supervisor's separately authorized, bounded RTK-only application.

This is approval of the current code and recorded isolated evidence. No live installation, workstation playbook, service/session restart or worker launch was performed by this review. No implementation was edited. Earlier reviews remain preserved.

## Findings closed

### P1: RTK entrypoint lacked shared defaults — resolved

`/home/andrew/git/ansible-workstation/ai/rtk.yml:14` statically declares `ai_stack` in the RTK play with `when: false`. Its defaults are therefore available in that play at role-default precedence, while its tasks are disabled there. The preceding `common.yml` import still performs ordinary prerequisite preparation. This fixes the missing-variable failure without overriding inventory or extra variables with higher-precedence play variables.

`/home/andrew/git/ansible-workstation/ai/tests/test_rtk_entrypoint.py` loads the actual standalone and combined entrypoints through Ansible and resolves their actual RTK plays. Three tests cover six combinations: `rtk.yml`/`all.yml` with defaults, inventory overrides and competing extra-variable overrides. Assertions cover user, home, bin/cache paths, environment, derived RTK paths and upgrade inheritance. The default case supplies only synthetic account facts, not the previously missing shared variables. The tests also check the static false condition on the repeated shared role.

`/home/andrew/git/ansible-workstation/tasks/rtk-shared-integration/ISOLATED_ENTRYPOINT.json` records successful execution of the real standalone entrypoint twice. The fixture seeded a disposable HOME with the retained OSS archive after checking its audited SHA256. Among shared variables, only the home was overridden; user/bin/cache/environment defaults came from the entrypoint. Common prerequisite tasks were skipped, the repeated shared-role tasks were visibly skipped, clients were empty and a loopback sentinel guarded against accidental release lookup. Initial wrapper/helper publication succeeded, and the repeat invocation returned **changed=0**. The fixture script removes its temporary HOME. This demonstrates the corrected runtime scope without applying workstation prerequisites or live hooks.

The final `/home/andrew/git/ansible-workstation/ai/all.yml` retains the RTK import after the client installers, the `rtk` tag and the default-true enable guard. README source/pin/update/PATH guidance remains unchanged from the previously reviewed integration. The recorded task selection still isolates prerequisite/RTK task bodies under `--tags rtk`.

### RTK P2: altered executable ran before integrity validation — resolved

`/home/andrew/git/ansible-workstation/ai/roles/rtk/files/installed_state.py:43` validates receipt shape, OSS edition/version/architecture metadata and SHA256 fields, reads only regular nonsymlink files, checks executable permissions and compares the installed binary hash without executing RTK. Its reader avoids following symlinks or blocking on FIFOs, and unsafe directory ancestors are rejected.

`/home/andrew/git/ansible-workstation/ai/roles/rtk/tasks/main.yml:48` permits the installed `--version` probe only when that inspection is valid, including in check mode. Invalid/skipped states safely require reconciliation. Published state is checked again before init at line 106. The release task validates the checksum first and then requires a regular nonsymlink executable candidate before executing its version probe. Nonregular publication destinations are preserved by rename without following targets.

The exact product-task regression in `/home/andrew/git/ansible-workstation/tasks/rtk-install/test_installed_state.py` exercises **20 normal/check combinations**. `/home/andrew/git/ansible-workstation/tasks/rtk-install/EXECUTION_GATE_RESULTS.json` records **18 invalid cases with no execution marker**, plus two verified controls that do execute. Cases include hash mismatch, missing/malformed/unsupported receipts, receipt/binary symlinks, FIFO, missing binary and nonexecutable binary.

Full-role recovery evidence additionally verifies that mismatched and symlinked executables are not run, check mode preserves the original state, normal mode publishes a verified replacement, symlink targets remain unchanged, and invalid directory objects are preserved. Malformed-receipt recovery succeeds. Final normal and check runs both report **changed=0**.

### RTK P2: old absolute native hook duplicated — resolved

`/home/andrew/git/ansible-workstation/ai/roles/rtk/files/configure_rtk.py:52` now recognizes exact native `rtk hook CLIENT` commands at previous absolute `*/rtk` paths, as well as bare/current paths. A single recognized hook is migrated to the current quoted wrapper command. Duplicate detection and matcher checks span those paths. Ambiguous path-shaped wrappers and customized recognized native commands are refused before client configuration writes.

`/home/andrew/git/ansible-workstation/tasks/rtk-install/test_configure_rtk.py` covers migration for both clients, quoted paths containing spaces, old/current/bare duplicate combinations, custom matchers, ambiguous wrappers and native extra flags. Its real-release relocation test checks that exactly one managed hook remains for each client and that a repeat is unchanged. The ambiguous second-client regression snapshots both clients' files and verifies that refusal causes no partial write. Existing unrelated-hook/settings/instruction/backup behavior remains covered.

## Evidence integrity and test assessment

Read both updated review requests, the final written task, prior reviews, current correction diffs/source/tests, reports and targeted validation artifacts. Checked git status and applicable AGENTS locations; no applicable target-tree or ancestor AGENTS file was present. Followed the latest supplied command-output instructions for subsequent work. Prohibited secret files were not accessed.

Independent fingerprint/diff checks confirmed:

- **11/11** combined implementation hashes match `/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/FINAL_STATE.json`.
- **79/79** artifact/current-file hashes match `/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/FILES.json` before adding these review outputs.
- The **nine previously reviewed paths** outside the entrypoint correction remain byte-identical. Round-two implementation snapshots match their historical hashes. The earlier CAO semantic-normalization and receipt-resolution-state fixes retain their approval and were not reopened.
- `CHANGES.diff` exactly reproduces the eleven-file current change, and `ROUND3_CHANGES.diff` exactly reproduces the two final entrypoint/test deltas.
- All **19 source fingerprints** in `/home/andrew/git/ansible-workstation/tasks/rtk-install/ROUND2_EVIDENCE.json` match current files, including all eight RTK role files. All eight role-context hashes in the combined final manifest also match. Concurrent role corrections recorded by the integration owner are therefore included in this final review rather than treated as accidental shared edits.
- The retained RTK complete implementation diff matches all **18 checked implementation/deliverable entries**; its review-request entry is separately covered by the matching evidence fingerprint. The RTK `ROUND2.diff` was reviewed against the original findings and current source.
- All **55** captured baseline files outside the authorized edits remain unchanged. The first CAO review equals its round-one preserved copy, and the second equals its preserved round-two copy. The original RTK review was left untouched.

Recorded evidence is credible and directly addresses the failures:

- Combined suite: **22 tests passed**, including the three new task-free entrypoint tests and the previously approved CAO/MCP tests; syntax/list checks passed.
- RTK suite: **29 tests passed**, including actual-task execution gating and real-release hook relocation.
- RTK gate: **20 cases**, with no invalid executable run.
- RTK full-role upgrade/offline-retention/checksum-rejection and recovery checks passed; final normal/check runs were idempotent.
- Actual standalone entrypoint: successful isolated initial publication and **changed=0** repeat against the final stable role.

No new tests or installations were needed for this final review: the current hashes match those validated files and the focused evidence resolves all three known findings. The retained GitHub quota failure is transparently documented; subsequent recovery used a localhost fixture serving the retained digest-verified official artifacts, without changing production endpoints.

## Scope and retained limits

The reviewed release policy remains OSS 1.2.0 with mandatory official checksum verification, explicit updates and valid-install offline retention. The public wrapper still disables telemetry and proxy onboarding; init uses an empty staging HOME and the correct separate Claude/Codex flags. No proxy, remote pipeline, MCP/auth/permission change or automatic session restart was introduced.

This approval supports bounded RTK application by the supervisor under the existing task scope. It does not represent a real-home apply, a whole-workstation apply, an authenticated agent end-to-end test, or a CAO upgrade. The standalone entrypoint normally includes shared prerequisite tasks; the bounded fixture deliberately skipped them and did not select clients. Actual client-hook processing/preservation is supported separately by the RTK real-release tests.

ARM64 archive/ELF validation remains recorded without ARM64 execution; ansible-lint remains unavailable. The original CAO role-task baseline was reconstructed from its initial read and lacks an independent initial hash. The upstream/PyPI same-version distinction and the limitation of decided effort to ephemeral `effort: auto` launches remain unchanged. None of these documented limits leaves one of the reviewed findings unresolved.

Critical final source fingerprints:

| Absolute path | SHA256 |
| --- | --- |
| `/home/andrew/git/ansible-workstation/ai/rtk.yml` | `267daf4a1e013358d992f537e5ddfcd969a6b561c12d515382589a997675ebd0` |
| `/home/andrew/git/ansible-workstation/ai/roles/rtk/tasks/main.yml` | `e44f89b2efc3f2327236c7af62b4da625b429b3d7aed6d536fe033dcbe8043e5` |
| `/home/andrew/git/ansible-workstation/ai/roles/rtk/files/installed_state.py` | `8350b0c1ddfcc251e5650285bcb302815b48e059aef1e5db3f274d74f82a054c` |
| `/home/andrew/git/ansible-workstation/ai/roles/rtk/files/configure_rtk.py` | `9f063e4d14b2ab4ebc11d015529a7b820410b4361ccc0afe785cbcf86e7a2d88` |
