# herdr "Pasture" plugin: implementation report

Developer: mala_developer_high_claude (terminal 5767df2f). The plugin is local only. Nothing was added to the repository except this report, and nothing was committed. The herdr-pastor files are untouched; they are kept for review.

## Files created (outside the repo)

`/home/satanas/.config/herdr/local-plugins/pasture/`:
- `herdr-plugin.toml`: manifest declaring one pane `pasture` (placement `zoomed`) and one action `open` (context `global`).
- `pasture.py`: the plugin itself. It uses only the Python 3 standard library. It reads data through the public CLI (`api snapshot`, `agent read`, `agent focus`) and draws with 24-bit ANSI colors. It also has a `--once [--plain] [--size WxH] [--session S]` mode for diagnostics.
- `test_pasture.py`: 18 unit tests.
- `README.md`: usage notes in Portuguese.

Files herdr created itself when the plugin was linked or opened (I did not write them):
- `~/.config/herdr/plugins.json`: the plugin registry. **It is global**, so the plugin is visible in every session, including `default` and `cao`.
- `~/.config/herdr/plugins/config/pasture/` (empty).
- `~/.local/state/herdr/plugins/pasture/`.

`~/.config/herdr/config.toml` was **not changed**. Its mtime is 16:12, before this work started.

## Manifest and runtime contract (from the installed binary only)

How I found it:
- `herdr plugin --help` lists the subcommands: `install|uninstall|update|link|unlink|enable|disable|list|config-dir|action|log|pane`.
- `plugin pane open` takes `--plugin --entrypoint --placement overlay|split|tab|zoomed --focus`, among other options.
- In `herdr api schema --json`, `InstalledPluginInfo`, `PluginManifestPane {id, title, command[], placement, width, height, description, platforms}` and `PluginManifestAction {id, title, command[], contexts[global|workspace|tab|pane|selection]}` describe the manifest. The schema also has `events`, `startup`, `build` and `link_handlers` sections.
- The manifest file name is `herdr-plugin.toml`, at the plugin root.

What the binary required and accepted:
- With only `id/name/version`, `plugin link` failed with `{"code":"invalid_plugin_min_herdr_version","message":"plugin min_herdr_version is required"}`.
- With `min_herdr_version = "0.9.5"` it linked: `type: plugin_linked`, `source.kind: local`. It also warned `manifest does not declare platforms`, so the manifest now declares `platforms = ["linux"]`.

Environment of the pane process, captured with a probe pane:
- The working directory is the plugin root.
- The command is exec'd directly as an argv list.
- Variables:
  - session connection: `HERDR_ENV=1`, `HERDR_SESSION`, `HERDR_SOCKET_PATH` (the socket of the calling session), `HERDR_BIN_PATH`;
  - pane location: `HERDR_PANE_ID`, `HERDR_TAB_ID`, `HERDR_WORKSPACE_ID`;
  - plugin paths: `HERDR_PLUGIN_ID`, `HERDR_PLUGIN_ROOT`, `HERDR_PLUGIN_ENTRYPOINT_ID`, `HERDR_PLUGIN_CONFIG_DIR`, `HERDR_PLUGIN_STATE_DIR`;
  - `HERDR_PLUGIN_CONTEXT_JSON={"workspace_id","workspace_label","tab_id","focused_pane_id",…}`;
  - terminal: `TERM=xterm-256color`, `COLORTERM=truecolor`.
- The pane is a normal pty (`stty size` gave 38×117 when zoomed in a 120×40 headless server).
- When the process exits, herdr closes the pane and un-zooms the tab.
- An action's command runs detached. `plugin log list --plugin pasture` showed `status: succeeded, exit_code: 0`.

Data sources:
- `herdr api snapshot` returns `.result.snapshot` with `workspaces`, `tabs`, `panes` (including `label`), `agents` (`agent`, `agent_status`, `name`, `pane_id`, `tab_id`, `workspace_id`), `layouts` and the focused ids.
- `herdr agent read <pane_id> --source recent --lines N` returns plain text.
- `herdr agent focus <pane_id>` accepts the pane id.

## How to open it

```bash
herdr plugin link ~/.config/herdr/local-plugins/pasture        # already done; registry is global
herdr plugin pane open --plugin pasture --entrypoint pasture --placement zoomed --focus
herdr plugin action invoke open --plugin pasture                # same, through the manifest action
```

Keys:
- arrows/hjkl select a sheep;
- Enter runs `herdr agent focus` on the selected sheep and closes the pasture;
- Tab/Shift+Tab cycle through workspaces that have agents (shown as "Tab: field i/n");
- a mouse click selects a sheep (SGR mouse mode); the wheel moves the selection;
- `r` refreshes;
- `q`/Esc close.

Opening the pasture with one key needs an entry in `config.toml`. I did **not** apply it; this is the snippet:

```toml
[[keys.command]]
key = "prefix+alt+p"
type = "shell"
command = "herdr plugin pane open --plugin pasture --entrypoint pasture --placement zoomed --focus"
```

Behaviour:
- **Counters:** working → wandering, blocked → need you, idle/done/unknown → resting.
- **Sheep labels:** the pane label, else the agent name, else a non-numeric tab label, else the agent kind.
- **Kind badge:** two letters (`CL`, `CO`, `GE`…) colored by kind.
- **Resting sheep** show `zzz`; **blocked sheep** show a ` (!) <Kind> ` balloon.
- **Working sheep** wander ±3 columns inside their cell.
- **Animation and polling:**
  - frames are redrawn at ≤ 4 fps, and only while some sheep is working;
  - otherwise the screen is redrawn only on a key, data change or resize;
  - the snapshot is polled every 1.5 s;
  - the selected sheep's output is re-read every 2 s.
- **Sign:** "WELCOME TO / <workspace>".
- **Opening workspace:** the pasture starts on the workspace from `HERDR_PLUGIN_CONTEXT_JSON`.
- **Overflow:** sheep are paged when they don't fit.
- **Sizes:** an empty session and tiny terminals are handled.
- **Text width:** emoji ZWJ sequences count as one 2-column cell.

## Verification

Tests: `cd ~/.config/herdr/local-plugins/pasture && python3 -m unittest`, result `Ran 18 tests … OK`. They cover:
- state → group mapping and counters;
- workspace grouping and label precedence;
- screen split, grid, cell bounds and sprite bounds while wandering;
- paging, hit-testing and arrow movement;
- key, Esc, unknown CSI sequence and SGR mouse parsing;
- the full scene text and truecolor ANSI output;
- Tab/Enter/quit handling, selection surviving a refresh, opening on the context workspace;
- empty session at 40×12, escape stripping and wide characters.

Headless check in the throwaway session `pasture-dev`:
- Setup: workspace `core`, real `claude` (pane label "doc comments", agent `docs`) and `codex` (agent `review`), both blocked on startup dialogs, plus workspace `blog` with no agent.
- `plugin action invoke open` opened pane `w1:p5` with label "The pasture", zoomed and focused. Its process was `python3 pasture.py`.
- `pane read --format ansi` contains 24-bit SGR codes (`38;2;…`).
- Input:
  - `send-keys right` moved the breadcrumb to `core / review`;
  - an SGR click (`ESC[<0;30;8M`) on the first sheep moved it back to `core / doc comments`;
  - right then Enter focused `w1:p4` (codex); the pane closed and the layout un-zoomed (`zoomed:false, focused_pane_id:w1:p4`);
  - a second pane `w1:p6` closed on `q` (`pane_not_found` afterwards).
- `python3 pasture.py --session pasture-dev --once --plain --size 100x30` from outside herdr also rendered.
- Afterwards: `session stop` returned `true`, `session delete` returned `true`, and `session list` shows `["default","cao"]`. No pasture or pasture-dev processes are left.

Captured render (`herdr pane read w1:p5 --source visible --format text`, 117×38):

```
                                                                      ▄███▄
   The pasture                  ▄▄██▄▄                               ███████   0 wandering   2 need you   0 resting
   2 sheep, one happy herd.    ▀▀▀▀▀▀▀▀▀                ▄▄██▄▄        ▀███▀
                                                       ▀▀▀▀▀▀▀▀▀
                   (!) Claude Code      (!) Codex
                        ▄▄▄▄▄             ▄▄▄▄▄
                       ███████▐█▌        ███████▐█▌
                        ▘▘  ▝▝CL          ▘▘  ▝▝CO
                     doc comments         review
  WELCOME TO
  core

       ██
       ██
       ██
       ██
       ██
       ██
       ██                                                                                                   ·
       ██          ·
       ██                              ·
    ▲         ▲         ▲         ▲         ▲         ▲         ▲         ▲         ▲         ▲         ▲         ▲
════█═════════█═════════█═════════█═════════█═════════█═════════█═════════█═════════█═════════█═════════█═════════█══
════█═════════█═════════█═════════█═════════█═════════█═════════█═════════█═════════█═════════█═════════█═════════█══
  core / doc comments                                                                                  THE WORKSHED
   ● Claude Code                                                                                          blocked
     moment to review what's in this folder first.

     Claude Code'll be able to read, edit, and execute files
     here.

     Security guide

     ❯ No, exit
       Yes, I trust this folder

     Enter to confirm · Esc to cancel
  ←↑↓→/hjkl select · Enter focus · Tab field · click select · q/Esc close
```

## Limitations and notes

- The CPU measurement was not valid: `pgrep` picked my own shell instead of the plugin process. Low CPU comes from the design (≤ 4 fps only while animating, otherwise a 0.5 s select timeout and polls every 1.5–2 s); I did not measure it.
- No working (wandering) agent was observable live. Accepting Claude's trust dialog would have written to the user's Claude config, so the agents stayed blocked. The wandering animation is covered by the unit tests only.
- Sprites are Unicode block characters, so the result is simpler than the website's artwork. Kitty graphics are not used.
- The plugin registry is global (`~/.config/herdr/plugins.json`). Linking registers it for all sessions, which is the intended end state. `herdr plugin unlink pasture` removes it.
- Pane events (`events.subscribe`) are not used. Polling through the CLI keeps the plugin independent of the socket protocol.

## Round 1 fixes (review CHANGES_REQUESTED: 1 HIGH, 3 MEDIUM)

All four findings are fixed. Only `pasture.py` and `test_pasture.py` in `~/.config/herdr/local-plugins/pasture/` changed. The repo, `config.toml` and the real herdr sessions were not touched, no throwaway session was needed, and nothing was committed.

1. **HIGH, terminal-control injection.**
   - New `safe_text()` removes:
     - complete CSI/OSC/ESC sequences, both the 7-bit forms and the C1 forms `\x9b` / `\x9d…\x9c`;
     - every remaining `Cc` character (C0 including ESC and BEL, DEL, C1 0x80–0x9F);
     - bidi override characters (U+202A–202E, U+2066–2069).
   - Tab becomes a space. ZWJ, accents and emoji are kept.
   - `Canvas.put()`, the single entry point for all text (labels, workspace names, kind, status, breadcrumb, errors, output), now always passes text through it.
   - `clean_output()` (workshed output) uses the same function.
   - Tests: `SanitizeTests`. They feed a pane label with `ESC[2J`, BEL, NEL and C1 CSI, a workspace label with OSC 52 and RLO, an agent kind with CSI, agent output with OSC 52 / CSI / C1, and an error message with OSC 52 / CSI / C1. They assert that the final ANSI frame contains only our own `ESC[…H` / `ESC[…m` sequences and no control characters.

2. **MEDIUM, strict decoding.**
   - `Herdr.run()` now uses `subprocess.run(..., encoding='utf-8', errors='replace')`.
   - `refresh_output` and the focus path also catch `ValueError`, which covers `UnicodeError` and JSON errors.
   - Tests in `DecodingTests` use a fake CLI that writes byte 0xff:
     - a successful `agent read` gives `ok �� end`;
     - failing `read` and `focus` with 0xff and OSC 52 on stderr raise `RuntimeError` with replacement characters and do not crash; the frame stays clean;
     - an invalid snapshot becomes `app.error` instead of a crash.

3. **MEDIUM, raw mode left on.**
   - New `restore_terminal(out, fd, saved, termios)`: the escape cleanup is best effort (`OSError`/`ValueError` are ignored), and `tcsetattr` runs in a `finally` that does not depend on the output.
   - `run_interactive` also restores the previous SIGWINCH/SIGTERM/SIGHUP handlers.
   - It now accepts `fd`, `out` and `size`, so it can be tested on a real pty.
   - Tests in `TerminalRestoreTests`:
     - a fake termios with a stdout whose `write` and `flush` raise `BrokenPipeError`: `tcsetattr` is still called;
     - a real `os.openpty()` with a broken stdout: `BrokenPipeError` propagates and the pty's termios equals the saved state;
     - a real pty with normal output: the termios state is restored and the output ends with `ESC[?1049l`.

4. **MEDIUM, sequences split across reads.**
   - New `InputDecoder`. It keeps a byte buffer and consumes only complete sequences, using `parse_events(data, final)`, which returns `(events, consumed)`.
   - A lone ESC or an unfinished CSI waits for up to `ESC_TIMEOUT` (50 ms):
     - if the continuation arrives in time, it completes the sequence;
     - once the time is up, a lone ESC means quit and a truncated CSI is dropped;
     - pending bytes are capped at 64.
   - The loop's `select` timeout includes the decoder deadline.
   - `parse_input()` still exists as a final-mode wrapper.
   - Tests in `InputBufferTests`:
     - **every split point** for `ESC[A`, `ESC O B`, `ESC[Z`, a press+release SGR click and an SGR wheel event;
     - byte-by-byte input;
     - a lone ESC fires only after the timeout;
     - a truncated CSI is dropped and not treated as quit;
     - the buffer is capped.
   - The real-pty test also sends `ESC[` and `C` 20 ms apart and checks that the breadcrumb moved to `core / review`.

### Test results

```
cd ~/.config/herdr/local-plugins/pasture && python3 -I -B -m unittest
Ran 32 tests in 0.717s
OK
```

- I ran it 6 times in a row and it passed every time.
- Running the same test file against the pre-fix `pasture.py` fails all the new regression tests: both sanitizer tests FAIL, and the decoder, restore and UTF-8 read tests ERROR.
- In the real-pty test, the first version wrote input before `setraw`, while the pty was still in canonical mode, so the plugin never received it. The test now writes only after the loop has switched to raw mode.
