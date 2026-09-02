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

**2026-08-27 — user directs "work only on this feature branch this session," including a
`fix:`; staging around unrelated pre-existing uncommitted WIP on the same branch:** started a
session on `main` (per the conversation's own `gitStatus` snapshot), but by the time work
began the checked-out branch had silently become `feat/tmdb-metadata-provider` with a large,
unrelated, uncommitted diff already in the working tree (the user's own in-progress work on
another machine/terminal, not something this session created — see
[[background-agents-switch-branches]] for the sibling case where an *agent* causes this; here
it was pre-existing state, discovered via `git status` before the first commit). Surfaced it
instead of assuming `main`; user replied "faz direto na nossa branch feat/tmdb-metadata-provider
vamos trabalhar so nela nessa sessao" — explicit permission to commit both the `fix:` (a
logging bug) and a follow-up `feat:` straight onto that branch, no new branch, no PR this
session. **Why:** the literal branch convention above (`fix:` → `main`, `feat:` → its own
branch+PR) is the *default*, not an override of an explicit, contemporaneous user instruction
about which branch to commit to.

Four files (`i18n/locales/{en,es,pt-BR}.json`, `static/styles.css`) had the user's unrelated WIP
and this session's new lines in the *same file*, so `git add <file>` would have swept the WIP
into this session's commit. Fix: for each such file, copied the file's *own* hunk (identified by
diffing against HEAD and picking out the hunk whose content matched what this session added) into
a hand-built unified diff — `diff --git a/<path> b/<path>` / `--- a/<path>` / `+++ b/<path>` /
one `@@` hunk — and ran `git apply --cached -` (patch on stdin via a Bash heredoc, since a
worktree-scratch file was denied by the sandbox — writes outside the repo aren't permitted) to
stage just that hunk into the index, leaving the rest of the file's diff unstaged. Confirmed with
`git diff --cached -- <file>` before committing that each staged diff was hunk-for-hunk exactly
this session's addition. **How to apply:** when a target file has *other* uncommitted changes
already in the working tree that aren't part of the current change, don't `git add` the whole
file — `git diff -- <file>` to find your own hunk's `@@ -old,n +old,n @@` header (using the
*original*, i.e. pre-my-changes, line numbers — `git apply --cached` resolves them against the
index, which is HEAD's content, unaffected by any other unstaged hunk in the same file), wrap it
in a minimal `diff --git`/`---`/`+++` header, and `git apply --cached -` it via a heredoc. Verify
with `git diff --cached` before committing. `git add -p` (interactive) is the standard tool for
this but isn't practical to drive non-interactively; the hand-built-patch approach is the
scriptable equivalent.

**2026-08-29 — a scratch `fix:` branch is disposable, and `git push origin main` can race with
a PR merging mid-session:** this round's UI-polish fixes had accumulated on a local-only branch
`chore/ui-fine-tuning` (6 `fix:` commits, never pushed to `origin`). Once `main` was
fast-forwarded to its tip (per the pattern above), the branch was deleted since it added nothing
further — but the user then asked to switch back to it by name ("switcha pra branch
chore/ui-fine-tuning"). Recreated it fresh at the current `main` tip
(`git checkout -b chore/ui-fine-tuning main`) rather than treating the name as gone for good.
**How to apply:** treat a scratch branch used only to stage `fix:` commits before they land on
`main` as disposable — safe to delete once fully merged, and just as safe to recreate under the
same name at `main`'s tip if the user asks for it back.

**2026-08-30 — "abre um pr" asked reflexively when there's nothing to PR:** after a `fix:` commit
was already pushed straight to `main` per the convention above, the user asked "abre um pr" again
with a clean working tree and no new commits since — not a new request, just the same habitual
phrase. Rather than reverting the already-pushed fix to redo it on a feature branch, or silently
ignoring the request, asked via `AskUserQuestion` whether to leave it as-is (recommended — a PR
against an unchanged `main` has no diff to review), revert-and-redo via branch+PR, or that
something else was intended; the user picked "already correct." **Why:** "abre um pr" is
sometimes just this user's shorthand for "wrap this up properly," not a literal instruction to
override the branch convention or a sign that something is actually pending — treating it as an
unconditional command risks an unnecessary, disruptive rewrite of an already-verified fix.
**How to apply:** before opening a PR or reverting/rebranching a `fix:` already on `main`, check
`git status`/`git log` first — if there's no pending diff and the last change already followed
the fix-direct-to-main convention correctly, clarify intent instead of assuming a revert is
wanted.

**2026-09-02 — recurrence: branch creation AND per-task test coverage must be literal
Tasks list entries, not just an Agreed Decisions bullet or a single end-of-plan test
task:** building a plan for the upgrade-job score/threshold/recheck-window feature,
"Feature branch + PR" was recorded under **Agreed Decisions** (not as a `- [ ]` Tasks
entry) and the Tasks list ended with one generic "lint, typecheck, full test suite" item
with no explicit per-change unit-test tasks. `ExitPlanMode` was rejected with "adiciona
para trabalharmos em uma branch e testar no final e cobrir com testes unitários" — the
same root cause as the 2026-07-22 entry above (knowing the rule isn't the same as
encoding it in the plan's actual Tasks list), now recurring a second time and extended
to explicitly cover test coverage too. **How to apply:** for any `feat:`-sized plan,
before calling `ExitPlanMode`: (1) add "create the feature branch" as the literal first
`- [ ]` Tasks entry, not just an Agreed Decisions bullet; (2) give implementation tasks
that touch testable logic their own paired "add/update tests for X" Tasks entries as you
go, not one bundled test task saved for the end; (3) still keep a final "lint,
typecheck, full test suite" task as the last entry. Do this by default — don't wait for
the user to reject `ExitPlanMode` a third time.

Separately, `git push origin main` was rejected ("the remote contains work you do not have")
after two small `chore:`/`docs:` commits were made directly on local `main`: a `feat:` PR opened
earlier the same session had been squash-merged into `origin/main` in the meantime (by the user,
outside this session), so local and remote `main` had diverged. **Why:** this repo's PRs can get
merged while other direct-to-main work is still in flight in the same session, especially when a
session interleaves feature-branch and fix-branch work. **How to apply:** a `git push origin
main` rejection mid-session isn't necessarily a mistake — `git fetch origin main` and look at
what landed before assuming anything is wrong. If the new commits touch different files than the
merged PR (as here — a `ROADMAP.md`/rules-stats chore vs. a feature PR's application code),
`git rebase origin/main` resolves cleanly with no conflicts; push again after.
