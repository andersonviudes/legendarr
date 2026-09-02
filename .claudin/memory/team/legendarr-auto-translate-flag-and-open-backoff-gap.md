---
name: legendarr-auto-translate-flag-and-open-backoff-gap
description: LanguageProfile.auto_translate gates automatic translation (fan-out + acquisition cascade); a separate "no backoff on repeated acquisition/translation failure" issue is still open
type: project
---

Added `LanguageProfile.auto_translate` (default `True`, migration
`e72442d07845_add_auto_translate_to_language_profile.py`) after a user report: disabling
translation for a movie had no effect — it kept showing up as "Failed" in History every
cycle. Root cause: there was no per-profile way to opt a profile out of *automatic*
translation at all; the periodic translation fan-out (`subtitle_translation.jobs.
enqueue_full_translation_scan`, via `needs_translation`) and the translation cascade that
follows a successful automatic acquisition (`subtitle_acquisition.jobs.enqueue_acquisition`'s
`cascade` block) both unconditionally attempted every media file with a missing target
subtitle. Both are now gated on the resolved profile's `auto_translate` — off skips the
enqueue entirely (never becomes a task, never shows in History). The manual "Translate"
button (`media_library.router`'s `trigger_file_translation`/
`trigger_subtitle_source_translation`) intentionally bypasses this gate — an explicit
one-off request always works regardless of the flag.

**Separate, still-open issue surfaced by the same investigation:** when acquisition or
translation genuinely finds nothing (below match-score cutoff, no provider has the
release yet), there is no backoff/give-up — it's retried every fan-out cycle (default
60 min) forever, with no cap. Confirmed live via a user's History page: dozens of
`Dragon Ball Super` episodes with repeated "Failed" acquisition attempts in `en` (their
default profile's only source language is `en`/`fr`, no Korean/Japanese-drama-friendly
source configured) and no automatic escalation or "give up" state. Not fixed by the
`auto_translate` flag — that only stops the *translation* step; a source-language
acquisition with no available subtitle will still retry indefinitely. Worth a future
ROADMAP item (e.g., a failure counter + escalating backoff per media file/language) if
this comes up again.

**Why:** avoids re-investigating the same History screenshots/queue-depth report if a
similar "it never stops trying" complaint comes in again — see the two theories that were
ruled out first: hyphenated source-language codes (`pt-BR`, `es-419`, `zh-Hant` are valid
`SUPPORTED_LANGUAGES` entries but get collapsed by `language_codes.normalize_language_code`
before comparison — a real bug in itself, but not what this user hit, since their
`source_languages` was `en,fr`, unhyphenated) and the single-worker `ACQUIRE_BULK`/
`TRANSLATE_BULK` queues (real bottleneck, but orthogonal to "why does the same item keep
failing").

**How to apply:** if a future report says "X keeps retrying/failing forever" first check
(1) is the effective profile's `auto_translate` on when it shouldn't be, (2) does the
profile's `source_languages` actually match a language any configured provider can supply
for that content (the Dragon Ball Super case), before assuming a code bug.
