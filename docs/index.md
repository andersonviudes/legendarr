# legendarr

<div align="center">

**Self-hosted subtitle translation companion for Radarr and Sonarr**

</div>

---

## What is legendarr?

legendarr is a self-hosted companion for **Radarr** and **Sonarr** that automatically
translates subtitles for your movies and TV shows. It runs as a **single Docker image**
combining a background sync scheduler, a translation pipeline, and a web dashboard — with
one SQLite database and no external services required.

Unlike tools that only handle external `.srt` files, legendarr is built to discover and
translate any subtitle track, including ones embedded inside the video container.

---

## Feature Highlights

=== "Language Profiles"

    - Named profiles pairing source and target languages (e.g. `ja` → `pt-BR, en`)
    - Per-profile translation provider selection
    - Per-profile control over extracting embedded subtitle tracks

=== "Media Library"

    - Periodic sync against the Radarr and Sonarr APIs
    - Runs on a configurable interval via a background scheduler
    - Single SQLite database shared by the sync job and the web UI

=== "Subtitle Discovery"

    - Finds external sibling subtitle files (`.srt`, `.ass`, `.ssa`, `.vtt`)
    - Embedded track probing via the video container, wired in as the feature matures

=== "Translation"

    - Pluggable `TranslationProvider` contract — bring your own backend (DeepL, Google, LibreTranslate, ...)
    - Ships with an `echo` provider for local development and testing

---

## Getting Started

<div class="grid cards" markdown>

- :material-rocket-launch:{ .lg .middle } **[Installation](getting-started/installation.md)**

    ---

    Docker, or run from source with `uv`

- :material-lightning-bolt:{ .lg .middle } **[Quick Start](getting-started/quick-start.md)**

    ---

    Point legendarr at Radarr/Sonarr and see it sync

- :material-cog:{ .lg .middle } **[Configuration](configuration/index.md)**

    ---

    All `LEGENDARR_*` environment variables explained

- :material-layers:{ .lg .middle } **[Architecture](architecture/overview.md)**

    ---

    Screaming Architecture + Vertical Slice internals

</div>

---
