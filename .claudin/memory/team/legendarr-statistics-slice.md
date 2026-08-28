---
name: legendarr statistics slice
description: Statistics view (ROADMAP 0.20.0) — new TranslationAttempt audit trail + statistics/ slice in backend and web, aggregating translation/acquisition activity
type: project
---

Built 2026-08-28 on `feat/statistics`, closing ROADMAP.md 0.20.0's "Statistics view" item.

**Gap found during planning**: `subtitle_acquisition` already had an audit trail
(`AcquisitionAttempt`, one row per attempt with provider/timestamp/outcome) that
`subtitle_discovery`/`subtitle_acquisition` writes to on every attempt, but
`subtitle_translation` had nothing equivalent — `translate_media_file.py` picked a provider
and translated but never persisted which provider won or when. Added `TranslationAttempt`
(`subtitle_translation/models.py`), mirroring `AcquisitionAttempt`'s shape, plus migration
`3e3a7c3f553b_add_translation_attempt_table`. `translate_media_file.py` now writes one row
per successful translation via a new `subtitle_translation/translation_history.py`
(`record_translation_attempt`), same pattern as acquisition's own history recorder.

**Backend shape**: new `statistics/` slice (`compute_statistics.py`, `schemas.py`,
`router.py`), one route `GET /statistics`. Response has two top-level sections
(`translated`/`acquired`), each with: a total count, a 30-day daily trend **zero-filled**
for days with no activity (not just the days that have rows — the web trend chart needs a
fixed-width 30-bar series), and a breakdown by language profile and by provider. Both
sections query their own table (`TranslationAttempt` / `AcquisitionAttempt`) independently —
no shared query helper, since the two tables' columns aren't identical.

**Web shape**: mirrored `statistics/` slice (router, service, `templates/statistics.html`),
new sidebar nav entry "Statistics" (between History and Settings) with a new
`chart-column.svg` icon obtained via the lucide fallback in
[[legendarr-lucide-icon-source]]. Trend bars and breakdown bars are **pure CSS** (a
`<div>` per day with an inline `height`/`width` percentage) — no new JS charting
dependency. Empty breakdown ("No activity recorded yet.") is a real state to design for:
this repo's dev stack had zero `TranslationAttempt` rows at verification time, so the
"Translated" section's by-profile/by-provider lists render that message while "Acquired"
(2 real rows) renders populated bars — both confirmed live via Playwright against the
docker-compose dev stack (needed a `build` + `up -d` first, see
[[legendarr-docker-compose-dev-stack-staleness]]).

**Gotcha for the next new top-level router**: `src/backend/tests/test_api.py`'s
`test_every_route_is_tagged_by_its_domain` walks a `_TAG_BY_PREFIX` dict to assert every
route's OpenAPI `tags` matches its URL prefix — forgetting to add the new prefix there
doesn't fail quietly, it raises `StopIteration` from the `next(...)` call (no matching
prefix), not a normal assertion failure. Added `"/statistics": "Statistics"` there.

**Why:** avoids re-discovering that translation had no audit trail (the acquisition one is
easy to assume covers both), and the zero-filled-trend / test_api.py prefix-map gotchas if a
future statistics section (e.g. per-item detail) gets added.

**How to apply:** any future "activity over time" feature should reuse
`compute_statistics.py`'s zero-fill-then-bucket pattern rather than re-deriving it, and
register its own audit-trail writes the same way `translation_history.py` does rather than
inferring history from side effects.
