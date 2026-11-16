# RTK live application handoff

Status: final independent review approved. A read-only preflight found RTK OSS
1.2.0 already installed and configured. The supervisor will coordinate any
bounded reconciliation; this worker did not apply the live playbook in this turn.

The exact bounded command, from `/home/andrew/git/ansible-workstation`, is:

```bash
ansible-playbook ai/rtk.yml --tags rtk --skip-tags ai_common -e ai_stack_user=andrew -e ai_stack_home=/home/andrew -e rtk_version=1.2.0 -e rtk_upgrade=false -e ai_stack_upgrade=false
```

The task listing showed only RTK tasks; the common prerequisite play contained
no selected tasks. Explicit `ai_stack_home` supplies the value normally obtained
by the skipped common role. Run as `andrew`; the checked destination directories
are user-owned and writable, so no sudo or `-K` is needed for this bounded run.
Python 3, tar, gzip, Git and CA certificates were present. The pinned official
release API returned 200 and its x86_64 OSS asset digest matched the reviewed pin.
If the already-verified installation remains valid, no release refresh is needed.

Read-only state summary: the public wrapper is `/home/andrew/.local/bin/rtk` and
matches the reviewed telemetry-disabling template. The regular nonsymlink managed
binary at `/home/andrew/.local/share/ai-stack/rtk/bin/rtk` matches its supported
receipt and has SHA256 `4625c86e6eab82911e25a340657450e9d45a3e992871580946e25e7a3f20bca7`.
The receipt records official OSS 1.2.0. Each global client has one native RTK
PreToolUse hook, with no change required by the merge calculation; instruction
files contain managed RTK blocks. Existing unrelated JSON was not printed.
The eight reviewed role files still match the final-review fingerprints.

Provenance requires care: an initial read-only preflight observed the binary,
receipt and global RTK hook/instruction files absent; the later preflight found
them present. `/home/andrew/.codex/AGENTS.md` and
`/home/andrew/.claude/CLAUDE.md` have managed-block mtimes at approximately
2026-11-16 14:19:17 UTC. The central-de-incidentes repository AGENTS file does
not contain that block. The actor responsible for the intervening live change
has not been established; do not claim the HOME remained untouched or attribute
the change to a particular worker without further evidence.

The retained initial Claude and Codex probe outputs identify task-local
`probe-home` paths. The Codex probe explicitly set CODEX_HOME and
CLAUDE_CONFIG_DIR to fixture paths. The current inherited overrides are unset;
the initial inherited values were not recorded. The actual role's configure
helper uses a fresh staging environment with explicit HOME, CODEX_HOME,
CLAUDE_CONFIG_DIR and XDG paths; the isolated Ansible fixture asserts its own
home. These observations support fixture isolation but do not independently
prove who created the live files. Preserve the live files and existing backups.

After supervisor-authorized reconciliation, verify without restarting sessions:

```bash
rtk --version
rtk gain
```

Inspect only hook summaries rather than printing private settings; confirm one
native `rtk hook claude` and `rtk hook codex` PreToolUse entry, matching the
public wrapper, and preserve unrelated entries. Exercise `rtk git status` and
`rtk bypass git status` in a disposable local Git repository. Repeat the bounded
playbook and require `changed=0`. Record actual results and the CAO/session
baseline before claiming live validation or preservation.

The separate Chrome failure reports a failed APT cache refresh but omits the APT
cause. It is outside the bounded RTK command, which skips common prerequisites
and does not invoke the Chrome play. Diagnose that APT error separately without
changing repository/package configuration as part of RTK reconciliation.
