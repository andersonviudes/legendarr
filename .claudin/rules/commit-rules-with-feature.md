---
paths:
  - ".claudin/rules/**"
  - ".claudin/memory/**"
---

# Commit rules/memory changes with the feature that motivated them

- When implementing a feature or fix touches `.claudin/rules/` (new/edited rule) or
  `.claudin/memory/` (new/updated memory file) *because of that change*, commit those
  files together with the feature's own commit — or include them in the same PR for a
  `feat:` branch — instead of leaving them uncommitted or bundling them into a separate,
  later `chore(memory)`/`chore(rules)` commit.
- Follow the same branch rule as the code: both `feat:` and `fix:` changes with rule/memory
  updates go through their own branch + PR, same as the code change itself (changed
  2026-09-10 — `fix:` used to be allowed straight to `main`, see
  `.claudin/memory/team/legendarr-branch-convention.md`).
- Exception: memory captured about a *past* session (not motivated by the change just
  made — e.g. a retrospective note, a correction unrelated to the current diff) can still
  land in its own standalone `chore(memory): ...` commit.
