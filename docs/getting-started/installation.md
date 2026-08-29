# Installation

## Docker

```bash
docker run -p 8000:8000 -v ./data:/config -v /path/to/your/library:/media \
  -e LEGENDARR_RADARR_URL=http://radarr:7878 \
  -e LEGENDARR_RADARR_API_KEY=your-radarr-api-key \
  -e LEGENDARR_SONARR_URL=http://sonarr:8989 \
  -e LEGENDARR_SONARR_API_KEY=your-sonarr-api-key \
  -e PUID=1000 -e PGID=1000 \
  ghcr.io/andersonviudes/legendarr:latest
```

The dashboard is then available at `http://localhost:8000`.

legendarr drops from root to a `PUID`/`PGID`-controlled user before writing anything, the
same convention Radarr/Sonarr/linuxserver.io images use — set them to match the user that
owns your media library (`id -u`/`id -g` on the host) so files legendarr writes stay owned
by you instead of container root. Both default to `1000`, the first non-system user on
most Linux hosts.

Mount your media library into the container so legendarr can see the actual files —
`/media` above is just a convention, any mount path works. If Radarr/Sonarr report the
same files under a different path than legendarr sees them (typical when they run in
separate containers), set a path mapping on each connection in **Settings → Servers**.

!!! note
    legendarr's CI currently only builds and tests the image; it does not publish it to a
    registry yet. Until an image is published, build it locally instead — see below.

## Build the image locally

```bash
git clone https://github.com/andersonviudes/legendarr.git
cd legendarr
make docker-build
docker run -p 8000:8000 -v ./data:/config -v /path/to/your/library:/media legendarr:local
```

## From source

Prerequisites: [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
git clone https://github.com/andersonviudes/legendarr.git
cd legendarr
make install   # uv sync --all-packages
make run       # starts the web app (and the backend scheduler) at http://localhost:8000
```
