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

**2026-07-16 addendum:** `docs:`-only changes (e.g. reordering/editing `ROADMAP.md`, no
application code touched) were also committed and pushed straight to `main` on explicit user
request ("pode comitar na main mesmo"), without a branch/PR — confirmed in practice even though
AGENTS.md's Conventions section only names `fix:` explicitly. Treat pure-`docs:` changes like
`fix:` (direct-to-main is fine if asked), but still ask if a `docs:` change is entangled with
non-trivial code.

**2026-07-22 — proactively put branch/PR steps in the plan itself for `feat:` work:** when
building an `EnterPlanMode` plan for a new feature (e.g. the subtitle-proxy-registration
feature), the initial plan's Tasks list jumped straight into model/router/test work without an
explicit "create the feature branch" task — the user had to reject `ExitPlanMode` and ask
("adiciona ao plano para trabalharmos em uma branch") for it to be added, even though this
convention was already documented in `AGENTS.md` and this file. **Why:** knowing the rule isn't
the same as applying it inside a concrete plan; the plan's task list is what actually gets
executed step-by-step, so if branch creation isn't a task in it, it's easy to skip straight to
implementation on `main`. **How to apply:** for any plan whose scope is `feat:`-sized, add
"create and switch to the feature branch" as the first Tasks entry and "push the branch and
open the PR" as the last, before ever calling `ExitPlanMode` — don't wait for the user to point
this out.
