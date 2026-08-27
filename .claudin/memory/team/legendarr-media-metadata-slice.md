---
name: legendarr media metadata slice
description: TheTVDB/TMDb/IMDb metadata provider registration, fetch-on-sync, and manual "Refetch All" — media_metadata slice, confirmed poster-cache/periodic-refresh gap
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

**Confirmed gap (2026-08-27, from a direct user question, not yet on ROADMAP.md)**: no local
image caching and no periodic metadata refresh. `poster_url` is stored and served as a
straight hotlink to the provider's own CDN (e.g. `image.tmdb.org`) — legendarr never
downloads/proxies the image itself, so caching is whatever the browser/provider CDN does on
its own. And metadata for an *existing* item only ever updates on a brand-new-item sync or a
manual "Refetch All" click — there's no `IntervalTrigger`-based job (unlike
`register_sync_job`/`register_scan_job` in `media_library`) that periodically re-pulls
metadata for items already in the library, so upstream changes (a corrected poster, an
updated rating) don't propagate until someone clicks refetch again.

**Resolved**: the "explicitly out of scope" note this memory used to carry (surfacing
`poster_url`/`overview` on `/media/movies`/`/media/series`, tracked at
[[legendarr-media-library-list-ui-not-wired]]) is done — those pages now render a poster-grid
using `show.poster_url` directly (confirmed via Playwright screenshot, 2026-08-27).

**Why:** avoids re-deriving the OMDb-for-IMDb decision, the Radarr-has-no-tvdbId gap, the
three-way merge policy, or the refetch upsert fix from scratch; the caching/periodic-refresh
note saves re-investigating the same question if it comes up again in a roadmap discussion.

**How to apply:** when extending metadata fetch (new fields, new sources, periodic refresh,
or image caching), read `media_metadata/fetch_metadata.py`'s `_merge` function first — it's
the single place the TVDB-wins/TMDb-fills-gaps/IMDb-rating-only policy lives. If asked to add
scheduled refresh or local image caching, treat it as new `feat:`-sized scope (own branch/PR)
since neither exists today.
