---
name: legendarr-pr-title-semantic-lint
description: PR titles are CI-linted with the same subjectPattern as commit-message-convention.md (lowercase start, no trailing period) — not just commit messages
type: feedback
---

Confirmed 2026-08-31 on PR #106: the `lint` CI check (`amannn/action-semantic-pull-request@v5`)
validates the **PR title** itself against `subjectPattern: ^[a-z].*[^.]$` — the same shape
`.claudin/rules/commit-message-convention.md` already requires for commit subjects. `gh pr create
--title 'fix: Live Activity queued-task display and unbounded OCR track duration'` looked fine
but failed CI because the summary after `fix: ` started with a capital letter (`Live`, copied
from prose); `gh pr edit --title 'fix: live activity ...'` (lowercase) fixed it, and the `lint`
job re-ran and passed automatically on the title edit alone — no new commit or push needed.

**Why:** the convention doc and CI's semantic-pull-request lint enforce the identical pattern,
but only on the PR title — a title written like a natural-language sentence (capitalized first
word) can fail a check that has nothing to do with the commits themselves.

**How to apply:** when running `gh pr create`/`gh pr edit --title`, apply the exact commit
subject rules to the title too — lowercase immediately after `type:` or `type(scope):`, no
trailing period. After opening or retitling a PR, `gh pr checks <n>` (via the Git tool) surfaces
this immediately; editing just the title re-triggers the `lint` job. See
[[legendarr-branch-convention]] for the rest of the branch/PR workflow.
