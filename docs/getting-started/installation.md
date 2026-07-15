# Installation

## Docker

```bash
docker run -p 8000:8000 -v ./data:/config \
  -e LEGENDARR_RADARR_URL=http://radarr:7878 \
  -e LEGENDARR_RADARR_API_KEY=your-radarr-api-key \
  -e LEGENDARR_SONARR_URL=http://sonarr:8989 \
  -e LEGENDARR_SONARR_API_KEY=your-sonarr-api-key \
  ghcr.io/andersonviudes/legendarr:latest
```

The dashboard is then available at `http://localhost:8000`.

!!! note
    legendarr's CI currently only builds and tests the image; it does not publish it to a
    registry yet. Until an image is published, build it locally instead — see below.

## Build the image locally

```bash
git clone https://github.com/andersonviudes/legendarr.git
cd legendarr
make docker-build
docker run -p 8000:8000 -v ./data:/config legendarr:local
```

## From source

Prerequisites: [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
git clone https://github.com/andersonviudes/legendarr.git
cd legendarr
make install   # uv sync --all-packages
make run       # starts the web app (and the backend scheduler) at http://localhost:8000
```
