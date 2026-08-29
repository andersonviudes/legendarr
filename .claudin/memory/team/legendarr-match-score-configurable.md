---
name: legendarr-match-score-configurable
description: LanguageProfile now has movie_match_score/series_match_score (0-100); match_score.py's TITLE_WEIGHT/ATTRIBUTE_WEIGHTS stay hardcoded
type: project
---

PR #83 (2026-08-29) made the subtitle acquisition match cutoff user-configurable, split by
media type. Before this, `subtitle_acquisition/candidate_evaluation/match_score.py`'s
`DEFAULT_CUTOFF = 0.4` was a hardcoded module constant, applied identically to movies and
series with no UI to change it (the only knobs already tunable per profile were
`release_name_must_contain`/`must_not_contain`, unrelated to scoring).

**What changed:** `LanguageProfile` (`language_profiles/models.py`) gained
`movie_match_score`/`series_match_score`, both `int` 0-100 (not a `0.0-1.0` float — the model/
schema/form/DB all speak whole percent, and the single division back to a fraction happens only
at the one point `pick_best_match` needs it, a new private helper
`_match_cutoff_for_media_file()` in `subtitle_acquisition/acquire_media_file_subtitle.py`). Split
by media type — not a single field — because a profile is type-agnostic and the same one can be
assigned to both a `Movie` and a `Series` (`resolve_effective_profile.py` has no type
distinction); `MediaFile.movie_id`/`series_id` (exactly one set) picks which field applies at
acquisition time. Migration `37624b260bfb`, default `40` server-side to match the old constant
exactly, so no existing profile's behavior changes on upgrade.

**What deliberately did NOT change:** `TITLE_WEIGHT`/`ATTRIBUTE_WEIGHTS` in the same file are
still hardcoded — their own comment ("Not user-configurable: the roadmap bullet only asks for
the weighting mechanism, not per-weight tuning") was never about the cutoff and is still
accurate. Only the accept/reject threshold is configurable now, not how a candidate's score is
computed. `upgrade_subtitle_for_media_file` (the separate upgrade/replace path) never used
`DEFAULT_CUTOFF` to begin with (it compares a candidate's score against the *current* subtitle's
own recorded score, not a fixed floor) — untouched, out of scope.

UI side: see [[legendarr-ui-design-system]]'s 2026-08-29 "match-score sliders" entry for the
range-input component and the accent-color rendering gotcha it hit.

**How to apply:** any future feature that wants to read "how strict is acquisition for this
profile" should call the same `_match_cutoff_for_media_file(profile, media_file)` helper (or read
the two raw fields directly, dividing by 100) rather than re-deriving a fraction by hand — and if
a use case ever needs the cutoff without a concrete `MediaFile` (e.g. a dry-run/preview), extend
that helper's signature rather than inlining the movie/series branch a second time.
