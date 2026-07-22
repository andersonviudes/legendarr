---
name: legendarr OpenSubtitles search options kept despite YAGNI flag
description: use_hash/include_ai_translated/include_machine_translated on SubtitleProviderConfig were flagged as YAGNI (nothing reads them yet) but the user explicitly chose to keep them — don't re-flag or revert without asking again
type: project
---

`SubtitleProviderConfig.use_hash`, `.include_ai_translated`, and `.include_machine_translated`
(`modules/backend/src/legendarr_backend/subtitle_acquisition/models.py`) are saved from the
OpenSubtitles edit form but not read by anything yet — subtitle search/matching isn't built. A
standards-audit agent flagged this as a YAGNI violation per `.claudin/rules/clean-code-solid.md`
(added ahead of the feature that would use them, outside the original subtitle_acquisition plan's
agreed scope).

**Why:** the user explicitly asked for these fields to be added and persisted earlier in the same
session (2026-07-22), then later replied "aplica todos" to a ranked list of audit findings that
included this YAGNI flag as a discretionary item. Asked directly via AskUserQuestion whether
"aplica todos" meant reverting this too, the user chose "Não reverter," confirming the fields
should stay even though nothing consumes them yet.

**How to apply:** if a future audit or review re-flags these fields (or the same pattern —
persisting data ahead of the feature that will consume it) as YAGNI/scope creep, don't revert or
remove them without asking again; this was already raised and the user decided to keep them.
