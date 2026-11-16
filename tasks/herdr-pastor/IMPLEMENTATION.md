# herdr-pastor — implementation report

Developer: mala_developer_high_claude (Claude Opus 5.5). Nothing committed.

## Files

New:
- `ai/roles/herdr/templates/herdr-pastor.j2`: the command (POSIX sh; `dash -n` clean).
- `ai/roles/herdr/tasks/pastor.yml`: validation assert, then a become block as `ai_stack_user` (same pattern as `install.yml`) that runs `file` (dir) and `template` (mode 0755) when enabled, or `file state=absent` when `herdr_pastor_enabled=false`.
- `ai/tests/test_herdr_pastor.py`: 10 unittest cases.

Edited (my changes are additions only):
- `ai/roles/herdr/defaults/main.yml`: adds `herdr_pastor_enabled: true`, `herdr_pastor_binary`, `herdr_pastor_sheep: [claude, codex]`, `herdr_pastor_editor_share: 0.65`.
- `ai/roles/herdr/tasks/main.yml`: adds `include_tasks: pastor.yml`, gated on the same x86_64/aarch64 condition as the herdr install.
- `ai/roles/herdr/README.md`: adds 4 vars to the table and a new "herdr-pastor" section.
- `ai/README.md`: adds the subsection "herdr-pastor: o editor como pastor, os agentes como ovelhas" and 2 table rows. The pre-existing uncommitted CAO hunk is untouched.
- `ai/vars.example.yml`: adds commented vars under the herdr block. The pre-existing hunks are untouched.

I did not touch `ai/roles/cao/*` or `ai/tests/test_sync_mcps.py`.

## Behaviour and design choices

- Usage: `herdr-pastor [--session NOME | --session=NOME] [--no-attach] [-h|--help] [DIR]`. DIR defaults to `$PWD` and is resolved to an absolute path. I added `--no-attach` beyond the spec, for scripting and tests.
- Workspace label: **`🧑‍🌾 <basename DIR>`**. I picked this over a fixed `🧑‍🌾 pastor` so several projects are easy to tell apart in the sidebar. The root pane is labelled `🧑‍🌾 pastor` and runs `${VISUAL:-${EDITOR:-vi}}` through `pane run`.
- Session choice:
  1. `--session` when given.
  2. Otherwise, when run inside herdr (`HERDR_PANE_ID` set), the current `$HERDR_SESSION`, unless that is `cao`.
  3. Otherwise `default`.
  Every herdr call passes `--session` explicitly. `cao` is never chosen implicitly.
- Server: if `herdr --session S status server --json` does not report `"running":true`, the script starts `setsid herdr --session S server` in the background (`nohup` if `setsid` is missing) and polls for up to 10 s.
- Sheep: each one is checked with `command -v`. A missing sheep produces a stderr warning and is skipped. If none are available, only the editor pane is created.
- Layout:
  - The first sheep splits the editor pane to the right with `--ratio 0.65`, so the editor keeps 65%.
  - Each following sheep splits the previous one downward with ratio `1/(sheep still to place + 1)`, which gives equal heights.
  - Splits use `--no-focus` and `--cwd DIR`.
- Starting agents: `herdr agent start <sheep>-<workspace_id> --kind <sheep> --pane <id>`. The `-wN` suffix keeps agent names unique within the server.
  - Exit 2 (kind not supported by herdr): fall back to `herdr pane run <id> <sheep>`.
  - Exit 1 with `agent_not_ready` or `timeout`: warn only, because the agent is already running in the pane.
  - Other errors: warn.
- End: `herdr pane focus --direction left --pane <first sheep>` returns focus to the editor.
  - Outside herdr: `exec herdr --session S` attaches, unless `--no-attach` was given.
  - Inside herdr but in a different session: prints an attach hint.
- Install time: the role only writes the script. It does not start a server, does not run herdr, and does not touch `~/.config/herdr`; a test asserts this. The assert limits `herdr_pastor_sheep` entries to `^[a-z][a-z0-9_-]{0,23}$`, so a name plus the `-wN` suffix fits herdr's 32-character agent-name limit and no shell metacharacters reach the template. It also requires `0 < editor_share < 1`.
- The binary is `herdr` from PATH, falling back to the rendered `{{ herdr_binary }}`.

## How I checked the herdr CLI (real binary, v0.9.5)

All mutating experiments ran in a throwaway session, `pastor-dev-test`, with the inherited `HERDR_*` variables unset. That session was stopped and deleted afterwards (`herdr session stop/delete pastor-dev-test` returned `"stopped":true` and `"deleted":true`). `session list` then showed only `default` and `cao`, both running and untouched, and `pgrep` found no leftover processes.

- `herdr <group> <cmd> --help`: `workspace create --cwd --label --focus/--no-focus`, `pane split [PANE_ID] --direction right|down --ratio --cwd --no-focus`, `pane rename <PANE_ID> [LABEL]...`, `pane run <PANE_ID> <COMMAND>...`, `pane focus --direction left|right|up|down --pane <ID>` (focuses a neighbour; the CLI has no "focus pane by id"), `agent start <NAME> --kind <KIND> --pane <ID>` (kinds include claude and codex), and `status server --json`.
- `herdr api schema --json`: the methods above exist in protocol 22.
- `--session X status server --json` returns `{"status":"not_running","running":false,...}` for a session that does not exist. `workspace list` against a stopped session fails with code `server_not_running`. Background `herdr --session X server` starts a headless server that keeps running after the CLI call returns.
- From inside the `cao` pane, `--session pastor-dev-test` and `--session default` both resolve to their own sockets (`~/.config/herdr/herdr.sock` for `default`), so `--session` takes precedence over the inherited `HERDR_SOCKET_PATH`.
- `workspace create` returns compact JSON with `.result.root_pane.pane_id` and `.result.workspace.workspace_id`. `pane split` returns `.result.pane.pane_id`.
- **`--ratio` is the share kept by the original pane.** Right split with 0.35: the left pane was 42/120 columns. Down split with 0.25: the top pane was 10/40 rows. That is why the editor uses 0.65.
- `agent start` for claude and codex took about 3.5 s each. In a new directory both returned exit 1 with `agent_not_ready`: Claude was on its folder-trust dialog and Codex on an update prompt. Both agents were still listed in `agent list` as `blocked` and running. Effect on `herdr agent start`: it works for both kinds, but in that state it is not a hard success. An unsupported kind (`--kind aider`) gives `unsupported interactive agent kind`, exit 2.
- `pane split ... --ratio 0,5` returns `invalid ratio: 0,5`, exit 2. **Bug found by the tests:** under the user's pt_BR locale, `awk` printed `0,3333`. The script now uses `LC_ALL=C awk`, and the tests run with `LC_ALL=pt_BR.UTF-8` to catch a regression.
- **End-to-end:** the rendered script ran against the real binary with `--session pastor-dev-test --no-attach`, exit 0. The result was workspace `🧑‍🌾 e2e-proj`, focused, with panes `🧑‍🌾 pastor` (title `vi`, 78×40), `🐑 claude` (42×20), and `🐑 codex` (42×20). The splits were right 0.65 and down 0.5, `focused_pane_id` was the editor, and the agents were named `claude-w2` and `codex-w2`.

## Tests

The fake `herdr` on PATH is a Python script that records argv and session and mimics the real 0.9.5 JSON and exit codes. The rendering tests run `ansible-playbook` with `tasks/pastor.yml` in an isolated HOME, following the same pattern as `test_mcp_check_mode.py`.

- Role:
  - `--check` on a fresh HOME creates nothing.
  - A real run installs the script with mode 0755 and fully rendered content.
  - A second run reports `changed=0`.
  - `enabled=false` in `--check` keeps the file; a real run with `enabled=false` removes it.
  - `~/.config/herdr` is never created.
  - Invalid sheep names are rejected.
- Script:
  - Exact command sequence: status → workspace create → rename → editor run → split, rename, and agent start per sheep → `pane run` fallback for an unknown kind → final focus → attach.
  - The missing sheep `ghost` is skipped with a warning.
  - The `agent_not_ready` warning is printed.
  - `--session NAME` and `--session=NAME` are passed to every call and to the attach.
  - `VISUAL` takes priority and a DIR argument works.
  - Inside the `cao` session the script targets `default` and does not attach; inside another session it stays in that session.
  - A headless server is started when the session is not running.
  - With no sheep, only the editor pane is created.
  - `--help` and invalid arguments make no herdr calls.

Command:

```
python3 -m unittest ai/tests/test_herdr_pastor.py -v
```

Result: `Ran 10 tests in ~11s — OK`.

Also run:
- `ansible-playbook ai/herdr.yml --syntax-check`: OK.
- `ansible-playbook ai/all.yml --list-tasks --tags herdr`: lists `herdr : Gerenciar comando herdr-pastor`.
- The full suite (`python3 -m unittest discover -s ai/tests`) still has failures outside herdr:
  - `test_sync_mcps` cannot import the `frontmatter` module.
  - `test_install_cao` has 2 errors and 1 failure.
  - `test_mcp_check_mode.test_stale_script_is_not_executed` fails because `/cli-agent-orchestrator/bin/python` is missing.

  These are in the CAO area, which has the pre-existing uncommitted changes, and none of them involve files I changed.

## Limitations

- When the server has to be started, the session runs headless at 120×40 until a client attaches. herdr resizes the layout on attach.
- On first use in a directory, agents may sit on their own trust or update dialogs. herdr reports these as `agent_not_ready`, and the script prints a warning naming the pane.
- `cao` is the only session excluded by name. A custom CAO herdr session (`CAO_HERDR_SESSION`) is not detected.
- No shellcheck, ansible-lint or yamllint is installed on this host, so those checks were not run.

## Follow-up: layout.apply / plugins (2026-11-16)

I checked these using only the installed binary's `--help` and `api schema --json`, plus a throwaway session `pastor-dev-test`, which was stopped and deleted afterwards. Only `default` and `cao` remain.

- **The CLI cannot call `layout.apply` or `layout.export`.** They exist in the API schema (`LayoutApplyParams {root, tab_id | workspace_id, focus, tab_label}`, and `LayoutNode` = pane `{command[], cwd, env, label, pane_id}` | split `{direction right|down, ratio, first, second}`). But herdr 0.9.5 has no `herdr layout` command, and `herdr api` only offers `snapshot` and `schema`. The only way to reach them is to write raw JSON to the session socket (`{"id","method","params"}` + newline). I probed this with a small Python client.
- **`layout.apply` does produce the target layout in one call.** I applied it with `tab_id` only; passing both `tab_id` and `workspace_id` fails with `invalid_target`. With split right 0.65 → editor | split down 0.5 → claude / codex, the result was:
  - panes of 78×40, 42×20 and 42×20 with the expected labels;
  - focus on the editor;
  - herdr detected the claude and codex agents in their panes (`blocked` on startup dialogs);
  - the tab was replaced: new tab id `w1:t2` and new pane ids, even though I passed the root `pane_id`.
- **Drawbacks of `layout.apply`:**
  1. `command` is the pane's process itself, with no shell. `process-info` shows `shell_pid` equal to the pid of `vi`. When the editor or an agent exits, its pane closes, and the command does not go through the user's shell (no aliases or PATH from rc files; `$EDITOR` with arguments would have to be split by hand).
  2. Agents get no herdr name (`name: null`), so `herdr agent prompt claude-wN` would not work.
  3. Only a private socket protocol reaches it, so the script would need python3 or `nc -U` plus JSON building, instead of the stable CLI.
- **Plugins:** `herdr plugin install <OWNER/REPO[/SUBDIR]>` installs from GitHub. `plugin list --json` shows no plugins installed. Neither `--help` nor the schema names an official layout plugin or example. Finding one would mean fetching URLs, which the task forbids, and installing a third-party plugin is a supply-chain decision for the user.
- **Decision:** I kept the CLI implementation (`workspace create` / `pane split` / `pane run` / `agent start`), which was already verified end-to-end. The 3-node `layout.apply` tree is a possible future change if herdr adds a `layout apply` CLI command. **No code was changed in this follow-up.**

## Round 1 fixes (2026-11-16)

Developer: mala_developer_high_claude (Claude Opus 5.5). Nothing committed. Files touched:
`ai/roles/herdr/templates/herdr-pastor.j2`, `ai/tests/test_herdr_pastor.py`, the herdr-pastor
sections of `ai/roles/herdr/README.md` and `ai/README.md`. `tasks/pastor.yml`, defaults,
`ai/roles/cao/*` and `~/.config/herdr/` were not touched. No herdr server or real session was
used; the only real-binary calls were `herdr agent start --help` and `herdr workspace close --help`.

### P2 #1: herdr failures were ignored (template ex-:142)

- New helpers `must WHAT herdr-args…` (runs `h …` capturing stdout+stderr in `$out`) and
  `abort WHAT OUTPUT`: prints `herdr-pastor: falha ao WHAT: <herdr output>` to stderr and
  exits 1. Once the workspace exists, it also prints
  `workspace wN ficou incompleto; feche-o com: herdr --session S workspace close wN`
  (form checked with `herdr workspace close --help`). It never attaches and never prints "pronto".
- Now fatal: `workspace create` (and an unparsable response), root pane rename, editor
  `pane run`, every `pane split` (non-zero exit or no `pane_id` in the reply; this was `break`),
  sheep pane rename, `agent start` with any exit other than 0/2 and no soft marker, the
  `pane run` fallback after exit 2, and the final `pane focus`.
- Soft cases kept, as documented: sheep missing from PATH → warning/skip; `agent start` exit 2
  (unsupported kind) → `pane run` fallback; `agent_not_ready` → warning. I also kept
  `"timeout"` as a warning (the original implementation already did). `agent start --help`
  describes `--timeout` as "wait for interactive readiness", so a timeout means the agent was
  launched and herdr stopped waiting, which is the same situation as `agent_not_ready`. The
  header comment and README now list exactly these soft cases.

### P2 #2: `[claude, claude]` collided on `claude-wN`

- Repeated sheep get an ordinal. The first occurrence keeps `claude-wN` / `🐑 claude` (unchanged
  for the common case); later ones become `claude-2-wN` / `🐑 claude 2`, `claude-3-wN`, and
  so on. The ordinal counts only sheep actually placed (after the PATH filter).
- Name length: the sheep regex still allows 24 chars, so `24 + "-N" + "-wNN"` stays ≤ 32
  (herdr's limit) for up to 9 repeats and workspace ids below w100. Same edge as before.

### Tests

- The fake herdr now prints errors the real way (`{"id","error":{"code","message"}}` on stderr,
  exit 1). It supports `FAKE_HERDR_FAIL=<argv prefix>` for failure injection and rejects a
  reused agent name (`agent_name_taken`), like a server that already has that agent.
- New tests:
  - `test_unexpected_herdr_failures_abort` (8 subtests: first/second split, editor run, pastor
    rename, sheep rename, generic `agent start` failure, `pane run` fallback failure, final
    focus). Each asserts exit 1, the `falha ao …` message plus herdr's error text, the
    `workspace close w7` hint, no attach, and that the call sequence stops exactly at the
    failing call.
  - `test_workspace_create_failure_aborts`: exit 1, no "incompleto" hint.
  - `test_repeated_sheep_get_unique_names`: renders `[claude, claude, codex]` and asserts the
    labels `🐑 claude`/`🐑 claude 2`/`🐑 codex`, the agents `claude-w7`/`claude-2-w7`/`codex-w7`,
    the equal-height ratios and the final focus.
- Regression check: with the HEAD (pre-fix) template temporarily restored, the new tests
  fail (`FAILED (failures=9)`: all 8 failure subtests plus the duplicate test). The fixed
  template was put back afterwards.

Commands and results:

```
python3 -m unittest ai/tests/test_herdr_pastor.py -v   # Ran 13 tests in ~16s — OK
ansible-playbook ai/herdr.yml --syntax-check           # playbook: ai/herdr.yml (OK)
```

Limitation: when the script aborts mid-way it does not close the half-built workspace. It
leaves the workspace for inspection and prints the close command instead.
