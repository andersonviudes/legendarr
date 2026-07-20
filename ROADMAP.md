# Roadmap

legendarr's core bet: translate **any** subtitle available for a piece of media — an external
sibling file, a track embedded in the video container, or one fetched from a subtitle
provider — instead of requiring a single pre-existing subtitle per language. Acquisition
(finding or downloading a subtitle) and translation are two halves of one pipeline, not two
unrelated features.

This is ordered purely by dependency and value: each `0.x.0` below
is the earliest point a coherent, demoable use case exists — not a grab-bag of tasks, and not
constrained by anything already shipped. Every item is tagged with the subject it belongs to
(mirroring the project's slice architecture — `media_library`, `subtitle_discovery`,
`subtitle_translation`, `language_profiles`, plus the acquisition, settings, and operations
areas still to come), so items for the same subject can still be traced across versions.
`1.0.0` is reached once every use case below works together and the image is published. Items
are checked off (`[x]`) as they land on `main`.

## 0.1.0 — Architecture, layout, and infrastructure

*Use case: none yet — this version has nothing a user can click through end to end. It's the
scaffolding every later version builds business rules on top of, instead of bolting them onto
ad-hoc plumbing decided along the way.*

- [x] **Database infrastructure** — Migration tooling (e.g. Alembic) around the existing
  SQLModel/SQLite setup, replacing implicit `create_all()` schema creation, so the schema
  changes later versions need (forced/HI flags, acquisition tables, settings) are tracked
  instead of improvised.
- [x] **Dashboard & UI** — Base UI layout for `legendarr_web`: navigation shell
  (header/sidebar) and a shared page template/design system, plus the convention for how
  HTMX partial responses relate to full-page templates — established before any feature page
  exists.
- [x] **Settings** — Config foundation: formalize the split between bootstrap config (env vars,
  `config/settings.py`) and runtime-editable settings persisted to the existing
  `config.yaml` file (extending `AppConfigFile` in `config/config_file.py`, already
  written to `settings.data_dir` — `/config` in the Docker image) instead of the database, so
  the 0.2.0 and 0.5.0 Settings pages read and rewrite one file instead of retrofitting onto
  whatever `config_file.py` looks like by then.
- [x] **Automation & scheduling** — Formalize the shared `APScheduler` instance/job-registration
  convention (already used by the sync job), including named queues and a
  retry/concurrency-dedup policy per job type, so later scheduled work (0.10.0 onward)
  registers into one consistent model instead of each job wiring its own.
- [x] **Media providers** — Shared HTTP client conventions (timeout/retry/error handling) for
  `RadarrClient`/`SonarrClient`-style integrations, so later subtitle-provider and
  translation-API clients follow one shape instead of each being bespoke.
- [x] Shared testing conventions (fixtures, test database setup) across
  `modules/<module>/tests/<slice>/`, and structured logging conventions in
  `logging/setup.py` for how slices report errors up to the orchestrators built
  starting 0.3.0.

## 0.2.0 — Connect Radarr & Sonarr, configure languages, and sync your library

*Use case: a user registers their Radarr/Sonarr connections and creates language profiles
(source/target languages, translation provider, embedded-track preference, forced/HI
attributes) entirely from the web UI, triggers a sync, and sees their movies/series list
populate in the dashboard — no shell access, CLI, or env-var editing needed for day-to-day
setup.*

- [x] **Settings** — Connection details (Radarr/Sonarr URL + API key) editable from the web UI
  and persisted, on top of the config foundation from 0.1.0 (env vars remain the way to
  bootstrap the very first run, per `AGENTS.md`).
- [x] **Settings** — Secrets (API keys) encrypted at rest instead of stored as plaintext.
- [x] **Settings** — Validate settings on save: creating/editing a Radarr/Sonarr connection
  probes the server (`/system/status`) and rejects unreachable servers, wrong app types, and
  bad API keys with an actionable message instead of persisting them. A "test connection"
  button in the form runs the same probe without saving.
- [x] **Settings** — Path mapping: each connection carries an optional
  remote→local path prefix pair, reconciling filesystem differences when legendarr and
  Radarr/Sonarr run in separate containers with different mounts. Paths are stored as
  reported and translated at read time (`resolve_local_path`), so editing a mapping
  never requires a re-sync. Known gap (deferred): Windows-style paths (`C:\Movies\...`)
  don't match prefix boundaries yet — `resolve_local_path` only handles `/` separators.
- [x] **Media providers** — Sync persists media (`Movie`/`Series` + the path as reported
  by the server) per connection, keyed by `(arr_service_id, arr_id)` so multiple Radarr/
  Sonarr instances never collide; rows a server stops reporting are deleted only within
  that connection's scope.
- [ ] **Language profiles** — Complete `LanguageProfile` CRUD in the backend (`update`/`delete`
  are missing today, not just their UI).
- [ ] **Language profiles** — Create/edit/delete language profiles from the web UI. Forced and
  hearing-impaired (HI) as first-class attributes on a profile, so it can require or exclude
  them per language rather than treating every subtitle as equivalent. Per-item override: a
  specific movie or series can be pinned to a profile other than its default.

## 0.3.0 — Translate one already-downloaded subtitle, end to end, in the real UI

*Use case: a movie has an external `.srt` sitting next to it; a user opens legendarr's web
UI, sees it, and gets a translated file back — fully automated, no manual database editing,
using the Radarr/Sonarr connection, synced library, and language profile already set up in
0.2.0.*

- [ ] **Subtitle discovery** — Subtitle file round-trip: parse an `.srt` into translatable lines
  and write translated lines back out to a new `.srt`, preserving timing. Nothing downstream
  can produce a real file without this.
- [ ] **Subtitle translation** — An orchestrator that ties a `LanguageProfile` to a media item:
  run external-only discovery, translate with the configured provider, write the result. One
  real `TranslationProvider` (e.g. LibreTranslate or DeepL) alongside `echo`.
- [ ] Manual trigger only (CLI or a "translate now" action in the UI) — no scheduling yet.

## 0.4.0 — See what's missing, from the dashboard

*Use case: a user sees, from the dashboard, what subtitles are still missing for their media
given their language profiles.*

- [ ] **Dashboard & UI** — Per-media view of discovered subtitles and translation status. Wanted
  view: library-wide list of media still missing a subtitle for one of its profile's target
  languages — the same signal later automation/acquisition will act on, made visible first.

## 0.5.0 — Runtime settings

*Use case: a user sets the sync interval, picks default translation providers, and can browse
library folders or recent logs, all from a Settings page, no shell access needed.*

- [ ] **Settings** — Sync interval and default translation provider/language editable from the
  web UI and persisted, on top of the config foundation from 0.1.0. Secrets (translation
  provider credentials) encrypted at rest instead of stored as plaintext.
- [ ] **Settings** — In-app directory browser (to pick library paths without typing them blind)
  and a log viewer, so day-to-day operation doesn't require shelling into the container.

## 0.6.0 — Embedded text subtitle tracks

*Use case: a show only has a Japanese subtitle track muxed into the `.mkv` — no external
file — and legendarr extracts and translates it anyway.*

- [ ] **Subtitle discovery** — Probe video containers (via `ffprobe`, already installed in the
  Docker image) for embedded subtitle streams. Extract text-based embedded tracks (SubRip,
  ASS/SSA, `mov_text`) into the same discovery pipeline external files already use. Read the
  forced/HI flags a container track already carries in its metadata, feeding the profile
  attributes from 0.2.0.
- [ ] Orchestrator falls back to an embedded track when no external file matches the source
  language.

## 0.7.0 — Subtitle timing sync

*Use case: a translated or downloaded subtitle drifts out of sync with the audio; legendarr
shifts its timing to match before handing it back to the user.*

- [ ] **Subtitle discovery** — Timing-correction pass (in the style of `ffsubsync`) that aligns a
  subtitle's cues against the video's audio track, using the `ffmpeg` toolchain already
  wired up at 0.6.0. Runs automatically after translation, replacing the drifted file.

## 0.8.0 — Multiple providers, multiple target languages

*Use case: one profile translates a source subtitle into `pt-BR` and `en` in a single pass,
using whichever engine (DeepL, Google Translate, or an LLM) the profile is configured for.*

- [ ] **Subtitle translation** — More `TranslationProvider` backends behind the existing
  protocol: DeepL, Google Translate, and an LLM-backed option. Translate into multiple
  target languages from one profile in a single operation, instead of one target language
  per action. Batch multiple subtitle lines per request where a provider supports it.

## 0.9.0 — Pluggable translation engines

*Use case: a user wants a translation engine legendarr doesn't ship built in — a private LLM
endpoint, a niche API — and adds it without waiting for a legendarr release, or tunes the
prompt an LLM-backed provider uses for their content.*

- [ ] **Subtitle translation** — Dynamic plugin loading for `TranslationProvider` implementations
  (load a third-party package at runtime, version-gated), so new engines don't require
  recompiling or redeploying legendarr itself.
- [ ] **Subtitle translation** — Customizable request templates per LLM-backed provider
  (user-editable prompt/payload), instead of one fixed prompt baked into the provider.

## 0.10.0 — Unattended scheduling

*Use case: legendarr runs with no one clicking anything — new media synced from Radarr/Sonarr
gets discovered and translated on a schedule, or immediately when Radarr/Sonarr says a file
just landed.*

- [ ] **Automation & scheduling** — Wire the orchestrator into a scheduled job, registered
  through the scheduler convention from 0.1.0. Content hash per subtitle so unchanged files
  are skipped on re-runs instead of re-translated every cycle.
- [ ] **Media providers** — Webhook endpoint Radarr/Sonarr can call on "file imported",
  triggering discovery and translation for that item immediately instead of waiting for the
  next scheduled pass.
- [ ] **Language profiles** — Per-profile or per-media opt-out of automated translation.

## 0.11.0 — Download subtitles from external providers

*Use case: no usable external or embedded subtitle exists in the source language, so
legendarr fetches one from a subtitle-provider site before translating — or a user picks a
specific result themselves.*

- [ ] **Subtitle acquisition** — New `subtitle_acquisition` slice with a provider-plugin
  protocol, mirroring `TranslationProvider`'s shape and the shared HTTP client conventions
  from 0.1.0, so subtitle-provider sites can be added without hardcoding one integration.
  First one or two providers wired in, with a basic match-score/cutoff model per language
  profile. Orchestrator falls back to acquisition when local discovery (external + embedded)
  comes up empty.
- [ ] Manual search and manual upload: let a user browse provider search results and pick one
  themselves, or upload their own subtitle file for a specific media item, bypassing the
  automatic match.

## 0.12.0 — Unified acquisition strategy

*Use case: legendarr always uses the best available source before translating, weighs a
downloaded subtitle's release attributes rather than a single cutoff score to avoid a bad
match, can be pointed at several provider sites at once, doesn't keep re-fetching a subtitle
it already knows is wrong, and can explain why it picked what it picked.*

- [ ] **Subtitle acquisition** — One ordered strategy per profile: external file → embedded
  track → provider download. Expand the provider list; add must-contain/must-not-contain
  release-name filters, plus per-attribute score weighting (release group, resolution,
  codec, source, edition) instead of a single flat cutoff. Upgrade/replace logic: re-fetch
  when a better-scoring subtitle becomes available later. Blacklist: mark a specific
  downloaded (or translated) subtitle as bad so it's never reused or re-fetched for that
  media item again.
- [ ] **Subtitle acquisition** — Structured audit trail: record which release attributes matched
  or didn't for each acquisition attempt, and link an upgraded subtitle back to the one it
  replaced.

## 0.13.0 — Subtitle quality control

*Use case: a subtitle that's technically "found" but garbage — wrong length, OCR artifacts,
stray formatting — gets caught or cleaned up instead of silently becoming someone's
translation source.*

- [ ] **Subtitle acquisition** — Quality-gate validation before accepting an acquired subtitle:
  file size and cue-count/duration bounds sanity-checked, obviously broken results rejected.
- [ ] **Subtitle discovery** — Text cleanup pass (regex-based fixes for common punctuation/OCR
  artifacts, stray color/formatting tags) applied to a subtitle's text before it's handed to
  translation.

## 0.14.0 — Image-based embedded tracks (OCR)

*Use case: a Blu-ray rip's embedded PGS/VobSub track — bitmap images, not text — gets OCR'd
into text and translated like any other track.*

- [ ] **Subtitle discovery** — OCR pipeline (e.g. Tesseract) for bitmap-based embedded subtitle
  formats.

## 0.15.0 — Speech-to-text fallback

*Use case: a piece of media has no subtitle anywhere — no external file, no embedded track,
no provider match — so legendarr transcribes the audio itself to produce a source subtitle
to translate from.*

- [ ] **Subtitle acquisition** — Local speech-to-text transcription (e.g. Whisper) as the
  last-resort acquisition source, used only when every other tier — external (0.3.0),
  embedded (0.6.0), and provider download (0.11.0–0.12.0) — comes up empty.

## 0.16.0 — Authentication & secrets

*Use case: legendarr requires logging in before anyone can see or change anything, and issues
an API key for scripts/tools instead of everyone sharing the dashboard session.*

- [ ] **Settings** — Session-based login gating the web UI, plus a generated API key for
  non-interactive access, both configurable from Settings — auth can be required or left off
  for trusted networks.

## 0.17.0 — External API

*Use case: a user scripts against legendarr or wires it into another tool via a documented
REST API, gated by the API key from 0.16.0, instead of only ever driving it through the
dashboard.*

- [ ] Documented REST API surface covering media, language profiles, subtitles, and system
  status — the same domain operations the dashboard already uses, exposed for external
  tools.

## 0.18.0 — Media-server integration

*Use case: a freshly translated subtitle shows up in Plex/Jellyfin immediately, without a
user manually triggering a library rescan.*

- [ ] **Media providers** — Targeted Plex/Jellyfin library-item refresh after a subtitle is
  written, falling back to a full library scan if a targeted refresh isn't available.

## 0.19.0 — UI polish and internationalization

*Use case: the dashboard looks and feels finished, and a user can pick their own UI language
from the Settings page instead of only ever seeing English.*

- [ ] **Dashboard & UI** — Visual refinement pass over the base layout from 0.1.0, once every
  page from 0.2.0 onward exists to refine against (spacing, empty states, responsiveness) —
  not a from-scratch redesign.
- [ ] **Dashboard & UI** — i18n scaffolding for `legendarr_web` (extractable strings, a locale
  switcher) and a first batch of translated locales. Repo content itself (code, comments,
  docs) stays English per `AGENTS.md` — this is about the UI a *user* sees, not the
  codebase.

## 0.20.0 — Dashboard observability

*Use case: a user can watch a translation happen live, see historical trends, and knows when
a new legendarr version is available — all without leaving the dashboard.*

- [ ] **Dashboard & UI** — Statistics view: subtitles translated/acquired over time, per profile
  and provider.
- [ ] **Dashboard & UI** — Live progress: push per-line/per-job translation and acquisition
  progress to the dashboard as it happens, instead of only a final status.
- [ ] **Operations** — Translation/acquisition history and error status surfaced in the
  dashboard.
- [ ] **Operations** — Announcements and an update check (is a newer legendarr version
  available), surfaced in the dashboard.

## 0.21.0 — Resilience

*Use case: a flaky translation or acquisition provider backs off instead of taking every
other job down with it, and a scheduled job failure gets retried instead of silently
vanishing.*

- [ ] **Operations** — Per-provider throttling/circuit breaker so one failing translation or
  acquisition provider backs off instead of failing every job.
- [ ] **Operations** — Retry handling around scheduled jobs, building on the per-job
  retry/concurrency policy established at 0.1.0.

## 0.22.0 — Maintenance & backup

*Use case: legendarr can be trusted to run unattended for weeks — disk usage doesn't creep up
from leftover temp files, and a bad upgrade or a corrupted database isn't a disaster.*

- [ ] **Operations** — Cleanup job: remove temporary files left behind by embedded-track
  extraction and stale acquisition/translation requests.
- [ ] **Operations** — Backup/restore: export the database (language profiles, settings,
  media/translation history) and configuration to a single archive from the Settings page,
  with basic retention, and restore from one — before upgrades and for moving to a new host.

## 1.0.0 — Official release

- [ ] Publish the Docker image to a container registry (CI currently only builds it to
  validate, without pushing it anywhere), gated behind authentication with an external API
  available. Every use case above works together: external, embedded, provider-downloaded,
  and transcribed subtitles, synced timing, quality-checked content, pluggable
  multi-provider/multi-language translation, unattended scheduling, media-server
  integration, and a configurable, backed-up, multi-language, observable UI.

Have a feature request? Open an issue on
[GitHub](https://github.com/andersonviudes/legendarr/issues).
