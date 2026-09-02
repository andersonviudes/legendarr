# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and commit messages follow
[Conventional Commits](https://www.conventionalcommits.org/).
## [0.22.4] - 2026-09-02

### ✨ Features

- Add a manual extract action for skipped embedded subtitle tracks (#111)
- Add auto_translate flag to language profiles to gate automatic translation (#113)

### 🐛 Bug Fixes

- Order live tasks by execution order and cap the dashboard widget to 10 (#112)

### 🔧 Miscellaneous

- Record external-subtitle language-guess gotcha
- Record auto_translate flag and open backoff gap

## [0.22.3] - 2026-08-31

### ✨ Features

- Sync Docker Hub repository overview on release (#103)
- Throttle periodic subtitle discovery, acquisition, and translation fan-outs (#107)
- Make each executor queue's worker count configurable (#108)
- Show media titles instead of raw job ids on the Tasks page (#109)

### 🐛 Bug Fixes

- Route uvicorn's startup and access logs through configure_logging (#104)
- Subtitle-pill dropdown fixes (#105)
- Live activity queued-task display and unbounded OCR track duration (#106)
- Don't let Docker Hub description sync block the release
- Stop mistaking a release-tag fragment for a subtitle's language (#110)

### 🔧 Miscellaneous

- Note the real legendarr instance runs on a separate host
- Bump version to v0.22.3 [skip ci]

## [0.22.2] - 2026-08-31

### 📚 Documentation

- Add codecov badge and Installation section to README
- Inline the full Docker Compose example in the README
- Add full-HD feature screenshots (#102)

### 🔧 Miscellaneous

- Grant actions:write so the release workflow can trigger the docs redeploy
- Bump version to v0.22.2 [skip ci]

## [0.22.1] - 2026-08-30

### ✨ Features

- Bootstrap legendarr monorepo with Screaming/VSA architecture
- Add Alembic migrations and persisted config.yaml for database location (#1)
- Add bootstrap module, split backend API from web (#2)
- Redesign web UI with sidebar nav shell, dashboard stats, and htmx polling (#5)
- Share HTTP client conventions across Radarr/Sonarr
- Back Radarr/Sonarr connection and sync settings by config.yaml (#6)
- Formalize APScheduler job registration conventions (#8)
- Formalize shared test fixtures and wire up logging (#9)
- Register, edit, and delete Radarr/Sonarr connections (#10)
- Encrypt API keys at rest instead of storing plaintext (#11)
- Persist synced media and per-connection path mapping (#12)
- Complete LanguageProfile CRUD in backend and web UI (#13)
- Add toast notifications for settings save and connection-test feedback (#14)
- Register subtitle providers with per-provider connection tests (#15)
- Proxy registration for CAPTCHA/Cloudflare bypass (#16)
- Register translation providers with per-provider connection tests (#17)
- Scan video files on disk via jobs, webhooks and history poll (#18)
- Tasks page with runtime-rescheduled job settings (#19)
- Add SubtitleProvider protocol (#20)
- Scan and persist subtitles, list media missing one (#21)
- Translate subtitles for a media file via real providers (#22) (#22)
- Manual library sync trigger (#23)
- Fetch TheTVDB/IMDb metadata on library sync (#24)
- Capture arr metadata and list movies/series in the UI (#25)
- Add movie/series detail pages with translate and scan actions (#26)
- Add library-wide wanted subtitles view (#27)
- Default translation provider, editable from web UI (#28)
- Add in-app directory browser and log viewer (#29)
- Add embedded subtitle track discovery and extraction (#31)
- Embedded-track source fallback (#33)
- Wire up OpenSubtitles search and download (#34)
- Wire up Addic7ed search and download (#35)
- Wire up YIFY Subtitles search and download (#36)
- Wire up Subdl search and download (#37)
- Wire up TVsubtitles search and download (#38)
- Wire up legendas.net search and download (#39)
- Wire up Napiprojekt search and download (#40)
- Wire up Subsource search and download (#41)
- Wire up Anime Tosho search and download (#42)
- Wire up Supersubtitles search and download (#43)
- Wire up AnimeKalesi search and download (#44)
- Wire up GreekSubtitles and BetaSeries search and download (#45)
- Manual per-subtitle timing sync (ROADMAP 0.7.0) (#46)
- Add LLM provider and batch translation requests (ROADMAP 0.8.0) (#47)
- Add pluggable translation provider plugins and custom LLM prompt templates (ROADMAP 0.9.0) (#48)
- Schedule translation and acquisition fan-out jobs (ROADMAP 0.10.0) (#49)
- Cascade Arr webhook imports through discovery, acquisition, and translation (ROADMAP 0.10.0) (#50)
- Manual search, candidate download, and subtitle upload (ROADMAP 0.11.0) (#51)
- Manual translation source pick (ROADMAP 0.11.0) (#52)
- Unify acquisition fallback into periodic translation runs (ROADMAP 0.12.0) (#53)
- Per-attribute score weighting and release-name filters (ROADMAP 0.12.0) (#54)
- Upgrade/replace and blacklist a bad subtitle (ROADMAP 0.12.0) (#55)
- Structured audit trail for acquisition attempts (#56)
- Reject broken subtitles and clean text before translation (ROADMAP 0.13.0) (#57)
- OCR pipeline for PGS embedded subtitle tracks (ROADMAP 0.14.0) (#58) (#58)
- Color subtitle pills by acquisition status (ROADMAP) (#59)
- Speech-to-text fallback via local Whisper (ROADMAP 0.15.0) (#61)
- Session-based login and API key access control (ROADMAP 0.16.0) (#62)
- Document and tag the backend REST API (ROADMAP 0.17.0) (#63)
- Notify Plex/Jellyfin after a subtitle is written (ROADMAP 0.18.0) (#64)
- I18n scaffolding + Settings General locale switcher (#65)
- Dashboard redesign, topbar search/notifications, and UI polish pass (ROADMAP 0.19.0) (#66)
- Authenticate OpenSubtitles with username/password login (#67)
- Make Anime Tosho's AniDB API Key optional (#68)
- TMDb provider, scheduler job history, and settings-page consolidation (#69)
- Local poster cache + periodic refresh/cleanup jobs (#70)
- Translation and acquisition activity view (ROADMAP 0.20.0) (#71)
- History view with translation/acquisition error status (ROADMAP 0.20.0) (#72)
- Render as a table, add the acquisition match score column (#73)
- Push live translation/acquisition progress to the dashboard (ROADMAP 0.20.0) (#74)
- Back off a failing translation/acquisition provider with a circuit breaker (ROADMAP 0.21.0) (#75)
- Reschedule a one-off job that exhausted its in-process retries (ROADMAP 0.21.0) (#76)
- Sweep orphaned temp files left behind by extraction/OCR/transcription/timing-sync (ROADMAP 0.22.0) (#78)
- Export config.yaml + Fernet key to an archive, restore from one (ROADMAP 0.22.0) (#79)
- Add per-subtitle Search and Remove style tags actions (ROADMAP 0.23.0) (#80)
- Search and upload subtitles for episodes Sonarr hasn't downloaded yet (#81)
- Configurable match score per media type (#83)
- Score candidates by content hash and hearing-impaired preference, gate on episode identity (#84)
- Add a timezone setting and localize interface timestamps (#85)
- Score embedded subtitle tracks against the language profile's forced/HI preference (#87)
- Skip extracting embedded subtitle tracks outside the language profile's source languages (#88)
- Confirm navigation away from a form with unsaved changes (#89)
- Stagger periodic jobs with a default jitter (#92)
- Search subtitles action + richer detail-page header (#94)
- Mark score improvements as an upgrade category (#95)
- Apply legendarr branding, real favicon, and simplify README/docs (#96)
- Wire up Dockerfile version labels, workspace versioning, and a release workflow (#100)
- Build+smoke-test+publish the Docker image and generate release notes (#101)

### 🐛 Bug Fixes

- Wire up pyright and resolve type errors across backend and web (#32)
- Register legendarr's real OpenSubtitles API consumer key
- Include the response body in provider request-failure errors
- Explain Anime Tosho's API Key is an AniDB client name
- Align sidebar submenu toggle padding with nav links
- Show the profile's target language as a gray pill for episodes with no file yet
- Only open the per-file subtitles dialog from the title or embedded pill
- Style the subtitle-dialog title trigger as a plain link
- Match the title trigger's font size to the rest of the row
- Restore the per-subtitle quick actions menu on external pills
- Add a manual-search button to the Actions column
- Search the profiles target languages instead of picking one manually
- Hide unwanted horizontal scrollbar in subtitle search results list
- Keep target-language casing so a pending subtitle's pill actually shows (#82)
- Simplify running-tasks badge to a solid count circle (#93)
- Use white screen artwork for the topbar brand mark
- Use the white-screen mark in the README header too
- Fix topbar brand link vertical alignment
- Shrink poster grid card width to 8-10rem
- Shrink poster grid card width to 7-8.75rem
- Trim top gap above media-detail toolbar by half
- Standardize toolbar top spacing across list and detail pages
- Align media-detail backdrop with the page padding
- Restore divider line above the media-detail backdrop
- Widen the gap between the toolbar divider and the backdrop
- Skip a target language matching the source's own language (#98)

### 📚 Documentation

- Add MkDocs documentation site
- Rewrite roadmap into dependency-ordered versions and move to ROADMAP.md
- Convert roadmap items to checkboxes (#4)
- Add Clean Code/SOLID rule, slim down AGENTS.md, track rules/skills in git
- Allow fix commits to push straight to main
- Reorder roadmap so Radarr/Sonarr + language profile setup precedes the library scan
- Record form-control specificity and multiselect height gotchas
- Pull minimal subtitle-provider acquisition into 0.3.0
- Order acquisition before discovery in 0.3.0
- Name the 8-provider target pool for subtitle acquisition
- Split 0.3.0 translation items into interface vs real implementation
- Move remaining subtitle providers into 0.6.0
- Log PR #46 and #47 roadmap-basis history (0.7.0 timing sync, 0.8.0 LLM/batching)
- Discard 0.10.0 opt-out bullet, add manual translation-source pick to 0.11.0
- Backlog periodic metadata refresh + local poster caching
- Note default cadence for the periodic metadata refresh backlog item
- Record Anime Tosho AniDB-key research and the main-revert convention note
- Record dialog centering, ffmpeg temp-suffix, and Playwright dialog-handler gotchas
- Reconcile ROADMAP 0.20.0 checkboxes with what actually shipped
- Record the per-subtitle Search/Remove-style-tags dropdown addition
- Note the scratch fix-branch and main-divergence recovery pattern

### ♻️ Refactor

- Share a MediaLibraryClient protocol between Radarr/Sonarr
- Organize shared_kernel into subject subfolders
- Reorganize slices by business domain (#7)
- Rename modules/ workspace directory to src/ (#30)
- Align backend/web with SOLID + Screaming Architecture + VSA (#77)

### ⏪ Reverts

- Move periodic-metadata-refresh backlog note to feat/tmdb-metadata-provider

### 🔧 Miscellaneous

- Translate UI and README to English, drop tool name comparison
- Build and test only, drop image publish
- Update team memory for bootstrap module split (#3)
- Update team memory with PR #12 media-library sync notes
- Update team memory with SQLite FK migration and plan-branch-task learnings
- Add docker-compose stack for testing against real Sonarr
- Note modules/ to src/ rename in team architecture memory
- Require pyright type-checking alongside lint/test
- Note 0.6.0 embedded-track source fallback completion
- Add search-strategy navigation rule
- Add legendarr i18n conventions team memory
- Capture QA and retrospective notes in team memory
- Add commit-message conventions, refresh search-strategy stats
- Refresh search-strategy stats
- Enforce conventional-commit format on PR titles (#91)
- Record .app-brand-mark shared-class gotcha
- Record reflex-PR clarification, playwright resize recurrence, and brand-asset check (#97)
- Disable Plex/Jellyfin by default in the dev compose stack (#99)
- Bump version to v0.22.1 [skip ci]


