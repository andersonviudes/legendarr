---
name: legendarr-free-translation-providers
description: PR #143 — google works with no API key (Bazarr's keyless endpoint, one request per line), new gemini kind; why the Cloud path was kept and why deep-translator was rejected
type: project
---

Landed 2026-09-11 on `feat/free-translation-providers` (PR #143). Until then every
translation backend needed a paid account (`deepl`, `google`, `llm`) or a self-hosted engine
(`libretranslate`), so a fresh install could not translate anything until the user signed up
somewhere. Modeled on what Bazarr actually ships — see
[[legendarr-bazarr-translation-architecture]] for how theirs is built.

**What changed:**

- `google` stayed **one kind with an optional API Key**, rather than being replaced or split
  into a second `google_free` kind. Blank key → `GoogleFreeTranslationProvider` (the public
  `translate_a/single` endpoint), stored key → `GoogleCloudTranslationProvider` (the paid v2
  API, unchanged). `provider_chain._PROVIDER_CLASSES["google"]` is the
  `build_google_provider` *function*, not a class — the `_ProviderFactory` alias already
  allowed that. Both backends keep `name = "google"` deliberately, so circuit-breaker state,
  `TranslationAttempt.provider` and System > Providers don't split in two when a user adds
  or removes a key.
- `models._NO_CREDENTIAL_KINDS = {"google"}` is a new third branch in `has_credentials`.
  Before this, a kind in neither `_API_KEY_KINDS` nor `_ENDPOINT_KINDS` fell through to the
  *plugin* lookup and returned True by accident; the explicit branch is what
  `test_credential_kinds_match_what_connection_tests_actually_requires` now pins.
- New `gemini` kind = `GeminiTranslationProvider(LLMTranslationProvider)` overriding only
  `name`, `client_label` and the two new `default_endpoint`/`default_model` class attributes.
  It speaks Google AI Studio's OpenAI-compatible surface
  (`https://generativelanguage.googleapis.com/v1beta/openai`, `gemini-2.0-flash`), which
  accepts `response_format: {"type": "json_object"}` — so no new protocol code at all.
  `endpoint` is deliberately absent from its `credential_fields`.

**Two decisions worth not relitigating:**

1. **No `deep-translator` dependency.** Bazarr uses it, but vendors a *patched* copy purely
   to set a browser user-agent, and it would bypass `ProviderHttpClient`'s shared
   timeout/retry/error conventions (see [[legendarr-http-client-conventions]]). The endpoint
   is a single GET; calling it directly costs less than the dependency.
2. **The keyless endpoint really does need one request per subtitle line.** It takes one
   string per call. Batching by joining lines with a separator is what caused Bazarr's
   line-scrambling bug (#2166), so it wasn't attempted. The fan-out is
   `GOOGLE_FREE_MAX_WORKERS = 6` `daemon=True` threads draining a `queue.Queue`, joined on
   one shared deadline — *not* a `ThreadPoolExecutor`, for the reason
   `subtitle_acquisition/provider_search.py:215` documents (see
   [[legendarr-opensubtitles-hash-hang-fix]]). Six, not Bazarr's ten, because
   `limit_concurrency` already permits `PROVIDER_MAX_CONCURRENCY = 3` media files at once,
   so it's really up to 18 requests in flight.

**Failure policy:** a line the endpoint still refuses after retrying keeps its **source
text**; past `MAX_FAILED_LINE_RATIO = 0.1` of the subtitle the call raises instead, so the
circuit breaker records it and `_translate_with_fallback` tries the next provider rather than
writing a mostly untranslated file. This is the one place legendarr deliberately diverges
from Bazarr, which never fails a translation over individual lines.

**Verified live**, not just in tests: multi-sentence lines rejoin correctly (the response's
first element holds one entry per sentence Google split the input into), blank lines are
passed through without a request, and `pt-BR` survives as a target — do **not** run a
translation target through `normalize_language_code`, which would collapse it to `pt`.

Still unverified in a real app run at the time of the merge: the end-to-end UI flow
(enable → Test connection → translate a media file) and Gemini against a real AI Studio key.
