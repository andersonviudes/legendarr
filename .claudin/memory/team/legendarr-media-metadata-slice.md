---
name: legendarr media metadata slice
description: TheTVDB/TMDb/IMDb metadata provider registration, fetch-on-sync/manual/periodic refresh, and the local poster cache + cleanup job — media_metadata slice
type: project
---

Built 2026-08-01 on `feat/metadata-source` (PR #24): a Settings → "Metadata source" page
to register TheTVDB and IMDb as metadata providers, plus real fetch-on-sync — unlike
`subtitle_acquisition`'s deliberate registration-only-first increment (see
`legendarr-roadmap-basis`), the user explicitly asked for full integration in one pass,
confirmed via AskUserQuestion before planning.

**Shape**: backend slice `media_metadata/` mirrors `subtitle_acquisition`'s fixed-catalog
pattern (`MetadataProviderConfig`, one row per kind, seeded at startup) but seeds
**`enabled=True`** by default (subtitle providers seed `False`) — an explicit, confirmed user
ask ("deixa marcado"). What actually gates a fetch attempt is `has_credentials`
(`api_key` set), not the `enabled` flag. `MediaMetadata` table (one row per `Movie`/
`Series`, unique on movie_id/series_id, mirrors `MediaFile`'s shape) stores fetched
`overview`/`poster_url`/`year`/`imdb_rating`.

**"IMDb" is backed by OMDb** (omdbapi.com) — IMDb itself has no free public API. The `kind`
is still stored/labeled `"imdb"` everywhere; only the HTTP client underneath
(`OmdbMetadataProvider`) is OMDb's. TheTVDB uses the v4 API, API-key-only login (no `pin`).

**Fetch keys**: `Movie`/`Series` gained plain `tvdb_id`/`imdb_id` columns, populated from
Radarr/Sonarr's own sync response. Confirmed by reading Radarr/Sonarr's API shape:
**Radarr movies never report a `tvdbId`** (Radarr's own canonical id system is TMDb) — only
`imdbId`. So the TVDB client falls back to a title search for movies; series always fetch by
id on both sources.

**TMDb added as a third provider** (2026-08-27, `feat/tmdb-metadata-provider`, still local/
unpushed at that point) as a gap-filler between the other two. Merge policy
(`fetch_metadata.py::_merge`) updated: TheTVDB is still authoritative for
`overview`/`poster_url`/`year`; **TMDb only fills in whichever of those TheTVDB left
empty** (order between TVDB/TMDb doesn't matter because of this); IMDb/OMDb only ever
contributes `imdb_rating`, the one field neither of the others has.

**Manual "Refetch All" bulk action** added the same day, stacked as a second commit on the
same still-unpushed branch (touched `fetch_metadata.py` a second time, so splitting cleanly
onto a fresh branch wasn't practical — see [[legendarr-branch-convention]] for context if this
recurs). Settings → Metadata source gained a "Refetch All" button that fans out a per-item
metadata (re)fetch job for every existing movie/series, mirroring `media_library`'s manual
full-library-scan pattern: own `JobQueue.METADATA_BULK` queue, `media_metadata/jobs.py`, one
job per item, config-driven `metadata_refetch_retry_attempts`/
`metadata_refetch_retry_delay_seconds` (manual-only, no periodic schedule — same precedent as
`timing_sync`). This also fixed a latent bug: `_fetch_and_store` previously only handled the
insert path, so refetching an item that already had a `MediaMetadata` row would have hit the
movie_id/series_id unique-constraint on insert; it now overwrites the existing row in place
(verified against the real dev stack: same row `id`, newer `fetched_at`, on a second click).

**Confirmed gap (2026-08-27, from a direct user question)**: no local image caching and no
periodic metadata refresh. `poster_url` is stored and served as a straight hotlink to the
provider's own CDN (e.g. `image.tmdb.org`) — legendarr never downloads/proxies the image
itself, so caching is whatever the browser/provider CDN does on its own. And metadata for an
*existing* item only ever updates on a brand-new-item sync or a manual "Refetch All" click —
there's no `IntervalTrigger`-based job (unlike `register_sync_job`/`register_scan_job` in
`media_library`) that periodically re-pulls metadata for items already in the library, so
upstream changes (a corrected poster, an updated rating) don't propagate until someone clicks
refetch again. **Backlogged** the same day at the user's request ("adiciona isso no
backlog"): `ROADMAP.md` 0.21.0 — Resilience gained an unchecked `**Media library**` bullet
covering both (commit `bb1a145`, pushed straight to `main` as a `docs:` change per
[[legendarr-branch-convention]]) — not implemented yet, just tracked.

**Cadence added in a follow-up commit** the same day (`0c59a4d`, also `docs:` direct-to-
`main`): the bullet now names a concrete default — `metadata_refresh_interval_minutes`, once
a day, config/env only (same posture as `translate_interval_minutes`), reasoned as "metadata
changes far less often than library contents" vs. the 15/60 min cadence the sync/scan/
history-poll jobs use.

**Implemented 2026-08-27** on `feat/media-poster-cache`, closing the 0.20.0 bullet (checkbox
now `[x]`). Poster download is wired straight into `fetch_metadata._fetch_and_store` (a new
private `_cache_poster(media_type, media_id, poster_url)`, plain `httpx.get` — not a
`ProviderHttpClient`, since that class models one fixed `base_url` per provider, not a
one-off arbitrary-CDN-host download), so every existing caller (first-sync, manual
"Refetch All", and the new periodic job) gets caching for free. `MediaMetadata` gained one
column, `poster_cached_at: datetime | None` — the sole "is this cached" signal, surfaced as
`poster_cached: bool` on `MediaRead`/`WantedRead` via `list_media_library.metadata_fields()`.

**Serving is a shared static-file mount, not a backend HTTP proxy** — confirmed directly with
the user over the alternative (proxying poster bytes through `legendarr_web`'s
`get_backend_client`, which would have stayed inside the auth gate). Backend writes to
`Settings.poster_cache_dir` (`data_dir/posters/{kind}_{id}.jpg`, always `.jpg` regardless of
the real `Content-Type` — TMDb/TheTVDB/OMDb all serve JPEG in practice, and Starlette's
`StaticFiles` sets `Content-Type` from the file extension, not a stored value);
`legendarr_web/app.py` mounts that same directory at `/posters` (needs `WebSettings.data_dir`,
a new field mirroring the backend's). **Explicitly accepted trade-offs**, both surfaced and
confirmed: this mount is unauthenticated-by-ID (same as `/static` today, not behind
`require_authenticated_session`), and backend+web are now coupled to a shared filesystem path
instead of talking only over HTTP — a first for this codebase, only safe because
`legendarr_bootstrap` always runs both in one process/container. Templates
(`movies.html`/`series.html`/`wanted.html`/`movie_detail.html`/`series_detail.html`) gate the
`<img>` on `poster_cached` with **no hotlink fallback** to `poster_url` while a poster isn't
cached yet — also an explicit user choice over the "graceful degrade" alternative.

Two new independent scheduled jobs in `media_metadata/jobs.py`, both on the existing
`JobQueue.METADATA_BULK` (no new queue — neither needs its own concurrency pool):
`register_metadata_refresh_job` (`metadata_refresh_interval_minutes`/`_retry_attempts`/
`_retry_delay_seconds`/`_max_instances`/`_coalesce`, own config fully independent from the
manual button's `metadata_refetch_*` — also an explicit user choice) just calls the existing
`enqueue_metadata_refetch` on a schedule; `register_poster_cache_cleanup_job`
(`poster_cache_cleanup_interval_minutes`/... same 5-field shape, also its own schedule rather
than folded into the refresh job — third explicit user choice) sweeps `poster_cache_dir` via
a new `media_metadata/poster_cache_cleanup.py::cleanup_orphaned_posters`, deleting any
`{kind}_{id}.jpg` with no matching `Movie`/`Series` row — the only way a file orphans, since a
refetch overwrites the same filename in place.

Full plan/rationale (including the alternatives considered for each of the four confirmed
decisions above) is in the now-consumed plan file; this memory is the durable record.

**Resolved**: the "explicitly out of scope" note this memory used to carry (surfacing
`poster_url`/`overview` on `/media/movies`/`/media/series`, tracked at
[[legendarr-media-library-list-ui-not-wired]]) is done — those pages now render a poster-grid
using `show.poster_url` directly (confirmed via Playwright screenshot, 2026-08-27).

**Why:** avoids re-deriving the OMDb-for-IMDb decision, the Radarr-has-no-tvdbId gap, the
three-way merge policy, or the refetch upsert fix from scratch; the caching/periodic-refresh
note saves re-investigating the same question if it comes up again in a roadmap discussion.

**How to apply:** when extending metadata fetch (new fields, new sources), read
`media_metadata/fetch_metadata.py`'s `_merge` function first — it's the single place the
TVDB-wins/TMDb-fills-gaps/IMDb-rating-only policy lives. When touching the poster cache
(new provider, different storage), read `_cache_poster` in that same file and
`poster_cache_cleanup.py` first — periodic refresh and cleanup are both implemented now (see
above), not a gap to plan from scratch.
