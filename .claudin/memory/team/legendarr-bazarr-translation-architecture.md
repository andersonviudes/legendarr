---
name: legendarr-bazarr-translation-architecture
description: How Bazarr's translate-subtitle feature is actually built (3 pluggable backends, one request per line, retry policy) — the reference legendarr's free providers were modeled on
type: reference
---

Researched 2026-09-11 from Bazarr master. Useful whenever legendarr's translation side is
compared against "what Bazarr does" — several widely repeated claims about it are out of
date.

**It is not hardcoded to Google any more.** `bazarr/subtitles/translate.py` no longer exists;
it's a package at `bazarr/subtitles/tools/translate/`, with `main.py` picking a backend via
`TranslatorFactory.create_translator(...)`. Three services under `services/`:

| Backend | Config (`bazarr/app/config.py`, `translator` section) | Shape |
| --- | --- | --- |
| `google_translate` (**default**) | no key | `deep_translator.GoogleTranslator(source='auto', ...)`, the public keyless endpoint |
| `gemini` | `gemini_keys` (a **list**), `gemini_model` (default `gemini-2.0-flash`), `gemini_batch_size` (default 300) | batches 300 subtitles per request |
| `lingarr` | `lingarr_url`, `lingarr_token` | delegates to a Lingarr instance |

**Google backend specifics** — the parts worth copying:

- **One HTTP request per subtitle line**, fanned out over
  `ThreadPoolExecutor(max_workers=10)`. There is no character-based chunking. This is
  deliberate: it sidesteps the ~5000-char cap *and* an earlier bug where batching scrambled
  line order (issue #2166).
- `@retry(exceptions=(TooManyRequests, RequestError), tries=6, delay=1, backoff=2, jitter=(0, 1))`.
- `TranslationNotFound` is logged at debug and the **original text is kept** — a line never
  fails the job.
- Bazarr vendors a *patched* `deep_translator` solely to set a custom user-agent.

**Gemini backend specifics:** detects HTTP 429 / `RESOURCE_EXHAUSTED`, honors `Retry-After`
(default 60s), rotates through the key pool with a 60s per-key cooldown, 3 attempts per batch.

**Other facts that correct common assumptions:**

- **DeepL was never integrated** — still an open feature request. legendarr has it, Bazarr
  doesn't.
- **Whisper is a subtitle *provider*, not a translate backend.** In
  `custom_libs/subliminal_patch/providers/whisperai.py` it sets `sub.task = 'translate'` only
  when the detected language differs, and hard-rejects non-English targets. So Whisper does
  audio → English subtitle; the translate action does existing subtitle → any language. The
  only "AI" in the translate action is Gemini.
- Subtitle parsing is the `srt` library (`srt.parse`/`compose`/`sort_and_reindex`), the same
  one legendarr uses.

See [[legendarr-free-translation-providers]] for which of these legendarr adopted, which it
deliberately did not, and why.
