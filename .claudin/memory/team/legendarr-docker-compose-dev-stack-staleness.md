---
name: legendarr-docker-compose-dev-stack-staleness
description: docker-compose.dev.yml's legendarr container silently runs a stale image for weeks unless rebuilt; how to check and fix
type: project
---

The `legendarr` service in `docker-compose.dev.yml` (local dev stack against real Sonarr,
see [[legendarr-architecture]]) is built once with `build: .` and then left running with
`restart: unless-stopped`. Nothing rebuilds it automatically, so it can silently run code
from weeks before `main` while `docker compose ps` shows it healthy and serving 200s —
found 2026-08-24 debugging a report that subtitles present on disk weren't showing in the
UI: the running container's `scan_video_subtitles()` had an older signature (no
`extract_embedded`/`ocr_embedded` params) than current `main`, from before the PGS OCR
feature (#58) landed.

**Why:** `docker exec <container> python3 -c "import inspect; ...; print(inspect.signature(...))"`
is the fast way to confirm whether a running container's code actually matches the repo
before debugging further — comparing `docker inspect --format '{{.Created}}'` against
recent commits works too, but signature/behavior diffing is more direct.

**How to apply:** after any backend/web change relevant to manual dev-stack testing, run
`docker compose -f docker-compose.dev.yml build legendarr && docker compose -f
docker-compose.dev.yml up -d legendarr` to pick it up — the `./dev/legendarr-config` bind
mount (SQLite DB + config) persists across the rebuild, so this is safe and doesn't lose
data. `docker compose up -d legendarr` alone (no `build`) will NOT rebuild even if the
Dockerfile or source changed.
