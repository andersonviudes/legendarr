# Quick Start

1. **Set your Radarr/Sonarr connection details.** Copy `.env.example` to `.env` and fill in
   the URLs and API keys:

    ```bash
    cp .env.example .env
    ```

    ```env
    LEGENDARR_RADARR_URL=http://localhost:7878
    LEGENDARR_RADARR_API_KEY=
    LEGENDARR_SONARR_URL=http://localhost:8989
    LEGENDARR_SONARR_API_KEY=
    LEGENDARR_SYNC_INTERVAL_MINUTES=15
    ```

2. **Start legendarr** (see [Installation](installation.md) for Docker or source options).

3. **Open the dashboard** at `http://localhost:8000`. It links to:
    - `/media/` — the media library synced from Radarr and Sonarr
    - `/language-profiles/` — configured language profiles

4. **Create a language profile** to tell legendarr which languages to translate to for
   which content, and whether to extract embedded subtitle tracks. See
   [Language Profiles](../features/language-profiles.md).

5. legendarr's background scheduler syncs the media library from Radarr and Sonarr every
   `LEGENDARR_SYNC_INTERVAL_MINUTES` minutes automatically — no manual trigger needed.
