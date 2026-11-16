# Fix round 1: herdr Pasture plugin (review CHANGES_REQUESTED)

- Level: HIGH (unchanged; 1st rejection). Developer: mala_developer_high_claude, same terminal
  5767df2f (original author). Next reviewer: mala_reviewer_advanced_codex d7aeeccf.
- Spec: /home/satanas/git/ansible-workstation/tasks/herdr-pasture/TASK.md
- Full review: /tmp/herdr-pasture-review-33107b13.md
- Code: /home/satanas/.config/herdr/local-plugins/pasture/ (local only, outside the repo)

## Findings to fix

1. `pasture.py:298` (HIGH, security): labels, metadata and error text enter the Canvas
   unsanitized; reviewer reproduced `ESC[2J` via a label and OSC 52 (clipboard write) via an
   error message reaching the final ANSI output. Strip/replace C0 and C1 control characters
   (incl. ESC, BEL, 0x80–0x9F) from ALL external text, ideally at the Canvas' single text entry
   point, and also in workshed output. Tests for labels, errors and agent output.
2. `pasture.py:491` (MEDIUM): `text=True` decodes strictly; byte 0xff in `agent read` raises an
   unhandled UnicodeDecodeError and kills the plugin. Use `encoding='utf-8', errors='replace'`
   for all subprocess captures; tests for stdout/stderr on the read and focus paths.
3. `pasture.py:655` (MEDIUM): a failing write/flush during cleanup skips `tcsetattr`, leaving the
   terminal in raw mode. Restore termios in a `finally` that does not depend on output
   succeeding; test with a broken stdout.
4. `pasture.py:636` (MEDIUM): fragmented reads lose sequences (`ESC[` then `A` loses the arrow;
   fragmented SGR mouse is lost). Add an incremental input buffer with a short timeout for a lone
   Escape; test every split point.

## Constraints

- Touch only files in ~/.config/herdr/local-plugins/pasture/. Do not touch the
  ansible-workstation repo except this tasks dir, the herdr config.toml, or real herdr sessions
  (throwaway session only if needed, deleted afterwards). Do not commit.

## Reporting

Append a "Round 1 fixes" section to
/home/satanas/git/ansible-workstation/tasks/herdr-pasture/IMPLEMENTATION.md with changes and
`cd ~/.config/herdr/local-plugins/pasture && python3 -I -B -m unittest` results, then report back.
