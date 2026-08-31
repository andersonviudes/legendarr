---
paths:
  - ".github/workflows/release.yml"
  - ".github/workflows/reusable-test.yml"
  - "scripts/bump_version.sh"
  - "cliff.toml"
---

# Release pipeline

`.github/workflows/release.yml` (`workflow_dispatch`, pick `bump: patch|minor|major` from the
Actions tab) does, in order:

1. Run the shared test job (`reusable-test.yml`).
2. Bump the version with `scripts/bump_version.sh` — working tree only, not committed yet.
3. Build a `linux/amd64` image (`--load`) and smoke-test it locally (`docker run` + poll `GET /`
   up to 30s).
4. Push a multi-arch (`linux/amd64,linux/arm64`) image to
   [Docker Hub](https://hub.docker.com/r/andersonviudes/legendarr), tagged both `vX.Y.Z` and
   `latest`.
5. Sync Docker Hub's Repository Overview (`peter-evans/dockerhub-description@v4`) from the root
   `README.md`, with its repo-relative logo/`LICENSE`/`docker-compose.example.yml` links
   rewritten to absolute GitHub URLs first — Docker Hub's renderer can't resolve repo-relative
   paths.
6. Regenerate `docs/changelog.md` and the release notes with [git-cliff](https://git-cliff.org)
   (`cliff.toml`, grouped by the commit types `.github/workflows/pr-title.yml` enforces).
7. Commit the version bump + changelog as `chore: bump version to vX.Y.Z [skip ci]` straight to
   `main` — the `[skip ci]` is why steps 3-5 happen *before* this commit, using the
   not-yet-committed version.
8. Tag `vX.Y.Z` and push the tag.
9. Create the GitHub Release (categorized changelog + compare link, `image-digest.txt`,
   `docker-compose.example.yml` as assets).
10. Manually re-trigger `docs.yml` (`gh workflow run docs.yml`) — `[skip ci]` also blocks its
    own push-triggered deploy, so the refreshed changelog page wouldn't otherwise go live until
    some unrelated docs change.

One version, shared by the root `pyproject.toml` and every workspace member (`src/backend`,
`src/web`, `src/bootstrap`) — always keep them in lockstep, since they ship as one Docker image.
Bump locally for testing only with `make bump-version part=patch|minor|major` (wraps
`scripts/bump_version.sh`, which re-locks `uv.lock` too) — this never publishes anything.

**One-time manual setup this depends on** (not doable from a session — flag it if either looks
unset rather than assuming a release run will just work): (1) repo Settings → Actions → General
→ Workflow permissions → "Read and write permissions", for the default `GITHUB_TOKEN` to
push/tag/release; (2) a Docker Hub access token (Docker Hub → Account Settings → Security → New
Access Token) stored as the `DOCKERHUB_TOKEN` repo secret, alongside a `DOCKERHUB_USERNAME`
secret — Docker Hub doesn't accept `GITHUB_TOKEN`.

For the history/rationale behind these choices (why Docker Hub over GHCR, why version follows
`ROADMAP.md` milestones instead of commit-type semver, verification caveats), see
`.claudin/memory/team/legendarr-versioning-release-pipeline.md`.
