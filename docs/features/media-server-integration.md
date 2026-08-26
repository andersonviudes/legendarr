# Media-Server Integration

*ROADMAP.md 0.18.0 — a freshly acquired or translated subtitle shows up in Plex/Jellyfin
without a user manually triggering a library rescan.*

## Registration

Settings → Media servers (`/settings/media-servers/`) has a fixed catalog of exactly two
rows — Plex and Jellyfin — the same fixed-catalog shape as Metadata source. For each,
set:

- **Base URL** — the server's own address, e.g. `http://plex.local:32400`.
- **Token** — a Plex token or a Jellyfin API key.

A server only turns on once both are set and "Test connection" has succeeded at least
once, same gating as every other provider page.

## What triggers a refresh

Only the automatic pipeline: a download or an upgrade in subtitle acquisition, and a
successful subtitle translation. Manually uploading a subtitle or running the manual
timing-sync pass does not notify a media server in this milestone.

## Targeted refresh, per server

- **Plex** — finds the library section whose configured root folder covers the video's
  path, then does a targeted, forced-metadata refresh of just that folder
  (`GET /library/sections/{id}/refresh?path=...&force=1`). Falls back to a full refresh
  of the same section if the targeted call fails. A path that matches no known section
  is skipped — there's nothing to refresh Plex doesn't already know about.
- **Jellyfin** — reports the video's own path (not the subtitle's) to
  `POST /Library/Media/Updated`; Jellyfin resolves the item server-side, no section/item
  id needed. Falls back to a full `POST /Library/Refresh` if that call fails.

Both are best-effort: a media server being unreachable or rejecting the credential is
logged and never blocks the acquisition/translation run that triggered it.

## Known limitations

- **Shared filesystem path assumed.** legendarr reports the same local path it resolved
  for itself — this only works when legendarr and the media server see the same
  filesystem (a shared Docker volume mount, this project's typical deployment). There's
  no separate remote/local path-mapping for media servers yet, same accepted-gap
  treatment as the Windows path-mapping note elsewhere in `ROADMAP.md`.
- **No debounce.** A bulk "translate all"/"acquire all" run fires one refresh call per
  file as it completes — no coalescing window yet.
- **Jellyfin subtitle pickup is best-effort.** Even reporting the video's path, whether
  Jellyfin's file-system watcher reliably notices a subtitle-only change alongside it is
  not guaranteed by Jellyfin itself; the full-refresh fallback only triggers on an
  outright failed call, not on a "succeeded but didn't actually pick it up" case.
