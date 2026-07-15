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
