# RTK implementation and isolated validation

Status: round-two corrections complete for independent re-review. No real-HOME installation was applied.
Only `ai/roles/rtk/` and `tasks/rtk-install/` were written by this worker. No shared
playbook, README, ai_stack role, CAO code, index entry or pre-existing user edit
was modified by this worker. No client/server/session was restarted.

## Source and release verification

Official latest redirected to https://github.com/rtk-ai/rtk/releases/tag/v1.2.0
on 2026-11-16. GitHub metadata reports publication on 2026-11-08. The role defaults
to the reviewed pin `1.2.0`; `latest` remains available with explicit updates.

Selected edition: `rtk-oss`, containing local shell filters/native hooks without
the engine. No installer script was executed. Downloads were taken from the
official release, checked against `checksums.txt`, GitHub asset digests and the
role's audited pins. The role also accepts an additional explicit archive pin.

| Asset | SHA256 |
| --- | --- |
| checksums.txt | cb6c58f0a063ee1ec2313d61d3ba7da6b4af95edf7a333739a692c099af4f48e |
| rtk-oss-x86_64-unknown-linux-musl.tar.gz | a28407dc13038bdc9c2a1f5a047b0c636e0c1d495b15523576e2adb992a06a17 |
| rtk-oss-aarch64-unknown-linux-musl.tar.gz | 9786c61dbbea704e1468ee7060930d3b45b67f79ba2babfb73463e85340628d9 |

The x86_64 executable reports `rtk 1.2.0`; its ELF machine is 62 and SHA256 is
`4625c86e6eab82911e25a340657450e9d45a3e992871580946e25e7a3f20bca7`.
ARM64 archive content/checksum and ELF machine 183 were verified; ARM64 execution
was not attempted on this x86_64 host.

The real release accepts `init -g --no-trust-filters --auto-patch` for Claude and
`init -g --no-trust-filters --codex` for Codex. Codex rejects `--auto-patch`.
Source snapshots from the v1.2.0 tag and actual CLI output are retained in this
task directory. Master-only behavior was not assumed.

## Round-two corrections

The written correction task is
`/home/andrew/git/ansible-workstation/tasks/rtk-install/REVIEW.md`.
Both P2 findings are addressed; the original review has been preserved.

1. Installed execution is now gated by `installed_state.py`, a trusted source
   utility that never executes RTK. It requires a supported regular nonsymlink
   receipt and a regular nonsymlink executable with matching SHA256 and executable
   permissions. Missing/malformed/unsupported receipts, invalid file types,
   missing binaries and mismatches skip --version and require reconciliation.
   This gate also runs in check mode. Skipped version results use safe defaults.
   A verified installation still gets a version probe and can stay offline.
   The role validates published integrity again immediately before running init.
   Downloaded candidates must be regular nonsymlink executables before probing.
   Nonregular publication destinations are preserved by rename; regular files
   use Ansible backups. Symlink targets are not changed. Unsafe parent paths
   fail before filesystem writes rather than being followed.
2. Native RTK hook recognition now covers bare/current commands and exact
   commands at previous absolute paths ending in `rtk`, including quoted paths.
   One hook migrates in place to the new wrapper. Duplicate and matcher guards
   cover all those spellings. Unknown path-shaped native commands, including
   arbitrarily named previous wrappers, and native commands with extra flags
   are rejected before any client config write for manual review. Unrelated
   commands/events/settings remain intact. Full configure tests verify relocation,
   repeat idempotence and no partial writes across clients on ambiguous input.

No runtime/update variable defaults or shared integration files were changed.
The wrapper's parent directory is now created from `rtk_binary`, so relocation
can use a newly selected bin directory. Existing source/preference behavior,
telemetry opt-out and noninteractive init flags are retained.

## Implemented behavior

The role installs a checksum-validated candidate and verifies its declared
version before copying it atomically into the managed bin directory. A receipt
records archive and executable SHA256, edition, source and version. Pin changes,
missing receipts, altered binaries or changed optional checksum pins trigger
reconciliation. `latest` does not query the network without explicit upgrade.
`rtk_upgrade` inherits the shared `ai_stack_upgrade` convention.

The public wrapper blocks telemetry and proxy onboarding with the upstream
supported environment variables. Existing RTK config/filters are not read or
rewritten. No proxy binary, service, remote pipeline or provider URL was added.

The merger invokes real init inside an empty temporary HOME and merges only the
native hook and awareness text into the selected destination files. It preserves
unrelated JSON values/hooks, existing instruction text and file modes; originals
receive private content-addressed backups. It refuses ambiguous legacy/duplicate
hooks, malformed input or symlinked integration paths before changing configs.
Codex config.toml, auth, MCPs, sandbox permissions and writable roots are untouched.

## Validation evidence

All commands below use absolute task paths or the supplied guarded fixture:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s /home/andrew/git/ansible-workstation/tasks/rtk-install -p 'test_*.py' -v
python3 /home/andrew/git/ansible-workstation/tasks/rtk-install/validate_ansible.py
PYTHONDONTWRITEBYTECODE=1 python3 /home/andrew/git/ansible-workstation/tasks/rtk-install/validate_recovery.py
ansible-playbook /home/andrew/git/ansible-workstation/tasks/rtk-install/isolated-empty.yml --check --diff
```

- 29 unit/integration tests passed in round two. They cover preserving existing hooks,
  permissions, configs/instructions and backups; idempotence; invalid schemas,
  duplicate/legacy hooks, malformed markers, symlinks, dry-run/no partial changes;
  actual Claude/Codex hook rewrites and telemetry opt-out even with consent enabled.
- Ansible syntax passed. First isolated install passed. Second/final runs and
  existing-install check mode all reported `changed=0`.
- Clean-install check mode passed with predicted changes and no installation.
- A real pinned 1.1.0 install passed. `latest` with an intentionally unreachable
  API retained 1.1.0 with `changed=0`, proving no implicit refresh.
- Explicit upgrade resolved latest and installed 1.2.0 successfully.
- A wrong explicit checksum failed at the checksum assertion (`failed=1`, expected),
  and the already installed executable SHA256 stayed unchanged.
- The installed wrapper ran the local Git status filter and bypass successfully
  in a disposable repository. Telemetry status reported the environment block.
- ARM64 archive checksum/ELF validation passed, without cross-architecture execution.

Round-two evidence:

- `all-tests-round2.log`: 29 passing tests (19 hook/config, 10 state/gate tests).
- `EXECUTION_GATE_RESULTS.json`: 20 offline runs of the actual role inspection,
  version and release-decision tasks: normal/check modes, each with nine invalid
  states and one verified positive control. Invalid states never wrote an
  execution marker; only the matching supported positive control executed.
- `ansible-validation-round2.log` and `VALIDATION_RESULTS.json`: existing syntax,
  version/upgrade/offline/idempotence/checksum checks rerun successfully against
  official releases before the public GitHub API quota was exhausted.
- `recovery-validation-round2.log` and `RECOVERY_RESULTS.json`: full guarded role
  checks for mismatched binary, symlink binary, directory binary and malformed
  receipt. Check mode preserves invalid state without executing it; normal mode
  publishes a verified replacement. Symlink targets and directory content are
  retained. Final ordinary/check runs report changed=0.
- `ansible-final-round2-idempotence.log` / `ansible-final-round2-check.log`:
  idempotence of the final helper source, with no release refresh required.
- `ansible-check-empty-round2.log`: clean-install check mode rerun.

The initial networked symlink-recovery attempt reached GitHub's public API rate
limit (403) after correctly skipping the invalid executable. That failure log
is retained as `recovery-symlink-normal-github-rate-limit.log`. Recovery validation
then completed using a temporary localhost download fixture serving only the
retained official metadata/manifest/archive after verifying their recorded
SHA256 digests. It forwards no agent traffic, changes no production endpoint and
is shut down at test completion. The final fixture receipt source is consequently
a localhost URL; this belongs only to the guarded test HOME.

`IMPLEMENTATION.diff` contains the current deliverables; `IMPLEMENTATION.round1.diff`
preserves the original review baseline, and `ROUND2.diff` isolates corrections
against that baseline. `ROUND2_EVIDENCE.json` records final checks and fingerprints.
Existing-check recaps are in `VALIDATION_RESULTS.json`; output is in the named logs.
Ansible-lint is not installed in this environment. Syntax, real isolated runs and
negative checksum validation were used. The role and tests require only the
existing stack prerequisites and Python standard library.

## Scope and operational limits

The guarded Ansible fixture used only:
`/home/andrew/git/ansible-workstation/tasks/rtk-install/ansible-home/`.
The initial binary/init probes used `probe-home/` in that same task directory;
unit tests used disposable temporary HOMEs. The native-hook tests exercised
actual release processors with realistic event payloads. No newly launched,
authenticated Claude/Codex/CAO session was used. Installed Codex CLI reported
0.169.0. Native client hook support is required for automatic shell interception;
inline instructions provide explicit RTK usage guidance. Built-in non-shell
and MCP tools do not pass through this filter.

Check mode does not execute init or download/install a release. It reports that
integration merging occurs on a real run. Removing a client from rtk_clients
stops managing it without uninstalling previously configured hooks. Existing
RTK local usage/recovery storage policy is retained. The managed public command,
not direct invocation of the private binary, enforces the telemetry opt-out.

No blocker remains for the round-two implementation/re-review handoff. Shared-file
integration and real-HOME application remain assigned to the supervisor/CAO
owner after review. Follow `INTEGRATION.md`; do not apply the whole workstation
playbook or restart active sessions as part of this RTK task.
