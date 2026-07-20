---
name: legendarr language profile provider removal
description: translation_provider was removed from LanguageProfile (form + model + migration) — provider selection is a separate, not-yet-designed feature/use case
type: project
---

The `translation_provider` field (free-text, e.g. `echo`) on `LanguageProfile` was removed
2026-07-20: the backend model/schema, the "Add/Edit Language Profile" web form and profile
card, both backend and web tests, and `docs/features/{language-profiles,subtitle-translation}.md`
were all updated, plus a new Alembic migration
(`6de10a94ec84_drop_translation_provider_from_language_.py`) drops the column.

**Why:** the user decided translation provider selection is a different use case than language
profiles and will be configured elsewhere (not yet designed) rather than per-profile.

**How to apply:** don't reintroduce a `translation_provider` field on `LanguageProfile` going
forward. When the "pick a translation provider" feature resurfaces, expect it to be a separate
slice/settings surface, not a language-profile form field. It was never wired to
`subtitle_translation`'s provider selection (nothing dispatched on it), so nothing there needed
a replacement source when the field was dropped.
