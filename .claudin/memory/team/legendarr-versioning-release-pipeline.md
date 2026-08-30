---
name: legendarr-versioning-release-pipeline
description: One version across root + workspace pyproject.toml files, ROADMAP-driven; make bump-version + Release workflow tag/release; Docker publish intentionally still off
type: project
---

Set up in the `feat/release-versioning` branch (2026-08-30): one version, shared by the root
`pyproject.toml` and all three workspace members (`src/backend`, `src/web`, `src/bootstrap`),
kept in lockstep via `scripts/bump_version.sh` (`make bump-version part=patch|minor|major`,
wraps `uv version --bump`/`uv version --package`, which also re-locks `uv.lock`). Version
follows `ROADMAP.md`'s `0.x.0` milestones rather than commit-type-driven semver — bumped by hand
when a milestone's items are fully checked off. The stale placeholder `0.1.0` (never bumped
since project inception) was realigned to `0.22.0` to match the last fully-checked-off
milestone (`0.23.0` is in progress).

Added `.github/workflows/release.yml` (`workflow_dispatch`, `bump: patch|minor|major`): bumps
the version, commits+pushes straight to `main` (mechanical `chore:`, same exception as
`fix:`/`docs:` per [[legendarr-branch-convention]]), tags `vX.Y.Z`, and `gh release create`s
it — that publish event is what `ci.yml`'s existing `docker-build` job (release-triggered,
`push: false`) already listens for. **Not yet enabled: it needs repo Settings → Actions →
General → Workflow permissions set to "Read and write permissions"** — the org/repo default is
currently "read", which silently caps what a workflow's `permissions:` block can request; I did
not flip this myself since it's a security-relevant repo setting, not a code change.

**Docker registry publish deliberately NOT wired up.** `ROADMAP.md`'s `1.0.0` milestone
explicitly gates "publish the Docker image to a container registry" behind every other roadmap
item being done, including `0.23.0` (Subtitle cleanup & editing tools, still has ~10 unchecked
items) — `docs/getting-started/installation.md` already documents this ("CI currently only
builds and tests the image... build it locally instead"). The target registry/name
(`ghcr.io/andersonviudes/legendarr`) is already decided in that doc, just not live. Added OCI
labels to the Dockerfile (`ARG VERSION` + `org.opencontainers.image.*`, defaulting to
`0.0.0-dev` for local builds) and threaded the release tag into `ci.yml`'s validation build as
that ARG, but left `push: false` — flipping it to push (plus `packages: write` + GHCR login) is
the actual `1.0.0` step, intentionally left for when that milestone is reached.
