---
name: legendarr roadmap competitive basis
description: Why legendarr's roadmap (ROADMAP.md) is phased the way it is — confirmed feature gaps found by reading Bazarr and Lingarr source directly
type: project
---

legendarr's roadmap (`ROADMAP.md` at the repo root — moved there from `docs/roadmap.md` on
2026-07-15 to match standard open-source convention, alongside `README.md`; no longer part of
the MkDocs site nav), versioned 0.1.0 → 1.0.0, was built 2026-07-15 from a
direct source-code comparison against two sibling projects checked out locally purely for
reference: `/home/viudes/projects/bazarr` (Python/subliminal-based subtitle manager for
Radarr/Sonarr) and `/home/viudes/projects/lingarr` (C#/.NET translation-only companion).
Neither is a dependency of legendarr; they're separate git repos on the same machine used as
competitive research. Confirmed via reading their source, not just their docs:

- **Bazarr**: strong provider-download system (60+ providers under
  `subliminal_patch/providers/`, scoring/cutoff, per-provider throttling, upgrade/replace
  logic) but translation is manual and one-existing-subtitle-to-one-target-language only
  (`bazarr/subtitles/tools/translate/`); it detects embedded subtitle tracks via ffprobe
  only for A/V sync purposes and never translates from them.
- **Lingarr**: strong multi-engine translation (OpenAI/Anthropic/Gemini/DeepL/LibreTranslate/
  GTranslate wrappers, via a keyed-DI provider-factory + plugin pattern in
  `Lingarr.Server/Services/Translation/`) and Hangfire job scheduling with content-hash
  dedup, but works exclusively off pre-existing sidecar subtitle files on disk — zero
  embedded-track detection/extraction, and zero external subtitle-provider downloading.

Neither tool combines embedded-track extraction + external-provider downloading +
multi-engine translation in one pipeline — that combination is legendarr's actual
differentiator, and is what the roadmap phases are built around (embedded tracks, then
provider downloads, then a unified external→embedded→provider acquisition strategy before
translation).

Also confirmed by reading legendarr's own code in this session: the implementation is
thinner than the pre-existing docs implied — `sync_media_library()` discarded synced media
instead of persisting it, `LanguageProfile` had no `update`/`delete`, and no subtitle
file (`.srt`) parser/writer existed anywhere. That's why roadmap `0.1.0` is pure
architecture/layout/infrastructure (no business rules at all, per explicit user request) and
`0.2.0` is the "walking skeleton" milestone, rather than jumping straight to
embedded/provider features.

**Why:** avoids re-litigating "why is the roadmap ordered this way" or re-researching these
two external tools from scratch in a future session — the findings above are the answer.

**How to apply:** when discussing roadmap scope/ordering or positioning legendarr against
alternatives, reuse these confirmed findings instead of re-exploring the sibling repos. Per
the existing architecture memory, keep competitor names out of committed repo content
(`ROADMAP.md`, README, UI strings) — comparisons by name belong in chat/PR discussion only,
never in files that ship with the repo.

**2026-07-16 reorder:** milestones `0.2.0`–`0.21.0` were renumbered up by one (now
`0.2.0`–`0.22.0`; `1.0.0` unchanged) to insert a new `0.2.0` — "Connect Radarr & Sonarr,
configure languages, and sync your library" — ahead of what was `0.2.0` ("Translate one
subtitle end to end"). Reasoning: registering a working Radarr/Sonarr connection and creating
a real (non-CLI/seed) `LanguageProfile` — languages, translation provider, embedded-track
preference, forced/HI — are themselves a coherent, demoable "setup" use case, and previously
both were deferred two milestones past the point the roadmap already assumed a synced library
and a translated subtitle existed. The new `0.2.0` absorbs: persisting synced media (old
`0.2.0`), `LanguageProfile` backend CRUD + its web UI (old `0.2.0`'s CLI/seed workaround is
dropped entirely, superseded by old `0.3.0`'s real profile UI moving forward), and the
Radarr/Sonarr connection-details/validate/path-mapping bullets split out of old `0.4.0`'s
Settings milestone (sync interval and default translation provider stayed behind at the new
`0.5.0`). Subtitle-acquisition/download-provider registration (old `0.10.0`/`0.11.0`, now
`0.11.0`/`0.12.0`) was explicitly *not* pulled forward — no `subtitle_acquisition` slice or
download-provider code exists yet, unlike `TranslationProvider`
(`subtitle_translation/providers/base.py`), which already had a working `echo` implementation
and a field on `LanguageProfile` to select it.

**2026-07-22 — `subtitle_acquisition` lands, scope narrowed to registration only:** a session
refining 0.3.0's acquisition item first explored collapsing all of 0.11.0/0.12.0 (all 8
providers + full matching/weighting/blacklist/audit-trail) forward into 0.3.0, then backed off
after hitting a real gap — there's no `Episode` model, so acquisition can't cleanly target a
`Series` yet, only `Movie`. Final scope actually built: `subtitle_acquisition/models.py`'s
`SubtitleProviderConfig` table (fixed catalog, one row per kind, seeded at startup via
`ensure_subtitle_providers_seeded`), a settings page at `/settings/subtitle-providers/`
(enable/disable, credentials, "Test connection"), and per-kind connection-test functions in
`subtitle_acquisition/connection_tests.py`. The `SubtitleProvider` protocol, real HTTP clients,
search, match scoring, and download are still not built — `ROADMAP.md`'s 0.3.0 now has two
acquisition bullets, one checked (registration) and one not (protocol + first real provider).

**Provider pool changed**: BSPlayer was dropped and replaced with **legendas.net**
(Brazilian PT-BR subtitle site). Reason, confirmed by reading Bazarr's own
`custom_libs/subliminal_patch/providers/bsplayer.py:88-90`: Bazarr disabled BSPlayer outright
("prevent usage of this provider and return no subtitles") because it was too unreliable —
same reasoning applied here rather than shipping a provider already known to be dead weight.
legendas.net's shape was confirmed via Bazarr's `legendasnet.py:82-133` (official API,
username/password → `access_token`).

**Auth shapes are not uniform across the 8 providers** — confirmed by reading each Bazarr
provider file directly (`opensubtitlescom.py`, `addic7ed.py`, `subdl.py`, `subsource.py`,
`yifysubtitles.py`, `napiprojekt.py`, `tvsubtitles.py`, `legendasnet.py`) plus live web research
on each one's current API docs: OpenSubtitles/Subdl/Subsource use an API key, Addic7ed/
legendas.net use username+password (Addic7ed has no official API and can be CAPTCHA-gated —
Bazarr's own login flow needs a third-party CAPTCHA solver it doesn't always have), and YIFY
Subtitles/TVsubtitles/Napiprojekt need no credential at all (their "test connection" is a bare
reachability ping, not real validation). This is why `SubtitleProviderConfig` has three nullable
columns (`api_key`, `username`, `password`) instead of one.
