<cao-memory>
## Context from CAO Memory
- [project] tiered-agent-profiles-design: Decision (2026-11-16): CAO agent profiles are managed by the ansible-workstation ai/ stack (role cao, sync_mcps.py). Design: generalist developer_low/medium/high (reasoning effort low/medium/high), reviewer_basic (lowest effort, simple tasks) and reviewer_advanced (high effort, high tasks); the supervisor classifies each task and routes accordingly; workers stay on the supervisor's provider.
- [project] ansible-workstation-task-playbooks: Tarefa: No repositório /home/andrew/git/ansible-workstation, examine e atualize os playbooks Ansible, respeitando as convenções e instruções locais. Faça alterações justificadas, execute verificações apropriadas e relate arquivos e resultados. Não leia credenciais, arquivos .env, chaves SSH ou arquivos PEM.
- [global] ansible-self-contained-dependencies: The user expects Ansible to install and refresh required repository signing keys and resolve its own dependencies, rather than requiring manual host repair. The current authorized change is the Chrome APT playbook in /home/andrew/git/ansible-workstation; previously cancelled CAO/RTK work must not be resumed.
- [global] language-preference: The user prefers all durable memories and internal technical records or agent instructions to be written in English, while all user-facing communication must be in Portuguese. Apply this preference across projects and delegated agents.
</cao-memory>

IMPLEMENTATION TASK — tiered CAO agent profiles managed by Ansible.

STEP 0 (mandatory, before anything else): save this entire message verbatim to
/home/andrew/git/ansible-workstation/tasks/tiered-agent-profiles/SPECIFICATION.md
(the supervisor has no file-write tool in this session). Keep all your working notes/logs under /home/andrew/git/ansible-workstation/tasks/tiered-agent-profiles/.

## Context
Repo: /home/andrew/git/ansible-workstation. The AI stack lives in ai/ (see ai/README.md). Role `cao` already:
- copies ai/roles/cao/files/sync_mcps.py to ~/.local/share/ai-stack/sync_mcps.py,
- templates ai/roles/cao/templates/ai-stack-sync-mcps.j2 into ~/.local/bin/ai-stack-sync-mcps,
- runs it (ai/roles/cao/tasks/mcp.yml), driven by ai/roles/cao/defaults/main.yml (`cao_mcp_profiles: [code_supervisor, developer, reviewer]`, `cao_mcp_clients`, `cao_mcp_profile_prefix: ai_stack`).
sync_mcps.py reads each BASE profile (local agent-store first, then the CAO package's built-in agent_store), and renders `<prefix>_<codex|claude>_<name>.md` into ~/.aws/cli-agent-orchestrator/agent-store/, copying all frontmatter, forcing `provider`, injecting client MCPs, and appending an "AI stack: provider and delegation" routes section.

Installed CAO (pinned commit) supports these profile frontmatter fields (verified in cli_agent_orchestrator/models/agent_profile.py):
- `codexConfig: {model_reasoning_effort: <minimal|low|medium|high|xhigh>}` → passed as `-c key=value` to Codex.
- `claudeConfig: {effort: <low|medium|high|xhigh>}` → `--effort` for Claude Code.
- `assign`/`handoff` accept a per-call `model` but NO per-call effort, so effort must be fixed per profile.

Built-in base prompts to reuse (read them first, keep what is useful):
/home/andrew/.local/share/uv/tools/cli-agent-orchestrator/lib/python3.12/site-packages/cli_agent_orchestrator/agent_store/{code_supervisor,developer,reviewer}.md
Research notes with rubric ideas (inspiration only; the gist has no visible license — do NOT copy its text): /home/andrew/git/ansible-workstation/tasks/research-tiered-agent-profiles.md

## Goal
The user's agent profiles must be defined in this Ansible repo and deployed by it:
1. Base profiles (source of truth) versioned in the repo, deployed by Ansible, then rendered per provider by sync_mcps.py.
2. Profiles:
   - `code_supervisor` — customized supervisor (see rubric below).
   - `developer_low`, `developer_medium`, `developer_high` — ONE generalist developer prompt (not tied to Python/pytest/docx; stack-agnostic: read the repo's own conventions such as CLAUDE.md/AGENTS.md/README, follow existing patterns, run the project's own checks), differing only in effort and description/tags.
   - `reviewer_basic` — lowest effort (`low` for both providers), for simple tasks.
   - `reviewer_advanced` — `high` effort, for high-complexity / risky tasks.
3. Effort levels must be configurable via Ansible variables (e.g. a dict in ai/roles/cao/defaults/main.yml keyed by profile name with `codex` and `claude` values). Defaults: developer_low=low, developer_medium=medium, developer_high=high, reviewer_basic=low, reviewer_advanced=high, code_supervisor=medium. Validate values with `assert` against each provider's allowed set.
4. Generated profiles for a provider must contain only that provider's config block (strip `claudeConfig` from codex renders and `codexConfig` from claude renders) — implement in sync_mcps.py.

## Design requirements
- Do NOT put base profiles into the CAO agent-store (that would shadow built-ins like `code_supervisor` and make un-provisioned base profiles launchable on the default Kiro provider). Instead: deploy base profiles to a separate directory, e.g. ~/.local/share/ai-stack/profiles/ (dir 0700, files 0600), and add a `--base-dir` option to sync_mcps.py. Lookup order: --base-dir → local agent-store → CAO built-in. Wire it in the wrapper template.
- Base profiles should be Jinja templates in the role (e.g. ai/roles/cao/templates/profiles/*.md.j2) so effort values come from variables. Agent prompt text in ENGLISH (user's convention: agent instructions in English, user-facing docs in Portuguese).
- Update `cao_mcp_profiles` default to [code_supervisor, developer_low, developer_medium, developer_high, reviewer_basic, reviewer_advanced].
- Stale generated profiles: remove `<prefix>_<client>_developer.md` and `<prefix>_<client>_reviewer.md` ONLY if they contain sync_mcps.py's MARKER (never delete files without the marker). Prefer implementing this as an explicit, tested sync_mcps.py option (e.g. `--prune` removing marker-bearing `<prefix>_*` profiles not in the current profile list) invoked by the Ansible task, rather than hard-coded names.
- Keep all existing behaviour (MCP import, Codex HTTP inheritance, allowedTools/delegateTools grants, idempotence, --check, 0600 perms, refusal to overwrite non-marker files).

## Supervisor routing rubric (write into code_supervisor base profile, in English)
Before delegating, classify every task as LOW / MEDIUM / HIGH and record the level and a one-line reason in the task description file.
- LOW: single file or mechanical change (rename, config tweak, docs, formatting, small obvious fix), clear spec, low risk.
- MEDIUM: feature/bugfix touching a few files with a clear spec; tests needed.
- HIGH: architecture/design, concurrency, security, data migration/loss risk, production infra, ambiguous spec, debugging without a known cause, or roughly >5 files.
Escalators (bump one level, max HIGH): ambiguity; ≥3 files/systems; security/production/data-loss stakes; unfamiliar territory; a wrong result would be hard to detect later.
When unsure between two levels, pick the higher (default MEDIUM when no information).
User override: if the user's request contains `[level: low|medium|high]` (also accept Portuguese `[nivel: baixo|medio|alto]`), use it without classifying.
Routing:
- developer: LOW→developer_low, MEDIUM→developer_medium, HIGH→developer_high.
- reviewer: LOW and MEDIUM→reviewer_basic; HIGH→reviewer_advanced. If any escalator for security/production/data-loss applies, use reviewer_advanced regardless of level.
- Escalation on failure: if the reviewer rejects the same task twice, re-assign the fix one developer level up (and use reviewer_advanced once the task reaches HIGH).
- Workers always use the same provider as the supervisor (the routes section appended by sync_mcps.py lists the provider-specific names; use those).
Also keep the built-in supervisor's workflow essentials: tasks written to files with absolute paths, every code change reviewed until approved, supervisor never writes code itself.

## Docs
Update ai/README.md (Portuguese): new profile table, what each level means, effort variables, how routing works, how to change efforts, that profiles are deployed by `ansible-playbook ai/mcp.yml -K`. Update ai/vars.example.yml with the effort dict example.

## Tests / verification (required)
- Extend ai/tests/test_sync_mcps.py: --base-dir lookup order, provider-specific config stripping, prune only removes marker files, existing tests still pass.
  Run: "$(uv tool dir)/cli-agent-orchestrator/bin/python" -m unittest discover -s ai/tests -v
- `ansible-playbook ai/mcp.yml --syntax-check` and `ansible-playbook ai/all.yml --syntax-check`.
- Validate each rendered profile with CAO's own loader/validator (e.g. `cao profile validate` or the AgentProfile model) — render into an ISOLATED temporary HOME under tasks/tiered-agent-profiles/, not the real home.
- Do NOT apply the playbook to the real home directory and do NOT modify ~/.aws/cli-agent-orchestrator/agent-store or ~/.local/share/ai-stack for real; the user will apply after review.
- Do not read credentials, .env, SSH keys or PEM files. Do not touch unrelated modified files in the repo (README.md, all.yml, browser/, sdk/ have pre-existing uncommitted changes — leave them alone). Do not commit.

## Deliverable
When done, call send_message with (in Portuguese): list of created/changed files (absolute paths), test and syntax-check results (pass/fail counts), anything you could not verify, and any deviation from this spec with the reason.

[Assigned by terminal 97593bc0. When done, send results back to terminal 97593bc0 using send_message]
