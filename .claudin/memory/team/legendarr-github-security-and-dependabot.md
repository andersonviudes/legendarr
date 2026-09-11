---
name: legendarr-github-security-and-dependabot
description: What's enabled under the repo's Code security settings, what silently isn't (and why), and the Dependabot config's four ecosystems
type: reference
---

Turned on 2026-09-11 via `gh api`, on top of secret scanning + push protection which were
already on:

| Feature | Endpoint | State |
|---|---|---|
| Dependabot alerts | `PUT /repos/{o}/{r}/vulnerability-alerts` | enabled |
| Dependabot security updates | `PUT /repos/{o}/{r}/automated-security-fixes` | enabled |
| Private vulnerability reporting | `PUT /repos/{o}/{r}/private-vulnerability-reporting` | enabled |
| Code scanning (CodeQL default setup) | `PATCH /repos/{o}/{r}/code-scanning/default-setup` | configured, `query_suite: extended` |
| Secret scanning non-provider patterns | `PATCH /repos/{o}/{r}` | **not enabled** |
| Secret scanning validity checks | `PATCH /repos/{o}/{r}` | **not enabled** |

**Two traps worth remembering.** The code-scanning default-setup endpoint takes **`PATCH`, not
`PUT`** — `PUT` answers `404 Not Found`, which reads like a permissions problem and isn't. And
`PATCH /repos/{o}/{r}` with `secret_scanning_non_provider_patterns`/`secret_scanning_validity_
checks` returns **`200` while changing nothing**: those are GitHub Secret Protection features
that a free public repo isn't entitled to, and the API ignores them instead of refusing. Always
read the setting back rather than trusting the response code.

CodeQL runs `extended` (the security-and-quality suite) over `python`,
`javascript-typescript` and `actions`. The `languages` array reads back empty from the API until
the first analysis finishes — check the run's job names instead. The JS analysis covers 17
first-party files under `src/web/src/legendarr_web/static/js/`; only `vendor/htmx.min.js` is
third-party.

**`.github/dependabot.yml` — four ecosystems**, one per dependency surface, all weekly on Monday
in `America/Sao_Paulo`, each grouping minor+patch into a single PR and leaving majors on their
own:

- `uv` at `/` — the workspace's Python deps. One entry, not one per member: `[tool.uv.workspace]`
  resolves all three members through the single root `uv.lock`. GitHub's docs say nothing about
  uv workspaces, so if member-only deps turn out to be missed the documented fallback is
  `directories: ["/", "/src/*"]` + `group-by: dependency-name`.
- `pip` at `/docs` — the MkDocs toolchain in `docs/requirements.txt`, which never reaches the
  shipped image.
- `github-actions` at `/` — covers every file in `.github/workflows`.
- `docker` at `/` — **only bumps the first `FROM`** (the `ghcr.io/astral-sh/uv` builder stage).
  The `python:3.12-slim-bookworm` runtime stage in the second `FROM` still needs bumping by hand.

`commit-message.prefix` is set per ecosystem (`chore`/`ci`/`build`) with `include: "scope"`, so
titles come out as `chore(deps): bump ...` — a type `.github/workflows/pr-title.yml` accepts,
with a summary that starts lowercase as its `subjectPattern` requires (see
[[legendarr-pr-title-semantic-lint]]).

**Don't add a `reviewers:` key** — GitHub removed that option on 2025-08-08. `.github/CODEOWNERS`
(`* @andersonviudes`) is the replacement and is what gets Dependabot's PRs reviewed. It costs
nothing on PRs the owner opens themselves, since GitHub never requests review from a PR's own
author. `main` is unprotected, so nothing here *blocks* a merge — if branch protection with
"require review from Code Owners" is ever turned on, that rule would make the sole maintainer
unable to merge their own PRs.
