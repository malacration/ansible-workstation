# Independent CAO update review

**Verdict: CHANGES REQUESTED — not APPROVED.**

Two reproducible P2 correctness findings require changes. Review covers the eight files in `/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/REPORT.md`. No implementation files were modified, no workstation playbook was applied, and no real uv tool environment, CAO configuration, server, session, or worker was changed. RTK is outside this review.

## Findings

### 1. [P2] Normalize requirements before using receipt equality as the no-update boundary

Location: `/home/andrew/git/ansible-workstation/ai/roles/cao/files/install_cao.py:97` (comparison at line 100; inputs at lines 78–83).

Configured `with_packages` strings are compared directly with uv's normalized receipt strings. For example, `fixture_plugin==1.0` is a valid requirement, but uv records `fixture-plugin==1.0`. On subsequent executions, the helper adds the normalized receipt requirement to the original configured requirement, so `requested` contains both strings and cannot equal `installed`. This bypasses the early return even though the configuration is unchanged and `upgrade` is false.

This has a functional consequence beyond redundant subprocess work: the helper then invokes `uv tool install` against a moving Git branch. As its own comment explains, uv can resolve that branch without `--upgrade`. The isolated probe installed the second branch commit, with the same nominal package version, while `upgrade=False` and the original request was unchanged. The second ordinary installation also returned `changed=True`.

Evidence: an in-memory variation of `/home/andrew/git/ansible-workstation/ai/tests/test_install_cao.py:85` changed only the auxiliary requirement spelling to `fixture_plugin==1.0` and retained that configuration across the later scenarios. The existing unchanged assertion at line 88 failed with `AssertionError: True is not false`. A diagnostic continuation printed:

```text
Expected unchanged: {'changed': True, 'extras': ['memory'], 'with_count': 2}
...
Expected unchanged: {'changed': True, 'extras': ['memory'], 'with_count': 2}
Installed module after branch advanced, upgrade=False: REVISION = 'second'
```

Recommended correction: compare semantic, normalized requirements, including normalized distribution/extra names and canonical specifiers, rather than raw input strings. Deduplicate equivalent auxiliary requirements before passing them to uv. Add a regression in which an underscore alias remains configured, the branch advances without changing the package version, and an ordinary run preserves the installed commit; an explicit upgrade must still advance it.

### 2. [P2] Preserve or reject receipt-level constraints before replacing the environment

Location: `/home/andrew/git/ansible-workstation/ai/roles/cao/files/install_cao.py:75` (receipt extraction at lines 75–76 and installation command at lines 105–110).

The helper reads only `tool.requirements` when reconstructing installation requirements. A valid uv receipt can also contain `tool.constraints`. Those constraints are ignored, omitted from the subsequent uv command, and silently disappear when uv rewrites the receipt. The unknown-field validation at lines 24–27 only checks individual requirement dictionaries, so it does not reject this unsupported receipt-level state before changing the environment.

Concrete reproduction: install the fixture with `--with fixture-plugin` and `UV_CONSTRAINT` pointing to a temporary file containing `fixture-plugin==1.0`. Its receipt contains the explicit constraint. Add a local 2.0 wheel, remove the one-time environment variable, then invoke the helper with `upgrade=True`. The preserved requirement is unpinned, the declared constraint is lost, and version 2.0 is installed:

```text
Before upgrade: [{'name': 'fixture-plugin', 'specifier': '==1.0'}]
Upgrade result: {'changed': True, 'extras': ['memory'], 'with_count': 1}
After upgrade: None
Installed plugin metadata: ['fixture_plugin-2.0.dist-info']
```

This contradicts the claimed fail-before-install behavior for unsupported receipt formats and can remove an operator's compatibility pin. Recommended correction: preserve supported receipt-level constraints and other resolution-affecting state, or reject unsupported nonempty fields before invoking `uv tool install`. Add a regression proving that a stored constraint either survives an upgrade/source change or causes a pre-install failure with the receipt/environment unchanged. Do not freeze all transitive dependencies as a substitute.

## Verification and scope assessment

- Checked ancestors `/AGENTS.md`, `/home/AGENTS.md`, `/home/andrew/AGENTS.md`, `/home/andrew/git/AGENTS.md`, and repository AGENTS discovery. No applicable AGENTS file was present in the target tree. Read the provided instructions for the initial working directory. Captured `git status --short` before review work; it matches `/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/BASELINE_STATUS.txt`.
- Read `/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/REVIEW_TASK.md`, `specification.md`, `REPORT.md`, `CHANGES.diff`, `VALIDATION.json`, `UPSTREAM.json`, `PRESERVATION.json`, `FINAL_STATE.json`, `FILES.json`, the baseline copies, and relevant upstream snapshot sections. Inspected the current implementation, tests, role prerequisites, uv tasks, handler, and imported playbook.
- SHA-256 validation: all **8/8 implementation hashes** match `/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/FINAL_STATE.json`; all **31/31 manifest hashes** match `/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/FILES.json`. Regenerating each no-index diff in memory reproduces `CHANGES.diff` exactly. All **56 baseline files outside the declared edits** retain their original hashes.
- Preservation limitation remains explicit: `/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/baseline/ai/roles/cao/tasks/main.yml` has only a reconstructed original, with no independent initial hash. Its current baseline copy matches the hash in `PRESERVATION.json`, but that cannot establish its identity with the original pre-edit file. The other reconstructed originals match their captured initial hashes. This limitation is not treated as independent proof of a preservation defect.
- The Git URL/ref and PyPI version are configurable, and the default is the recorded upstream SHA `3e30ea3ed6e7fb607b13358d81123afff5a8e69f`. The snapshots distinguish PyPI 2.5.4 from upstream code also declaring 2.5.4. `/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/upstream-decisions.txt:162` and line 501 explicitly limit decided effort consumption to ephemeral `effort: "auto"` launches. The documentation does not claim normal installed-profile delegation gains effort routing.
- Ordinary pins and canonical requirements, source changes, explicit upgrades, and additive extras/`--with` preservation have useful coverage. Unknown fields within individual requirement dictionaries are rejected before tool installation. The findings identify gaps outside those tested representations.
- `/home/andrew/git/ansible-workstation/ai/roles/cao/tasks/main.yml:32` runs the helper with uv-selected Python 3.11+, avoiding the Ubuntu 22.04 system Python 3.10 `tomllib` issue. The upstream snapshot declares Python >=3.11. Actual installation of the upstream build on all supported Ubuntu architectures was not demonstrated by the fixture tests.
- `/home/andrew/git/ansible-workstation/ai/cao-update.yml:3` imports only `cao.yml`, preserving the `ai_stack` role prerequisites through CAO's metadata dependency. It does not import service/MCP management. The recorded task listing supports this. Common APT/directory preparation still runs, as documented. `cao_upgrade` is separate from uv/other-CLI upgrades unless `ai_stack_upgrade` is also enabled.
- `/home/andrew/git/ansible-workstation/ai/roles/cao/handlers/main.yml:6` adds the restart opt-in alongside service-enabled and non-check-mode guards; the default is false. Static inspection supports no automatic restart from the update playbook with defaults. No service operation was executed during this review.
- The recorded three syntax checks and task listing succeeded. The `--check` fixture covers the actual installer task being skipped without changing the receipt; it does not prove a full workstation `--check` run. The role also skips executable verification in check mode. Read-only uv version discovery is retained. No additional syntax run was necessary after matching the validated hashes.

## Test evidence and focused reproduction

`/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/VALIDATION.json` records **15 tests passed**: four installer tests and eleven existing MCP tests. The installer integration test exercises local wheels/Git, same-version commit changes, explicit upgrade, return to a SHA, additive extras/auxiliary requirements, CLI JSON, and the actual Ansible script task. These are meaningful tests, but they use canonical auxiliary names and do not cover receipt-level constraints. The whole suite was not repeated.

Review probes reused only the existing disposable integration harness, with `PYTHONDONTWRITEBYTECODE=1`, offline uv, temporary tool/bin/cache directories, and source transformations in memory. No test source was edited. The diagnostic continuation replaces selected assertions with observations; its runner's `OK` is not evidence that the original invariant passed.

The following reproduces the branch observation and constraint loss without changing repository files. It runs two focused variations, not the full suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from pathlib import Path
import unittest

path = Path('/home/andrew/git/ansible-workstation/ai/tests/test_install_cao.py')
original = path.read_text()
method = 'test_install_repeat_pin_upgrade_and_git_source_preserve_extras'

alias = original.replace("'with_packages': ['fixture-plugin==1.0']",
                         "'with_packages': ['fixture_plugin==1.0']")
alias = alias.replace('config.update(extras=[], with_packages=[], upgrade=True)',
                      'config.update(extras=[], upgrade=True)')
alias = alias.replace("self.assertFalse(installer.install(uv, config)['changed'])",
                      "print('Expected unchanged:', installer.install(uv, config))")
alias = alias.replace(
    "                config['upgrade'] = True\n"
    "                self.assertTrue(installer.install(uv, config)['changed'])\n"
    "                config['spec']",
    "                print('Module after branch advance with upgrade=False:', "
    "next((root / 'tools').rglob('cli_agent_orchestrator.py')).read_text())\n"
    "                return\n"
    "                config['upgrade'] = True\n"
    "                self.assertTrue(installer.install(uv, config)['changed'])\n"
    "                config['spec']")

constraints = original.replace(
    "            uv = shutil.which('uv')",
    "            (root / 'constraints.txt').write_text('fixture-plugin==1.0')\n"
    "            env['UV_CONSTRAINT'] = str(root / 'constraints.txt')\n"
    "            uv = shutil.which('uv')")
constraints = constraints.replace("'with_packages': ['fixture-plugin==1.0']",
                                  "'with_packages': ['fixture-plugin']")
constraints = constraints.replace(
    "                self.assertTrue(installer.install(uv, config)['changed'])",
    """                self.assertTrue(installer.install(uv, config)['changed'])
                receipt_path = root / 'tools/cli-agent-orchestrator/uv-receipt.toml'
                print('Before:', tomllib.loads(receipt_path.read_text())['tool'].get('constraints'))
                wheel(wheels, 'fixture_plugin', '2.0')
                os.environ.pop('UV_CONSTRAINT')
                config['upgrade'] = True
                print('Upgrade:', installer.install(uv, config))
                print('After:', tomllib.loads(receipt_path.read_text())['tool'].get('constraints'))
                print('Plugin:', [p.name for p in (root / 'tools').rglob('fixture_plugin-*.dist-info')])
                return""", 1)

for label, source in [('alias', alias), ('constraints', constraints)]:
    namespace = {'__file__': str(path), '__name__': 'review_' + label}
    exec(compile(source, str(path), 'exec'), namespace)
    suite = unittest.TestSuite([namespace['IsolatedInstallTests'](method)])
    unittest.TextTestRunner(verbosity=2).run(suite)
PY
```

Approval is withheld for the code at the recorded hashes. This review makes no claim of a real installation or end-to-end effort-routing validation.
