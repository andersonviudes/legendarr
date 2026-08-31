<h1 align="center">
  <img src="branding/legendarr-mark-512.png" alt="legendarr" width="32" height="32" style="vertical-align: middle;">
  legendarr
</h1>

<p align="center">
  <a href="https://github.com/andersonviudes/legendarr/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/andersonviudes/legendarr/ci.yml?branch=main&label=CI" alt="CI">
  </a>
  <a href="https://github.com/andersonviudes/legendarr/releases/latest">
    <img src="https://img.shields.io/github/v/release/andersonviudes/legendarr?label=release" alt="release">
  </a>
  <a href="https://hub.docker.com/r/andersonviudes/legendarr">
    <img src="https://img.shields.io/docker/pulls/andersonviudes/legendarr" alt="docker pulls">
  </a>
  <a href="https://github.com/andersonviudes/legendarr">
    <img src="https://img.shields.io/github/languages/code-size/andersonviudes/legendarr" alt="code size">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/andersonviudes/legendarr" alt="License">
  </a>
</p>

## About

Self-hosted companion for **Radarr** and **Sonarr** that automatically translates
subtitles, with flexible language profiles and the ability to translate any subtitle,
including tracks embedded inside the video.

Full documentation: **[andersonviudes.github.io/legendarr](https://andersonviudes.github.io/legendarr/)**.

## Installation

Full walkthrough (path mappings, `PUID`/`PGID`, building from source): [Installation docs](https://andersonviudes.github.io/legendarr/getting-started/installation/).

### Docker

```bash
docker run -p 8000:8000 -v ./data:/config -v /path/to/your/library:/media \
  -e LEGENDARR_RADARR_URL=http://radarr:7878 \
  -e LEGENDARR_RADARR_API_KEY=your-radarr-api-key \
  -e LEGENDARR_SONARR_URL=http://sonarr:8989 \
  -e LEGENDARR_SONARR_API_KEY=your-sonarr-api-key \
  -e PUID=1000 -e PGID=1000 \
  andersonviudes/legendarr:latest
```

### Docker Compose

Save as `docker-compose.yml` (also available as [`docker-compose.example.yml`](docker-compose.example.yml)
in the repo root), adjust the paths/env vars, then `docker compose up -d`:

```yaml
services:
  legendarr:
    image: andersonviudes/legendarr:latest
    environment:
      - LEGENDARR_RADARR_URL=http://radarr:7878
      - LEGENDARR_RADARR_API_KEY=your-radarr-api-key
      - LEGENDARR_SONARR_URL=http://sonarr:8989
      - LEGENDARR_SONARR_API_KEY=your-sonarr-api-key
      - PUID=1000
      - PGID=1000
    volumes:
      - ./data:/config
      - /path/to/your/library:/media
    ports:
      - "8000:8000"
    restart: unless-stopped
```

```bash
docker compose up -d
```

The dashboard is then available at `http://localhost:8000`.

## Features

- [Language Profiles](https://andersonviudes.github.io/legendarr/features/language-profiles/) —
  named source/target language and translation-preference sets, e.g. "translate embedded
  Japanese to `pt-BR` and `en` for anime".
- [Media Library Sync](https://andersonviudes.github.io/legendarr/features/media-library/) —
  keeps track of every movie and series in your Radarr/Sonarr library on a background schedule.
- [Subtitle Discovery](https://andersonviudes.github.io/legendarr/features/subtitle-discovery/) —
  finds every subtitle a video already has, external or embedded.
- [Subtitle Acquisition](https://andersonviudes.github.io/legendarr/features/subtitle-acquisition/) —
  downloads subtitles from your configured provider sites when none exist yet.
- [Subtitle Translation](https://andersonviudes.github.io/legendarr/features/subtitle-translation/) —
  pluggable translation backends behind a single provider interface.
- [Subtitle Timing Sync](https://andersonviudes.github.io/legendarr/features/subtitle-timing-sync/) —
  re-aligns a subtitle's cues against the video with `ffsubsync`.
- [Authentication](https://andersonviudes.github.io/legendarr/features/authentication/) —
  optional single-admin login for self-hosted deployments.
- [External API](https://andersonviudes.github.io/legendarr/features/external-api/) —
  the same REST API the dashboard uses, documented for scripts and other tools.
- [Media-Server Integration](https://andersonviudes.github.io/legendarr/features/media-server-integration/) —
  notifies Plex/Jellyfin automatically after a subtitle is written.
- [Internationalization](https://andersonviudes.github.io/legendarr/features/internationalization/) —
  pick your own UI language from Settings.
- [Backup & Restore](https://andersonviudes.github.io/legendarr/features/backup-restore/) —
  snapshot legendarr's configuration before an upgrade or a move to a new host.

## License

Licensed under the [GNU General Public License v3.0](LICENSE) or later.
