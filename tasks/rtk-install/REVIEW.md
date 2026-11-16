# Independent RTK role review

**Verdict: CHANGES REQUESTED — not APPROVED.**

Two concrete P2 findings require correction. This review covers only `/home/andrew/git/ansible-workstation/ai/roles/rtk/` and its evidence under `/home/andrew/git/ansible-workstation/tasks/rtk-install/`. Unfinished CAO changes and shared integration are excluded. No implementation was modified, no live installation was applied, and no agent/server/session was started or restarted.

## 1. [P2] Gate execution of the installed binary on receipt integrity

Location: `/home/andrew/git/ansible-workstation/ai/roles/rtk/tasks/main.yml:45` through line 51; checksum comparison currently occurs later at line 58.

The role obtains the installed executable's checksum, then unconditionally executes that executable with `--version`. Only afterward does it compare the checksum with `release.json` and decide to reconcile. Therefore, a missing/mismatched integrity record does not prevent execution of an altered executable. `check_mode: false` also causes this execution during `--check`.

A focused offline fixture copied the actual stat, version, and release-decision tasks into a temporary playbook. Its temporary executable was a harmless shell script that wrote a temporary marker and printed `rtk 1.2.0`; its checksum intentionally differed from the receipt. Running those tasks with `--check` produced:

```text
Exit: 0
Checksum differs from receipt: True
Altered binary executed during --check: True
rtk_needs_release: true
localhost : ok=4 changed=0 unreachable=0 failed=0
```

The role detects the mismatch, but the detection is too late to serve as an execution boundary. An altered executable can perform side effects or hang before recovery begins. This finding concerns the existing executable; the downloaded candidate already receives archive verification before its version probe.

**Requested correction:** establish receipt/binary validity before the installed version command. Skip execution when the file is missing, is a symlink/nonregular file, or lacks a matching supported receipt/hash. Treat those cases as requiring release reconciliation, and handle skipped version results without undefined-variable errors. Preserve the ability to probe and retain a verified installed release without a network request. Add a regression proving that a mismatched executable's marker is never written in either ordinary or check mode.

## 2. [P2] Recognize native RTK hooks at previous absolute paths

Location: `/home/andrew/git/ansible-workstation/ai/roles/rtk/files/configure_rtk.py:57` through line 58, used by `merge_hooks` at line 92.

`is_rtk_hook` recognizes only the bare command `rtk` or the exact currently requested wrapper path. An existing native hook such as `/old/install/bin/rtk hook codex` is treated as unrelated when the new wrapper is `/new/install/bin/rtk`. The merger preserves the old hook and appends another one. This occurs when adopting an existing absolute-path installation or changing the supported `rtk_binary` setting after an earlier run.

The pure-function reproduction returned both commands:

```text
/old/install/bin/rtk hook codex
/new/install/bin/rtk hook codex
```

This bypasses duplicate/custom-matcher protection for the old path. Both hooks can be invoked for the same shell event; the old executable can also be stale or unavailable. The current tests cover bare `rtk` and the current path, but omit a previous absolute path. The retained official source also recognizes absolute native paths: `/home/andrew/git/ansible-workstation/tasks/rtk-install/upstream-src-hooks-init-codex.rs:993`, with an explicit absolute-path test at line 1022.

**Requested correction:** identify unambiguous native RTK hook commands independently of the new wrapper location. Migrate one recognized old native hook to the managed wrapper, or reject it before writing when ownership is ambiguous. Count duplicates and enforce matcher checks across old/current/bare native paths while preserving unrelated commands. Add regressions for adopting an old absolute path, relocating the wrapper after configuration, and duplicates mixing old/current paths.

## Focused reproductions

The following reproduces both findings without downloading anything or changing repository source. The Ansible invocation contains only three copied role tasks plus a diagnostic; it does not apply the role or any workstation playbook. All writable fixture paths are temporary.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shlex
import subprocess
import tempfile
import yaml

role = Path('/home/andrew/git/ansible-workstation/ai/roles/rtk')
spec = importlib.util.spec_from_file_location('rtk_review', role / 'files/configure_rtk.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def hooks(command):
    return {'hooks': {'PreToolUse': [{'matcher': 'Bash', 'hooks': [
        {'type': 'command', 'command': command}]}]}}

merged = module.merge_hooks(
    hooks('/old/install/bin/rtk hook codex'), hooks('rtk hook codex'),
    'codex', Path('/new/install/bin/rtk'))
print('Merged hooks:', json.dumps(merged))

source = yaml.safe_load((role / 'tasks/main.yml').read_text())
block = next(task['block'] for task in source if 'block' in task)
names = ['Conferir integridade atual do executável gerenciado',
         'Verificar versão do binário gerenciado',
         'Definir necessidade de consultar release']
tasks = [next(task for task in block if task['name'] == name) for name in names]
with tempfile.TemporaryDirectory(prefix='rtk-integrity-review-') as temporary:
    root = Path(temporary)
    install = root / 'install'
    (install / 'bin').mkdir(parents=True)
    marker = root / 'unexpected-version-execution'
    binary = install / 'bin/rtk'
    binary.write_text('#!/bin/sh\nprintf executed > ' + shlex.quote(str(marker))
                      + '\nprintf "rtk 1.2.0\\n"\n')
    binary.chmod(0o755)
    expected = hashlib.sha256(b'original verified release bytes').hexdigest()
    play = root / 'probe.yml'
    play.write_text(yaml.safe_dump([{
        'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
        'vars': {
            'rtk_install_dir': str(install),
            'rtk_receipt': {'edition': 'oss', 'version': '1.2.0',
                            'binary_sha256': expected},
            'rtk_version': '1.2.0', 'rtk_upgrade': False, 'rtk_checksum': '',
            'ansible_facts': {'architecture': 'x86_64'},
        },
        'tasks': tasks + [{'ansible.builtin.debug': {'var': 'rtk_needs_release'}}],
    }], sort_keys=False))
    environment = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(root / 'local'),
                       ANSIBLE_REMOTE_TEMP=str(root / 'remote'), ANSIBLE_NOCOLOR='1')
    result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play), '--check'],
                            env=environment, cwd=root, capture_output=True, text=True)
    print('Exit:', result.returncode)
    print('Checksum differs from receipt:',
          hashlib.sha256(binary.read_bytes()).hexdigest() != expected)
    print('Altered binary executed during --check:', marker.exists())
    print(result.stdout[result.stdout.find('TASK [ansible.builtin.debug]'):])
PY
```

## Other review conclusions and evidence

- Read `/home/andrew/git/ansible-workstation/tasks/rtk-install/REVIEW_TASK.md` and its listed role/test/handoff files, relevant official source snapshots, release metadata, checksums, validation records, and logs. No applicable target/ancestor AGENTS instructions were found; AGENTS files generated inside fixture homes do not govern the role. The review did not access prohibited secret paths.
- All **16 source/deliverable entries** in `/home/andrew/git/ansible-workstation/tasks/rtk-install/IMPLEMENTATION.diff` match their current new-file contents. The role did not exist at the recorded preflight. No shared source files were edited during this review, and no conclusion here attributes concurrent shared/CAO work to the RTK developer.
- Independently hashed the retained `checksums.txt`, x86_64 OSS archive, and extracted executable. They match the report and GitHub asset digests: manifest `cb6c58f0a063ee1ec2313d61d3ba7da6b4af95edf7a333739a692c099af4f48e`, archive `a28407dc13038bdc9c2a1f5a047b0c636e0c1d495b15523576e2adb992a06a17`, binary `4625c86e6eab82911e25a340657450e9d45a3e992871580946e25e7a3f20bca7`. The archive contains `rtk` and `LICENSE`; the binary matches its archived bytes and ELF machine 62. Recorded metadata identifies stable official v1.2.0, published 2026-11-08.
- `/home/andrew/git/ansible-workstation/ai/roles/rtk/tasks/release.yml:35` requires a unique manifest checksum and verifies optional/audited pins and available asset digest. `get_url` verifies archive contents before extraction/execution; the candidate's declared version is checked before atomic publication. Static inspection supports missing-checksum rejection before replacing the installed executable. The recorded wrong-checksum run fails before publication with `changed=0`; the validation runner additionally checks the existing binary hash is unchanged.
- Linux x86_64/aarch64 selection uses OSS musl assets and rejects unsupported architectures. `/home/andrew/git/ansible-workstation/tasks/rtk-install/ARCHITECTURE_VERIFICATION.json` records the ARM64 archive checksum and ELF machine 183. ARM64 execution was not performed; this review did not independently execute or re-download ARM64 artifacts.
- Pin changes reconcile immediately. `latest` retains a valid managed installation without contacting the API until an explicit refresh. The recorded unreachable-API case retained 1.1.0 unchanged; explicit upgrade installed 1.2.0. `rtk_upgrade` inherits `ai_stack_upgrade`. Explicit refresh can report staging changes even for the same release, as documented. Finding 1 limits the integrity behavior of this otherwise useful receipt mechanism.
- `/home/andrew/git/ansible-workstation/ai/roles/rtk/files/configure_rtk.py:145` constructs an empty temporary HOME and a fresh environment with CODEX_HOME, CLAUDE_CONFIG_DIR, XDG overrides, telemetry disabled and onboarding disabled. Claude receives `--auto-patch --no-trust-filters`; Codex receives `--codex --no-trust-filters` without the rejected flag. Init does not receive copies of live client settings.
- The merger preserves unrelated JSON fields and hooks, backs up changed originals before writing configs, retains destination modes, and validates integration paths/backups against symlinks. It stages both clients' proposals before writing, so a malformed second client prevents partial configuration. It imports Claude awareness through `@RTK.md` and provides inline Codex awareness. The intended files exclude client config.toml, authentication, MCP definitions, sandbox permissions, and existing RTK configuration/filter files. Finding 2 limits native-hook adoption and duplicate detection.
- The public wrapper exports `RTK_TELEMETRY_DISABLED=1` and `RTK_ONRAMP_DISABLED=1`. The retained source checks telemetry opt-out before loading configuration/transmission and checks the onboarding opt-out. Recorded native-hook, telemetry-enabled-config, local Git filter and bypass checks support the wrapper behavior. No proxy binary, service, provider URL change, remote pipeline or telemetry enablement was introduced. Direct use of the private binary and client PATH requirements remain documented operational limits.
- The handoff imports `common.yml` and then the standalone role, matching the existing stack prerequisites without adding an implicit system dependency to isolated role tests. Shared entrypoint/all.yml/documentation integration belongs to the designated owner and is not a defect in this review.

## Test credibility and limits

`/home/andrew/git/ansible-workstation/tasks/rtk-install/unit-tests.log` records **13 passed tests**. They meaningfully exercise merge preservation, ordinary duplicate/legacy/malformed handling, symlinks, backups, repeat idempotence, isolated real-release init and realistic native hook payloads. The validation logs/runner support initial installation, repeated `changed=0`, existing/empty check mode, explicit version transition, offline latest retention and checksum rejection. They do not cover an altered installed executable being run before checksum rejection, or native hooks at previous absolute paths.

The full suite and download/install validation runner were not repeated. Only the two focused offline probes above were performed. No authenticated client session or live end-to-end hook interception was tested, ARM64 was not executed, and ansible-lint was unavailable in the recorded implementation validation. These documented limits are distinct from the two actionable code findings.

Reviewed role SHA-256 fingerprints:

| Absolute path | SHA-256 |
| --- | --- |
| `/home/andrew/git/ansible-workstation/ai/roles/rtk/README.md` | `220607c54397bcb40bf7e9b3af1d526d31ea04414f978c1d09796b969a4c9f32` |
| `/home/andrew/git/ansible-workstation/ai/roles/rtk/defaults/main.yml` | `4b8de896291e401d0ac56dded59ca31a0f9d30609d36381e87958b70fefbe324` |
| `/home/andrew/git/ansible-workstation/ai/roles/rtk/tasks/main.yml` | `c5f88519cb7026fad223bc42422e4365aa8cb092be6916d6d2322969c621488b` |
| `/home/andrew/git/ansible-workstation/ai/roles/rtk/tasks/release.yml` | `3cef9f9aa0f650ee141373d0a41b1fe772603b16237ee5f10f0d0df3b46f4a19` |
| `/home/andrew/git/ansible-workstation/ai/roles/rtk/files/configure_rtk.py` | `e2defa61670989efcb42a1082f14bc765e273b8577ccfe4e22b1f5c132a8a5e5` |
| `/home/andrew/git/ansible-workstation/ai/roles/rtk/templates/rtk.j2` | `f8dccc91f4854d1fcba4b91576d95d1de75e658d4e8be11c96f420737d710968` |
| `/home/andrew/git/ansible-workstation/ai/roles/rtk/meta/main.yml` | `40c407353bdc672aa412bc39317c5c1cab145fda4d1eaa2c17f9cad1da397b52` |
