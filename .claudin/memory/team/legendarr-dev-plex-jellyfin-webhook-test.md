---
name: legendarr-dev-plex-jellyfin-webhook-test
description: docker-compose.dev.yml has Plex+Jellyfin gated behind the "media-servers" profile (opt-in) for testing the media-server notify webhook; Jellyfin verified end-to-end, Plex blocked on a real plex.tv account claim
type: project
---

`docker-compose.dev.yml` gained `plex` and `jellyfin` services (2026-08-30, PR #99), both
mounting `./dev/media/tv:/media/tv` — the same path legendarr's own container uses, since
both `media_servers` providers match/resolve library items by that exact path (Plex by
prefix-matching a library section's root folder, Jellyfin by direct path lookup).

Both services are gated behind a `media-servers` Compose profile, so a plain
`docker compose -f docker-compose.dev.yml up` only starts `sonarr` + `legendarr` as before;
opt in with `--profile media-servers` to also bring up Plex/Jellyfin. **Compose gotcha:**
gating a service behind a profile isn't enough on its own — if another service's
`depends_on` lists it, Compose auto-activates that dependency's profile too, silently
defeating the gate. `legendarr`'s `depends_on: [plex, jellyfin]` had to be dropped for the
profile to actually keep them off by default.

Jellyfin: wizard completed via Playwright (admin account, library at `/media/tv`, API key
created), configured + enabled in legendarr's Settings → Media Servers
(`base_url=http://jellyfin:8096`). Confirmed working end-to-end: a real translation write
triggered `POST http://jellyfin:8096/Library/Media/Updated` → `204 No Content` in the
legendarr container logs.

Plex: container is up (`http://localhost:32400`) but **unclaimed** — Plex Web forces sign-in
with a real plex.tv account before the server can be claimed and a library/token created, so
setup couldn't be finished without human-provided credentials.

**Why:** user asked to stand both up specifically to verify `notify_media_servers_of_subtitle_write`
(called after acquisition/upgrade/translation writes a subtitle) actually reaches real
Plex/Jellyfin instances, not just unit-test mocks.

**How to apply:** if asked to finish or repeat the Plex side of this test, the blocker is the
plex.tv claim step (needs a human to sign in via the browser, or supply test credentials) —
not a bug in the integration code. See [[legendarr-docker-compose-dev-stack-staleness]] for
the dev compose stack's other gotcha (stale `legendarr` image), and
[[legendarr-dev-db-direct-inspection]] for how the resulting `translationattempt`/
`mediaserverconfig` rows were checked directly.
