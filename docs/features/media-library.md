# Media Library Sync

legendarr syncs its media library from your Radarr and Sonarr instances on a background
schedule, so it always knows which movies and series you have and where their files live.

## How it works

A `BackgroundScheduler` job runs `sync_media_library()` every
[`LEGENDARR_SYNC_INTERVAL_MINUTES`](../configuration/environment-variables.md) minutes,
using a `RadarrClient` and/or `SonarrClient` — whichever providers have a URL configured.
The scheduler is started once and shared by both the CLI entrypoint and the web app's
`lifespan`, so there's a single sync job regardless of how legendarr is run.

## Viewing the library

The synced library is browsable at `/media/movies` and `/media/series` in the web
dashboard, each showing the count of items currently synced.
