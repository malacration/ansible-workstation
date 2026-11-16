# Review: herdr Pasture plugin (round 1)

- Level: HIGH → reviewer: mala_reviewer_advanced_codex (Codex, cross-model; new terminal because
  b6a13d4f is reviewing herdr-pastor round 2).
- Spec: /home/satanas/git/ansible-workstation/tasks/herdr-pasture/TASK.md
- Developer report: /home/satanas/git/ansible-workstation/tasks/herdr-pasture/IMPLEMENTATION.md
- Code (outside the repo, local only): /home/satanas/.config/herdr/local-plugins/pasture/
  (herdr-plugin.toml, pasture.py, test_pasture.py, README.md). Do NOT modify any file.

## Focus

- Correctness vs spec: state mapping (working → wandering, blocked → need you,
  idle/done/unknown → resting), counters, sign/workspace grouping + Tab, workshed output,
  keys (arrows/hjkl, Enter focus, q/Esc, mouse click), terminal resize, small terminals.
- Robustness: herdr CLI errors/timeouts, agents appearing/disappearing, non-UTF-8 output, the
  terminal is always restored (raw mode, alt screen, mouse reporting) on exit, exceptions and
  SIGTERM/SIGHUP when the pane closes.
- Safety: subprocess calls use argv lists (no shell injection from agent/pane names or
  output), escape sequences from agent output cannot break the plugin's rendering or inject
  terminal control codes into the host terminal.
- CPU usage: polling/animation loop must not busy-wait.
- Side effect: herdr wrote ~/.config/herdr/plugins.json (global registration, the plugin shows up
  in every session including `cao`). Judge whether that harms anything; report only.
- Tests: run `cd /home/satanas/.config/herdr/local-plugins/pasture && python3 -I -m unittest`
  if your tools allow (expect 18 OK).

Do not start herdr servers or touch the user's herdr sessions (default, cao).

## Output

Reply with APPROVED or CHANGES_REQUESTED and numbered findings (file:line, severity, fix).
