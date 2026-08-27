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

**2026-08-26 — stacking `fix:` commits onto an active feature branch instead of switching to
`main`:** while iterating on UI polish on `feat/dashboard-redesign` (a branch already several
commits ahead of `main`, including an earlier `fix(web): flatten the System > Tasks page`
commit), several unrelated `fix:`-sized changes (a CSS specificity bug, a poster-grid layout
bug, toolbar padding) were committed directly onto that feature branch rather than switching to
`main` first. **Why:** the files being fixed (`styles.css`, `macros.html`) had already
diverged substantially between `main` and the feature branch from earlier commits in the same
stack, so switching to `main` with the fix as uncommitted changes risked a messy/conflicting
checkout; committing onto the already-open feature branch was the safer, and evidently
established, path in this repo when a fix's target files are mid-refactor on a long-lived
branch. **How to apply:** the literal "`fix:` can go straight to `main`" rule is *permission*,
not a *requirement* — when the fix touches files that a currently-checked-out, unmerged feature
branch has already changed, prefer committing the fix onto that branch over a risky
`git checkout main` with conflicting uncommitted edits. Only actually switch to `main` for a
fix when the working tree is clean of unrelated feature work and the touched files haven't
diverged.

**2026-08-27 — landing an isolated docs/chore change while a feature branch has unrelated
stacked commits:** to add a `ROADMAP.md`-only line while `feat/tmdb-metadata-provider` had two
unpushed `feat:` commits stacked on top of it, used `git stash push -- <file>` to shelve just
that one file, `git checkout main`, `git stash pop`, commit + push straight to `main` (per the
`docs:`-direct-to-main rule above), then `git checkout` back to the feature branch. **Why:**
lands the docs commit on `main` immediately instead of it waiting on that branch's eventual PR,
without disturbing the feature branch's own state. **Side effect to expect:** switching
branches when the two branches' tracked files differ triggers a wave of "file was modified,
either by the user or by a linter" system reminders for every file that differs between them —
this is normal branch-diff noise from `checkout`, not a real edit; don't try to "restore" those
files and don't mention the noise to the user.

**2026-08-27 — undoing a `fix:` commit already pushed to `main`:** asked to remove a `fix:`
commit from `main` and keep it only on the feature branch that had already merged it, offered
two explicit options via `AskUserQuestion` — `git revert` (new commit undoing the change,
doesn't rewrite already-published history) vs. `git reset --hard` + force-push (erases the
commit from `main`'s history entirely, riskier since it's already on `origin`) — instead of
picking one. The user chose `git revert`. **Why:** rewriting a shared branch's already-pushed
history is a destructive, outward-facing action (per the harness's confirm-first rule) with a
real difference in risk between the two methods, not a judgment call to make unilaterally.
**How to apply:** for any request to undo/remove a commit already pushed to `main` (or another
shared branch), ask which method before running either — default recommendation is `git
revert`, since it's non-destructive and doesn't require `--force`; only reset+force-push if the
user explicitly wants the commit erased from history. See [[legendarr-animetosho-anidb-key]]
for the case that prompted this.
