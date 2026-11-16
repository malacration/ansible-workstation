# Chrome signing key review

## Finding

**P2 — Legacy source removal can corrupt a non-equivalent source** ([browser/chrome.yml](/home/andrew/git/ansible-workstation/browser/chrome.yml:34)). The removal expression has no end-of-line boundary after `main`, so it matches only the prefix of a source with additional components or a component beginning with `main`. For example, `deb https://dl.google.com/linux/chrome/deb/ stable main contrib` becomes `contrib`, and `stable main-extra` becomes `-extra`. The remaining text is invalid APT syntax and can make the subsequent cache update fail. These lines are not equivalent to the targeted stable/main source and must be preserved. Require the remainder of the line to consist only of optional whitespace and an optional comment before the newline or end of file; add focused checks for both non-equivalent examples alongside an ordinary matching line.

The observed `/etc/apt/sources.list.d/google-chrome.sources` stanza matches the deb822 rewrite, which updates its key reference before the first explicit APT task. The key download uses HTTPS with normal certificate validation, refreshes the key, and installs it with a readable mode; the managed one-line source uses HTTPS and an explicit `signed-by`. Review was read-only apart from this report: a focused Python regex reproduction confirmed the finding, and the previously reported syntax and replacement checks were not rerun. Live APT convergence and Chrome package post-install behavior remain unverified.

**Verdict: CHANGES REQUESTED**
