---
name: legendarr-prod-deployment-topology
description: user's real legendarr instance runs on a separate host/NAS (docker container "legendarr"), not this dev checkout — confirmed 2026-08-31
type: project
---

The user's actual legendarr instance (the one processing their real Sonarr/Radarr library)
runs as a Docker container named `legendarr` on a separate host from this dev checkout —
sibling containers on that host include `watchtower`, `gitea`, `sabnzbd`, `portainer_agent`
(a typical self-hosted media/dev stack, likely a home server/NAS). This sandbox has no
docker/SSH access to that host: `docker ps` here is empty and the dev checkout's own
`data/legendarr.db` is a separate, mostly-idle local DB — don't confuse the two when a user
reports something about "the app" without specifying which instance.

**Why this matters:** debugging a live-behavior report (queued tasks, slow scans, etc.)
requires either the user pasting `docker logs`/`docker stats`/`htop` output from that host,
or SSH access — there is no way to inspect it directly from this environment. See
[[legendarr-docker-compose-dev-stack-staleness]] for the separate dev-stack-staleness gotcha
(unrelated host, don't conflate).

**Confirmed 2026-08-31:** a report of "many `subtitle_scan` tasks stuck in Queued" turned out
to be the just-merged throttle feature (PR #107, `scheduling/queues.py`'s `JobQueue.SCAN` with
`max_workers=2`) working as designed — `htop` on that host showed 2 live `ffmpeg` processes
actively extracting embedded subtitles (Rings of Power S01 import cascaded a burst of
per-episode `subtitle_scan` jobs onto the 2-worker `scan` queue), not a deadlock. Diagnosed by
asking the user for `docker stats`/`htop` screenshots rather than guessing.
