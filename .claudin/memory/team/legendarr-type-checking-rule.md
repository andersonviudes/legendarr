---
name: legendarr type-checking rule
description: pyright is now wired up (pyrightconfig.json) and enforced via .claudin/rules/type-checking.md, added 2026-08-11
type: project
---

Added `pyrightconfig.json` (repo root) pointing pyright at the `uv` workspace's `.venv` —
without it pyright can't resolve any workspace import and reports hundreds of false
positives on every file. PR #32 fixed the 289 real diagnostics this then surfaced (mostly
SQLModel `int | None` primary keys flowing into non-optional parameters, and
`Model.column.in_()` calls untyped by SQLModel — fixed with `sqlmodel.col()`).

Added `.claudin/rules/type-checking.md` (scoped to `src/**/*.py` via `paths`, same trigger
as [[legendarr-clean-code-solid-rule]] and the Python conventions rule) requiring the
`Typecheck` tool / `uv run pyright` to be run alongside `make lint` and `make test` before
considering any Python change done.

**Why:** pyright is *not* wired into `.github/workflows/ci.yml` yet — CI still only runs
`make lint` and `make test` (see `AGENTS.md`) — so nothing else catches type errors on new
code until this rule is followed manually.

**How to apply:** when touching `src/**/*.py`, run the `Typecheck` tool before reporting a
change done, same as `make lint`/`make test`. If `pyrightconfig.json` or the CI workflow
changes to add pyright as a real CI gate, update this memory and drop the "not wired into
CI" caveat above.
