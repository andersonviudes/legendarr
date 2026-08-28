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

**Alternative for browser/Playwright QA on a feature branch:** skip the compose stack
entirely — point `LEGENDARR_DATA_DIR` at a throwaway directory, run
`uv run uvicorn legendarr_bootstrap.app:app --host 127.0.0.1 --port <port>` in the
background on that branch, drive it with the Playwright MCP tools, then kill the process
and delete the throwaway dir. Guarantees the code under test instead of whatever the
container last had baked in. Used 2026-08-26 to manually verify PR #65 (i18n) across
en/es/pt-BR on every settings page.

**Update (2026-08-28) — stale container caused a false routing-bug investigation:** hit this
again while manually verifying a brand-new `/settings/backup/` page: `GET /settings/backup/`
returned a 405 with `Allow: POST`, which looked exactly like a real route-collision bug (real
effort was spent theorizing about Starlette's `redirect_slashes`/route-registration-order
semantics against the pre-existing `language_profiles` router's dynamic `/settings/{profile_id}`
route). The actual cause was this same gotcha: `docker ps` showed `legendarr-legendarr-1`
`Up 5 hours` on port 8000, serving code from before the backup slice existed at all —
`curl localhost:8000/api/openapi.json` had zero `backup` paths, confirming it. **How to apply:**
before debugging *any* unexpected HTTP status on a route that was just added, check `docker ps`
for a same-project container bound to the port under test first — if its uptime predates the
change, that's the cause, not a real routing bug; don't reach for route-matching-internals
theories until that's ruled out. This time the user explicitly wanted to test on the *real* port
8000 rather than isolate (per [[legendarr-live-test-on-8000-preference]]): `docker stop
legendarr-legendarr-1` (leaves sibling containers — sonarr/postgres/redis — untouched) then
`make run` in the background reclaims 8000 with current code — the bootstrap entrypoint
(`src/bootstrap/src/legendarr_bootstrap/__main__.py`) hardcodes `host="0.0.0.0", port=8000`, so
no env var is needed to bind it there.
