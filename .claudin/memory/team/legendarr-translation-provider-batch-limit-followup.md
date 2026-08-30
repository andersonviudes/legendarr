---
name: legendarr-translation-provider-batch-limit-followup
description: Google Translate hit a real 128-text-segment-per-request API limit on real subtitles; fixed via chunking. DeepL/LibreTranslate/LLM still send the whole subtitle in one call, unchecked for similar limits.
type: project
---

On 2026-08-30, live-testing the newly configured Google Translate provider against a real
subtitle (Ahsoka S01E04, 234 lines) failed with `400: "Too many text segments"` — Google
Cloud Translation API v2 rejects a request with more than 128 `q` text segments per call.
The job "succeeded" (200 OK end-to-end, HTTP-wise) but silently produced zero translated
languages, recorded only in the `translationfailure` table, not surfaced as a UI error.
Fixed by chunking `texts` into batches of ≤128 in `GoogleTranslationProvider.translate_batch`
(`google.py`), confirmed working after a dev container rebuild — two chunked API calls,
full 234-line `.pt-br.srt` written to disk.

**Why:** every `TranslationProvider.translate_batch()` implementation
(deepl.py/google.py/libretranslate.py/llm.py) sends the *entire* subtitle's line list in
one API call — nothing in `translate_subtitle.py` chunks beforehand. Google's 128-segment
cap was the one instance found so far, purely because it was the provider actually
exercised end-to-end this session.

**How to apply:** DeepL, LibreTranslate, and the generic LLM provider are NOT yet verified
against a similarly-capped real request (segment count, character count, or token count) —
treat them as unverified until one is actually driven against a full-length subtitle. A
translation job that "succeeds" with an empty/partial `translated_languages` list means
check `translationfailure` in `dev/legendarr-config/legendarr.db` (see
[[legendarr-dev-db-direct-inspection]]), not just the toast/HTTP status. See also
[[legendarr-dev-deepl-key-broken]] for how this was discovered (testing Google as the
DeepL replacement).
