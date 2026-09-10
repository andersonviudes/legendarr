---
name: legendarr-language-coverage-normalization-fix
description: PR #127 — existing-subtitle coverage checks compared raw .lower() instead of normalize_language_code, so a region-tagged subtitle (pt-BR) didn't satisfy a profile's generic target language (pt)
type: project
---

Fixed 2026-09-09 (branch `fix/language-code-region-normalization`, PR #127, commit `cf693de`).
`get_media_detail.py`'s language-coverage table, `list_missing_subtitles.py`, and the embedded-
track extraction's source-language gate (`scan_media_subtitles.py`) all compared a profile's
target/source language against existing `Subtitle.language` values with a raw `.lower()`
instead of the existing `language_codes.normalize_language_code` helper. Since
`normalize_language_code` collapses a region-tagged code to its primary ISO 639-1 subtag
("pt-BR" -> "pt", `subtitle_discovery/language_codes.py:79`), a profile targeting generic "pt"
with an already-present "pt-BR" subtitle on disk showed that language as missing on the media
detail page, and the embedded-track extraction gate treated the source language as uncovered
even though a matching subtitle already existed. Fix applies `normalize_language_code`
consistently at all three call sites; the repeated normalized-set comprehension was factored
into a new `normalized_language_set(codes)` helper in the same module.

**Distinct from a still-open, different call site:**
[[legendarr-auto-translate-flag-and-open-backoff-gap]] flags a *separate*, still-unconfirmed
`normalize_language_code` concern in `LanguageProfile.source_languages` handling
(`subtitle_acquisition/acquire_media_file_subtitle.py`, `upgrade_media_file_subtitle.py`) —
collapsing a profile's explicit region-specific source language (e.g. `es-419`) before matching
against provider results. This PR did not touch that path — don't assume it's fixed too.

**How to apply:** any new comparison against a `Subtitle.language`/profile-language value
should go through `normalize_language_code`/`normalized_language_set`, never a raw string
comparison or `.lower()`.
