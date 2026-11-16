# Independent CAO round-two and RTK shared-integration review

**Combined verdict: CHANGES REQUESTED — one remaining P1 integration finding.**

**The two first-round CAO P2 findings are resolved; their corrections are APPROVED within this review's scope.** The new RTK entrypoint needs the correction below before the combined change can be approved. The RTK role implementation and its separate correction cycle are outside this review.

No implementation was edited, no live installation/playbook was applied, and no server/session was restarted or worker launched. `/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/REVIEW.md` remains the unchanged first-round review.

## Remaining finding

### [P1] Supply shared stack defaults in the play that runs RTK

Location: `/home/andrew/git/ansible-workstation/ai/rtk.yml:6` through line 13; prerequisite import at line 3.

`common.yml` runs the `ai_stack` role in a separate play. Its role defaults are available in that first play, but do not become host facts or carry into the second play. The RTK play includes only the `rtk` role, whose empty dependency list intentionally relies on the caller to supply stack variables. Consequently, default standalone execution reaches RTK without `ai_stack_home`, `ai_stack_user`, `ai_stack_bin_dir`, `ai_stack_cache_dir`, or `ai_stack_environment`. Referencing them fails before RTK installation can proceed. Importing the entrypoint from `/home/andrew/git/ansible-workstation/ai/all.yml:15` has the same problem.

`ai_stack`'s prerequisite tasks gather account information but do not export these defaults with `set_fact`. The existing syntax checks and task listings cannot detect missing variables that are evaluated only when tasks execute. The role's earlier isolated fixture explicitly supplied all five variables and therefore cannot validate this new entrypoint's variable scope.

**Requested correction:** make the shared defaults available explicitly in the RTK play, for example through an appropriate `vars_files` reference to `/home/andrew/git/ansible-workstation/ai/roles/ai_stack/defaults/main.yml`, while retaining the prerequisite play. Alternatively, execute prerequisites and RTK in a shared play scope. This can be fixed in the shared entrypoint without editing the separately owned RTK role. Add a focused assertion that the actual second play resolves the required stack variables with ordinary defaults; do not apply the real installation to validate this.

### Read-only reproduction

This loads the actual entrypoint and asks Ansible for each play's variables. It executes no tasks, performs no downloads, and changes no workstation configuration:

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 - <<'PY'
from ansible.plugins.loader import init_plugin_loader
init_plugin_loader()
from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager
from ansible.vars.manager import VariableManager
from ansible.playbook import Playbook

loader = DataLoader()
inventory = InventoryManager(loader=loader, sources=['localhost,'])
manager = VariableManager(loader=loader, inventory=inventory)
playbook = Playbook.load('/home/andrew/git/ansible-workstation/ai/rtk.yml',
                         loader=loader, variable_manager=manager)
names = ['ai_stack_user', 'ai_stack_home', 'ai_stack_bin_dir',
         'ai_stack_cache_dir', 'ai_stack_environment']
for play in playbook.get_plays():
    variables = manager.get_vars(play=play, host=inventory.get_host('localhost'))
    print(play.get_name(), {name: name in variables for name in names})
PY
```

Observed result:

```text
Preparar Ubuntu para a stack de IA
  ai_stack_user/home/bin_dir/cache_dir/environment: all present
Install RTK OSS local shell filtering
  ai_stack_user/home/bin_dir/cache_dir/environment: all absent
```

`/usr/bin/python3` is the interpreter with the installed Ansible modules on this workstation. The default `python3` used by other fixtures does not have Ansible installed. This interpreter difference does not affect the finding.

## First-round CAO findings: resolved

1. **Semantic requirement comparison and branch retention:** `/home/andrew/git/ansible-workstation/ai/roles/cao/files/install_cao.py:25` parses requirements with `packaging`, canonicalizes distribution/extra names, and uses semantic Requirement equality/hashing for both requested and recorded requirements. Equivalent auxiliary requirements are deduplicated at line 137; the no-update boundary compares the normalized sets at lines 141–149. This resolves the persistent underscore-alias failure.

   `/home/andrew/git/ansible-workstation/ai/tests/test_install_cao.py:104` retains the mixed-case underscore requirement throughout the actual offline installation sequence. Lines 164–175 inspect installed module content: after a same-version Git branch advance, an ordinary call remains unchanged with revision `first`; explicit upgrade installs revision `second`. This is stronger evidence than checking only a `changed` flag. The semantic unit regression at line 51 also checks distribution/extra aliases, equivalent specifiers and consistent hashes.

2. **Receipt-level constraints/resolution state:** `/home/andrew/git/ansible-workstation/ai/roles/cao/files/install_cao.py:33` rejects unsupported nonempty root/tool/option state. It is called immediately after receipt loading, before the no-op decision and before `uv tool install`. Stored constraints, overrides and unsupported resolution/index options therefore fail before an installation can discard them. Supported `find-links` values are validated and explicitly replayed at lines 54–57 and line 150. The implementation preserves the requested fail-before-install boundary without freezing transitive dependencies.

   `/home/andrew/git/ansible-workstation/ai/tests/test_install_cao.py:226` creates a genuine disposable receipt using `UV_CONSTRAINT`, introduces plugin 2.0 and removes the original environment variable. Both explicit-upgrade and source-change attempts must raise on constraints; the test asserts that the only subprocess is `uv tool dir`, every file in the temporary tool environment remains byte-identical, and plugin 1.0 remains installed while 2.0 is absent. The independent unknown-state unit regression also covers overrides, resolution/index options and a future field.

The new `/home/andrew/git/ansible-workstation/ai/roles/cao/tasks/main.yml:34` supplies `packaging>=24.2,<27` to the separate `uv run` interpreter, without adding it to CAO tool requirements. Python selection remains >=3.11 for `tomllib`, avoiding dependence on Ubuntu 22.04's system Python 3.10. The offline parser-wheel fixture copies the locally installed parser sources into a temporary wheel; the integration sequence invokes the actual Ansible installer task with that dependency in normal/check mode. This is credible validation of argument quoting and interpreter availability, while remaining separate from a real upstream installation.

## RTK integration assessment

- `/home/andrew/git/ansible-workstation/ai/all.yml:14` correctly places RTK after Codex/Claude installers and before CAO integration. The `rtk` tag and default-true `rtk_enabled` guard match the authorized handoff.
- `/home/andrew/git/ansible-workstation/ai/rtk.yml:3` imports the correct existing prerequisite playbook. That does run prerequisite tasks, but the missing per-play defaults identified above prevent the intended RTK invocation from using them.
- `/home/andrew/git/ansible-workstation/ai/README.md:116` accurately documents the intended OSS source/pin, mandatory checksum policy, explicit latest updates, inherited upgrade flag, shell-tool scope, PATH needs and absence of live authenticated validation. Its standalone application commands depend on fixing the entrypoint's variable scope.
- The recorded `all.yml --list-tasks --tags rtk` output selects shared prerequisite and RTK task bodies; CAO/service/MCP task bodies are empty under that selection. This validates tag selection, not runtime variable availability. No runtime installation is implied by the syntax/list evidence.
- All seven RTK role hashes matched `/home/andrew/git/ansible-workstation/tasks/rtk-shared-integration/ROLE_BASELINE.json` when checked. This establishes that the shared-integration developer preserved that baseline. It does not approve the role's separate known findings or any subsequent independently owned fixes.

## Evidence integrity and review limits

Read the complete first-round review, `/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/ROUND2_TASK.md`, the updated review request/report/manifests, both diffs, current implementation/tests, round-one snapshots, and `/home/andrew/git/ansible-workstation/tasks/rtk-shared-integration/specification.md` and its report. Checked git status and applicable AGENTS paths before review; no applicable target-tree or ancestor AGENTS file was present. Generated instructions inside test homes are outside this scope.

Independent checks confirmed:

- **10/10** current implementation hashes match `/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/FINAL_STATE.json`.
- **53/53** artifact/current-file hashes match `/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/FILES.json`.
- The **eight** round-one implementation snapshots match their historical hashes. `REVIEW.md` is byte-identical to `round1/REVIEW.md`.
- Regenerating no-index diffs in memory exactly reproduces both `CHANGES.diff` (**10 entries**) and `ROUND2_CHANGES.diff` (**6 entries**).
- All **55** captured baseline files outside the declared edits remain unchanged.

`/home/andrew/git/ansible-workstation/tasks/ansible-cao-updates/VALIDATION.json` records **19 passing tests**, four passing syntax checks and three passing task listings. The eight installer tests include the focused regressions above; eleven existing MCP tests also passed. The complete suite and syntax checks were not repeated because the source hashes match those validated files. The only additional behavioral probe was the read-only Ansible variable-scope inspection needed for the concrete integration concern.

The original `/home/andrew/git/ansible-workstation/ai/roles/cao/tasks/main.yml` baseline was reconstructed from an initial read and still lacks an independent initial hash; round-two snapshot integrity does not remove that historical limitation. The recorded upstream SHA remains distinct from PyPI despite both declaring 2.5.4. Effort consumption is still limited to ephemeral `effort: auto` launches; no installed-profile or live end-to-end effort-routing claim is approved here. The restart opt-in/default and update-only CAO playbook are unchanged by this round.

Approval of the CAO corrections applies to the recorded code and focused evidence. Combined approval remains withheld until the shared RTK entrypoint resolves its required defaults. No live application or RTK role approval is implied.
