---
name: legendarr feature vs. fix branch convention
description: When to use a feature branch + PR vs. committing/pushing straight to main in the legendarr repo
type: feedback
---

New features go on a feature branch with a PR into `main`; bug fixes (`fix:` commits) can be
committed and pushed straight to `main`. This is codified in `AGENTS.md`'s Conventions section
(changed 2026-07-16, previously said *all* work needed a branch+PR, no exception for fixes).

**Why:** the user asked to relax the blanket "always branch + PR" rule specifically for bug
fixes, keeping the heavier feature-branch/PR workflow only for `feat:`-sized work.

**How to apply:** before committing, judge whether the change is a `feat:` (new
capability/refactor of scope) or a `fix:` (bug fix). For `feat:`, create a branch, push it, and
open a PR — never push a feature branch's work directly to `main`. For `fix:`, it's fine to
commit and push directly to `main` if the user asks for that. When in doubt about which bucket
a change falls into, ask rather than assume `fix:` to bypass the PR step.
