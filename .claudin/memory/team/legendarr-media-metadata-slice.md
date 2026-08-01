---
name: legendarr media metadata slice
description: TheTVDB/IMDb metadata provider registration + fetch-on-sync — new media_metadata slice, PR #24 on feat/metadata-source
type: project
---

Built 2026-08-01 on `feat/metadata-source` (PR #24): a Settings → "Metadata source" page
to register TheTVDB and IMDb as metadata providers, plus real fetch-on-sync — unlike
`subtitle_acquisition`'s deliberate registration-only-first increment (see
`legendarr-roadmap-basis`), the user explicitly asked for full integration in one pass,
confirmed via AskUserQuestion before planning.

**Shape**: new backend slice `media_metadata/` mirrors `subtitle_acquisition`'s fixed-catalog
pattern (`MetadataProviderConfig`, one row per kind, seeded at startup) but seeds
**`enabled=True`** by default (subtitle providers seed `False`) — an explicit, confirmed user
ask ("deixa marcado"). What actually gates a fetch attempt is `has_credentials`
(`api_key` set), not the `enabled` flag. New `MediaMetadata` table (own row per `Movie`/
`Series`, mirrors `MediaFile`'s movie_id/series_id shape) stores fetched
`overview`/`poster_url`/`year`/`imdb_rating`.

**"IMDb" is backed by OMDb** (omdbapi.com) — IMDb itself has no free public API. The `kind`
is still stored/labeled `"imdb"` everywhere; only the HTTP client underneath
(`OmdbMetadataProvider`) is OMDb's. TheTVDB uses the v4 API, API-key-only login (no `pin`).

**Fetch keys**: `Movie`/`Series` gained plain `tvdb_id`/`imdb_id` columns, populated from
Radarr/Sonarr's own sync response (`MediaItem` in `arr_clients/base.py` gained the same two
fields). Confirmed by reading Radarr/Sonarr's API shape: **Radarr movies never report a
`tvdbId`** (Radarr's own canonical id system is TMDb) — only `imdbId`. So the TVDB client
falls back to a title search for movies; series always fetch by id on both sources.

**Hook point**: `media_library/sync_media_library.py`, right after each connection's
`session.commit()` — fetches metadata only for rows the sync run just created (the
`row is None` branch), never re-fetched for existing rows. Runs synchronously inline (no
new job-queue plumbing), each connection's metadata step wrapped in its own try/except so a
metadata-source outage never fails the sync itself.

**Merge policy** (confirmed via AskUserQuestion) when both sources are enabled: TheTVDB is
authoritative for `overview`/`poster_url`/`year` (same source Sonarr itself uses); IMDb/OMDb
only ever contributes `imdb_rating`, the one field TVDB doesn't have.

**Explicitly out of scope**: surfacing the fetched metadata on `/media/movies`/
`/media/series` — see [[legendarr-media-library-list-ui-not-wired]], still stub pages. This
only persists the data for a future task.

**Why:** avoids re-deriving the OMDb-for-IMDb decision, the Radarr-has-no-tvdbId gap, or the
merge policy from scratch; also documents that this feature deliberately diverged from the
registration-first increment shape `subtitle_acquisition`/`legendarr-roadmap-basis` used
twice before — that precedent is not a hard rule, it's overridden when the user asks for
full scope up front and confirms it.

**How to apply:** when extending metadata fetch (new fields, new sources, or actually
displaying it in the UI), read `media_metadata/fetch_metadata.py`'s `_merge` function first
— it's the single place the TVDB-wins/IMDb-rating-only policy lives.
