# Chrome signing key review

## Change

`browser/chrome.yml` downloads Google's published ASCII signing key on every run (replacing it only when content differs), installs it as a world-readable APT keyring, and configures the Chrome source with `signed-by` before updating the package cache. It removes matching legacy one-line Chrome entries elsewhere and updates the key reference in the existing `chrome-stable` deb822 source. The pre-existing dependency installation and `changed_when: false` edits remain in place. TLS and APT signature validation remain enabled.

## Evidence

- Google publishes the key and documents ASCII keyrings for modern APT: https://www.google.com/linuxrepositories/
- Ansible documents `get_url` force behavior: https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/get_url_module.html
- APT documents source formats and `Signed-By`: https://manpages.debian.org/bookworm/apt/sources.list.5.en.html
- Ansible documents the APT module dependency and automatic installation behavior: https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/apt_module.html
- `ansible-playbook browser/chrome.yml --syntax-check`, `--list-tasks`, `ansible-playbook all.yml --syntax-check`, and `git diff --check` passed. The aggregate syntax check reports existing deprecation warnings in unrelated playbooks.
- A focused local Python check exercised legacy source removal, canonical source matching, the actual existing `chrome-stable` stanza, repeated replacement, and preservation of an unrelated source. No playbook, live APT operation, keyring modification, or package installation was run.

## Limits for review

The initial HTTPS request requires a functioning system TLS trust store; the play installs `ca-certificates` after the key and sources are repaired so a broken Chrome repository cannot block the initial cache refresh. The deb822 rewrite targets the existing `chrome-stable` URI and a same-stanza `Signed-By` field; arbitrary deb822 arrangements, alternate Chrome repository variants, and unrelated broken APT sources are not normalized. Multiple matching lines inside the managed `google-chrome.list` are not deduplicated. Full live convergence and package post-install behavior were not tested.
