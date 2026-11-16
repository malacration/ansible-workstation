# RTK local shell filtering

This role installs the official `rtk-oss` release for Linux x86_64 or aarch64
(musl), checks its SHA256 before executing it, and integrates its native
PreToolUse hooks with Claude Code and Codex. No proxy binary, service, remote
pipeline, API routing or telemetry is enabled.

Import `ai/common.yml` from the calling playbook first. This role uses the
existing `ai_stack_user`, `ai_stack_home`, `ai_stack_bin_dir`,
`ai_stack_cache_dir` and `ai_stack_environment` variables. It deliberately has
no implicit system dependency role, allowing isolated validation without APT,
shell startup changes or access to the real user's client settings.

| Variable | Default | Behavior |
| --- | --- | --- |
| `rtk_version` | `'1.2.0'` | Audited release pin, or `latest` |
| `rtk_upgrade` | `ai_stack_upgrade`, otherwise `false` | Explicit release refresh |
| `rtk_clients` | `[claude_code, codex]` | Clients whose global hooks/instructions are merged |
| `rtk_install_dir` | `{{ ai_stack_home }}/.local/share/ai-stack/rtk` | Private binary, helper and release receipt |
| `rtk_binary` | `{{ ai_stack_bin_dir }}/rtk` | Public wrapper with mandatory telemetry opt-out |
| `rtk_claude_dir` | `{{ ai_stack_home }}/.claude` | Claude global settings/instructions directory |
| `rtk_codex_dir` | `{{ ai_stack_home }}/.codex` | Codex global hooks/instructions directory |
| `rtk_checksum` | empty | Optional additional `sha256:HEX` archive pin |
| `rtk_audited_checksums` | v1.2.0 Linux x86_64/aarch64 | Reviewed pins, checked against the official manifest |
| `rtk_release_api` | GitHub RTK releases API | Metadata endpoint; override only for a trusted mirror/test fixture |
| `rtk_release_download_url` | Official GitHub release download URL | Asset/manifest base URL |

A pinned version change reconciles immediately. `latest` retains the installed
managed release without network access until `rtk_upgrade=true` or
`ai_stack_upgrade=true`. A missing receipt, altered binary or changed explicit
checksum forces verification/reconciliation. The receipt records edition,
version, architecture-specific asset, source URL, archive SHA256 and executable
SHA256. A deliberate refresh may report changed temporary staging tasks even
when the remote release has not changed.

Before an installed binary is executed, `installed_state.py` requires a regular
nonsymlink receipt with the supported edition/version/asset/hash fields and a
regular nonsymlink executable matching its recorded SHA256. Missing, malformed,
unsupported or mismatched state skips `--version` and requires reconciliation,
including in check mode. The role checks published integrity again before init.
Unsafe directory ancestors fail before filesystem writes. Nonregular binary,
receipt or wrapper destinations are preserved by rename to
`FILE.rtk-invalid-UUID` before publication; symlink targets are not followed or
changed. Regular overwritten files use Ansible backups. The downloaded candidate
also must be a regular nonsymlink executable before its version is probed.

The public wrapper exports `RTK_TELEMETRY_DISABLED=1` and
`RTK_ONRAMP_DISABLED=1` on every call. Existing RTK configuration files remain
untouched, including an existing telemetry preference; the environment override
blocks transmission through the managed command regardless of that preference.
The raw executable in the private install directory is not the public entrypoint.
RTK's local usage/recovery storage follows its existing config/defaults.

`configure_rtk.py` invokes the installed release's real `init` in a temporary,
empty HOME, with explicit CODEX_HOME, CLAUDE_CONFIG_DIR and XDG overrides. For
v1.2.0 the supported calls are:

```text
rtk init -g --no-trust-filters --auto-patch
rtk init -g --no-trust-filters --codex
```

Codex rejects `--auto-patch`. Only the generated PreToolUse hook and awareness
text are used; generated filters, permissions and other files are not copied.
No existing custom filters are trusted automatically.

The merger reads only selected `settings.json`/`hooks.json`, `CLAUDE.md`/
`AGENTS.md` and `RTK.md`. It retains unrelated JSON fields, hooks and instruction
text; its instruction text lives between `BEGIN/END ANSIBLE RTK` markers. A
native existing `rtk hook CLIENT` or `/previous/path/rtk hook CLIENT` is updated
to the public absolute wrapper path, including quoted paths with spaces.
Duplicate and matcher guards cover bare, previous absolute and current paths.
A native-shaped hook at an unknown custom executable path (for example a
previous arbitrarily named wrapper), or a native RTK command with extra flags,
is rejected before any client configuration write for manual review. Unrelated
commands/events/JSON values are retained. Legacy rewrite scripts, duplicate RTK
hooks, custom RTK matchers, malformed
JSON/markers or symlinked paths fail before user configuration is changed.
Existing files are backed up as `FILE.rtk-backup.FULL_SHA256`, with mode 0600;
existing file modes are retained. JSON formatting can change on the first merge.

Claude receives the release's awareness through `@RTK.md`. Codex receives inline
awareness and explicit `rtk` usage guidance in its managed AGENTS.md block, so it
does not depend on Markdown import behavior. Client config.toml, MCPs, auth,
permission settings and sandbox writable roots are not rewritten. The hook
commands use the absolute wrapper path; rewritten commands use `rtk` from PATH,
so retain the stack's `~/.local/bin` PATH setup when launching clients/CAO.

The integration requires clients supporting native PreToolUse hooks and input
rewrites. The installed Codex CLI was 0.169.0 during validation; tests cover the
release's native hook processors with actual event payloads, not a newly
launched authenticated agent session. Built-in Read/Grep/Glob tools and MCP
responses are outside this shell filter's scope. Existing CAO sessions are not
restarted. New client sessions load the changed global hooks/instructions.

Removing a client from `rtk_clients` stops managing that client's files; it does
not uninstall its previously installed hook. `--check` predicts binary/template
changes without downloads or init; integration merging is validated during an
actual run. The helper offers a separate `--check` once the binary is present.

Validation and the handoff plan are under
`/home/andrew/git/ansible-workstation/tasks/rtk-install/`.

Official references:

- https://github.com/rtk-ai/rtk/releases/tag/v1.2.0
- https://github.com/rtk-ai/rtk/blob/v1.2.0/src/hooks/init/claude.rs
- https://github.com/rtk-ai/rtk/blob/v1.2.0/src/hooks/init/codex.rs
- https://github.com/rtk-ai/rtk/blob/v1.2.0/src/core/telemetry_cmd.rs
- https://github.com/rtk-ai/rtk/blob/v1.2.0/src/hooks/hook_cmd.rs
