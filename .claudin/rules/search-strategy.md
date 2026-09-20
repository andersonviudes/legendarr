---
paths:
  - "**/*.py"
  - "**/*.html"
---
<!-- claudin:module-map -->
# Module Map

Generated from the tracked file list, and meant to be edited by hand. The
structure and the `(N)` counts are kept current automatically; the `←`
annotations are not — replace each `TODO` with what the directory is for,
and that text will survive every later refresh.

```
└── src/ (571)                              ← uv workspace root: one lockfile, three packages
    ├── backend/ (401)                      ← domain logic: Arr clients, subtitle pipeline, internal API
    │   ├── db/ (41)                        ← SQLModel tables + shared database setup
    │   │   └── migrations/ (41)            ← Alembic revisions (`make db-revision`)
    │   ├── src/ (216)                      ← installable `legendarr_backend` package source
    │   │   └── legendarr_backend/ (216)    ← vertical slices per capability + shared top-level modules
    │   └── tests/ (145)                    ← mirrors each backend slice, same folder names
    │       ├── arr_services/ (3)           ← Radarr/Sonarr service CRUD + connection tests
    │       ├── authentication/ (4)         ← login/session guard tests
    │       ├── backup/ (3)                 ← config backup/restore tests
    │       ├── language_profiles/ (4)      ← profile CRUD + match-score tests
    │       ├── maintenance/ (3)            ← scheduled maintenance/backup job tests
    │       ├── media_library/ (11)         ← sync/scan/poster-cache test coverage
    │       ├── media_metadata/ (8)         ← metadata providers + poster caching tests
    │       ├── media_servers/ (8)          ← webhook notify (Plex/Jellyfin) provider tests
    │       ├── scheduling/ (7)             ← shared scheduler/retry/job-budget tests
    │       ├── subtitle_acquisition/ (44)  ← provider clients + download tests (largest slice)
    │       ├── subtitle_discovery/ (12)    ← embedded/external subtitle discovery tests
    │       ├── subtitle_translation/ (11)  ← translation backends + per-line fan-out tests
    │       └── system/ (8)                 ← tasks/logs/settings API tests
    ├── bootstrap/ (5)                      ← single-process entrypoint (`make run` / Docker CMD)
    │   └── src/ (3)                        ← installable `legendarr_bootstrap` package source
    │       └── legendarr_bootstrap/ (3)    ← app.py mounts backend API + web UI, owns scheduler lifespan
    └── web/ (158)                          ← FastAPI+Jinja2/HTMX UI; talks to backend over loopback HTTP only
        ├── src/ (126)                      ← installable `legendarr_web` package source
        │   └── legendarr_web/ (126)        ← UI slices mirroring backend capabilities + templates/static
        └── tests/ (39)                     ← mirrors each web slice, same folder names
            ├── media_library/ (15)         ← library table/detail/poller UI tests
            └── system/ (5)                 ← system pages + web app shell tests
```
