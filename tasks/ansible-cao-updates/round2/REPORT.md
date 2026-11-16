# CAO corrections and RTK shared integration — round two

Status: **implemented and validated; ready for independent re-review**. No blocker. The workstation playbook was not applied; no live installation, CAO configuration change or server/session restart occurred. The independently owned RTK role was not edited.

## Correction task and evidence preservation

The complete written review `/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/REVIEW.md` was read before edits. Its two P2 findings are addressed below. `ROUND2_TASK.md` records the correction scope. The round-one implementation hashes were verified and the files/evidence checkpointed in `round1/` before changes; `round1/REVIEW.md` preserves the review. Historical manifests under round1 describe historical hashes, not the current files.

Git status and applicable AGENTS paths were checked before editing. No applicable AGENTS.md was present. Preexisting tracked/untracked work was retained. The RTK shared-integration task was subsequently copied to `/home/andrew/git/ansible-workstation/tasks/rtk-shared-integration/specification.md` before edits to the shared entry points or README.

## Finding 1: normalized requirements and the no-update boundary

`/home/andrew/git/ansible-workstation/ai/roles/cao/files/install_cao.py` now parses requirements with `packaging.requirements.Requirement`, canonicalizes distribution and extra names, and compares semantic Requirement objects. Specifier equality handles equivalent versions and reordered clauses; equivalent auxiliary declarations are deduplicated before invoking uv. Both configured and receipt requirements pass through the same normalization. Raw underscore/case/dot aliases therefore cannot bypass the no-update boundary for an unchanged mutable Git request.

`/home/andrew/git/ansible-workstation/ai/roles/cao/tasks/main.yml` explicitly supplies `packaging>=24.2,<27` through the separate uv-run interpreter environment. The parser dependency does not become a CAO tool requirement. The selected Python remains >=3.11, preserving Ubuntu 22.04 support despite its system Python 3.10. Offline tests expose the already installed parser source as a temporary local wheel so this runtime invocation is exercised without downloading a package or changing the real tool environment.

Focused regressions retain a mixed-case underscore auxiliary alias throughout the installation sequence. After main advances to a new commit with the same package version, an ordinary invocation returns unchanged and the installed module remains at the first revision; an explicit upgrade installs the second revision. Unit coverage additionally checks extra aliases, repeated separators and semantically equivalent version specifiers/hashes. The auxiliary requirement count remains one.

## Finding 2: receipt-level resolution state

The helper now validates the full receipt before the no-op decision or any uv tool installation. Nonempty unsupported receipt-level state (including constraints and overrides) and unsupported tool options (including resolution/index options) cause an actionable ValueError. The operation fails before invoking `uv tool install`; operator compatibility pins are not silently removed. The supported find-links option is replayed explicitly. Empty unsupported fields have no resolution state to preserve.

A regression creates a real disposable uv receipt with UV_CONSTRAINT pinning an unpinned auxiliary requirement to 1.0, then makes 2.0 locally available and removes the one-time environment variable. Both explicit upgrade and source-change attempts are rejected. The test asserts that the only uv subprocess is tool-dir discovery, that every file under the temporary tool environment is byte-for-byte unchanged, and that plugin 1.0 remains installed without 2.0. This is fail-before-install handling, not transitive dependency freezing.

## RTK shared-file integration

After the focused CAO checks passed, the sequential integration task was implemented from `/home/andrew/git/ansible-workstation/tasks/rtk-install/INTEGRATION.md` and `rtk.yml.example`:

- `/home/andrew/git/ansible-workstation/ai/rtk.yml` imports common.yml for prerequisites/PATH, then invokes the existing RTK role locally as a normal user.
- `/home/andrew/git/ansible-workstation/ai/all.yml` imports rtk.yml after the client installers, with tags [rtk] and the optional rtk_enabled guard (default true).
- `/home/andrew/git/ansible-workstation/ai/README.md` documents standalone installation, reviewed version pins, latest plus explicit upgrade, the ai_stack_upgrade inheritance, checksum/source policy, shell-hook scope and the absence of live agent validation.

The RTK role files match `/home/andrew/git/ansible-workstation/tasks/rtk-shared-integration/ROLE_BASELINE.json`. No ai/roles/rtk file was edited. This shared integration is included in the round-two review scope; it does not supersede the separate review of the role itself.

## Validation

`VALIDATION.json` contains round-two argv, exit codes and full stdout/stderr. Every command returned zero:

- Syntax-check of cao.yml, cao-update.yml, rtk.yml and all.yml.
- Task listings for cao-update.yml, rtk.yml and all.yml --tags rtk. The RTK tag selects common prerequisites plus RTK tasks; CAO/server/MCP installation tasks are absent from the selected task bodies.
- **19 passing tests:** eight CAO installer tests (including canonical/alias offline integration sequences, actual Ansible script-task invocations in normal/check mode, and stored-constraint rejection) and eleven existing MCP regressions.
- Python AST parsing for the helper/test, git diff --check, and individual whitespace checks for all ten implementation diffs.
- The real uv tool list still reports cli-agent-orchestrator v2.5.4. The live receipt hash matches round one. The server remains PID 240075, started Fri Nov 13 13:42:29 2026. No session-management action was performed.

Warnings remain the implicit localhost inventory and preexisting browser/chrome.yml apt_key/apt_repository deprecations. No full workstation check/apply or live authenticated agent test was run. The isolated Ansible checks cover only the installer task; RTK integration was validated through syntax and actual task selection, using the already tested role without reapplying its fixtures.

## Existing CAO source policy retained

The configurable default remains official upstream SHA 3e30ea3ed6e7fb607b13358d81123afff5a8e69f. The recorded official source snapshots and UPSTREAM.json distinguish PyPI latest 2.5.4 from upstream code declaring the same version. The upstream consumer of decided effort applies only to ephemeral effort:auto launches; normal installed-profile delegation is not claimed to gain effort routing. No decider was installed or configured. Receipt extras/--with remain additive; unsupported resolution state requires operator review rather than automatic removal.

## Preservation and review artifacts

CHANGES.diff covers all ten implementation files against their initial originals/new-file baselines. ROUND2_CHANGES.diff isolates the six files changed in this round. FINAL_STATE.json contains current implementation hashes and the untouched RTK role hashes; FILES.json lists artifact/current-file hashes. The original report and earlier validation remain under round1/.

The initial hash capture excluded path components named tasks, including role task files. The original cao/tasks/main.yml was reconstructed from the initial full read and has no independent initial hash; this remains an explicit evidence limitation. The other preserved original files match their initial hashes. After the newly authorized all.yml integration, 55 captured baseline files outside the declared changes remain unchanged. No central-de-incidentes checkout file was edited.

Future application commands are documented in ai/README.md and were not executed. Updating the shared CAO venv still requires a maintenance window even with automatic restart disabled. A real installation and end-to-end effort routing are separate from approval of these changes.
