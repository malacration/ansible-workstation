# Review: herdr Pasture plugin (round 2)

- Level: HIGH → reviewer: mala_reviewer_advanced_codex d7aeeccf (same as round 1).
- Round 1 findings: /tmp/herdr-pasture-review-33107b13.md
- Fix spec: /home/satanas/git/ansible-workstation/tasks/herdr-pasture/FIX_ROUND1.md
- Developer report: /home/satanas/git/ansible-workstation/tasks/herdr-pasture/IMPLEMENTATION.md
  (section "Round 1 fixes")
- Code: /home/satanas/.config/herdr/local-plugins/pasture/ (only pasture.py and test_pasture.py
  changed). Do NOT modify any file.

## Verify

1. HIGH: `safe_text()` applied at `Canvas.put` and `clean_output` removes CSI/OSC (7-bit and C1
   forms), remaining C0/C1/ESC/BEL/DEL and bidi overrides, while keeping ZWJ/accents/emoji. Try
   to bypass it (e.g. DCS/APC/PM/SOS strings, 8-bit CSI 0x9B, split sequences across fields,
   text that reaches the screen without going through Canvas.put, such as the window title).
2. MEDIUM: all CLI captures use utf-8 with errors='replace'; read/focus also catch ValueError.
3. MEDIUM: `restore_terminal()` restores termios in a `finally` independent of output; signal
   handlers restored.
4. MEDIUM: `InputDecoder` incremental buffer with a 50 ms timeout for a lone ESC; fragmented
   CSI/SS3/SGR mouse decoded correctly; check for unbounded buffer growth on garbage input.
5. Regressions elsewhere; CPU loop still not busy-waiting.

Run `cd /home/satanas/.config/herdr/local-plugins/pasture && python3 -I -B -m unittest`
(expect 32 OK). Do not start herdr servers or touch the user's herdr sessions.

## Output

Reply with APPROVED or CHANGES_REQUESTED and numbered findings (file:line, severity, fix).
