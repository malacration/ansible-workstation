# Chrome signing key correction — round 2

The legacy one-line source removal expression now requires the end of the line after optional whitespace and an optional comment following `main`. This prevents partial removal of entries with extra components or a component beginning with `main`.

Focused regression checks in `test_legacy_source.py` read the expression from the playbook and apply it using Ansible replace's multiline matching mode. Both reported non-equivalent entries (`main contrib` and `main-extra`) remain unchanged; ordinary equivalent entries, including options, a comment, and a final line without a newline, are removed.

Validation passed: `rtk python3 tasks/chrome-signing-key/test_legacy_source.py` (2 tests), `rtk ansible-playbook browser/chrome.yml --syntax-check`, and `rtk git diff --check`. The syntax check emitted the standard implicit-localhost inventory warning. No playbook or live APT, keyring, or package operation was run.
