---
name: legendarr-echo-translation-provider-not-wired
description: the "echo" dev translation provider (src/backend/.../subtitle_translation/providers/echo.py) exists but isn't reachable — dead code, pre-existing, not on any roadmap item
type: project
---

`EchoTranslationProvider` (`src/backend/src/legendarr_backend/subtitle_translation/providers/echo.py`)
is a real, credential-free provider meant for exercising the translation pipeline without
real API keys — but it is **not** in `provider_chain.py`'s `_PROVIDER_CLASSES` dict, and
there's no `TranslationProviderConfig` row or UI affordance to enable it (the Translation
Providers settings page only lists DeepL/Google/LibreTranslate/LLM). The settings page's
own copy claims "`echo` ... is always available too, for development" — that's stale/
inaccurate; a manual translate with no other provider configured is skipped with
`no_provider_configured`, echo is never reached.

**Why it matters:** discovered live-testing ROADMAP 0.20.0's "Live progress" feature in
the `docker-compose.dev.yml` stack — planned to use `echo` for a credential-free live
translate, found it unreachable, worked around it by enabling DeepL with a fake API key
instead (still exercises the real code path via a real, failing HTTPS call).

**How to apply:** if a future task wants a working no-credential dev provider (e.g. for
`make run`/dev-stack smoke tests), either wire `echo` into `_PROVIDER_CLASSES` +
`BUILTIN_PROVIDER_LABELS`/`BUILTIN_PROVIDER_CREDENTIAL_FIELDS` (`provider_catalog.py`) so
it can be enabled from the UI, or fix the settings page copy to stop claiming it's
available. Neither was done as part of the live-progress work — out of scope, flagged
here instead. Not on `ROADMAP.md` as its own item.
