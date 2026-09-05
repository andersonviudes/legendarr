---
name: legendarr-match-score-normalization-fix
description: match_score.py attribute comparison bug (spelling/bracket-group variants) fixed 2026-09-05; audio/Proper noise in title similarity deliberately left unfixed
type: project
---

Fixed 2026-09-05 (commit `08edb90`, `fix(subtitle-acquisition)`): manual-search scores
looked wrong (a lower-resolution candidate could outrank a same-quality one) because
`candidate_evaluation/match_score.py`'s `==` comparison treated spelling variants as
real mismatches — `"WEBDL"` vs `"WEB-DL"`, `"x264"` vs `"h264"`/`"h.264"` — and
`release_attributes._GROUP_PATTERN` couldn't detect a release group trailing a
bracket-wrapped tag (`[h265]-GROUP`, Radarr/Sonarr's own renaming shape), so the group
bonus silently dropped out too. With none of those bonuses landing, ranking degenerated
into noisy `SequenceMatcher` text similarity. Fix: separator-stripping +
codec-family (`x264`≈`h264`, `x265`/`hevc`≈`h265`) normalization now happens only inside
`match_score.py`'s comparison step, not in `ReleaseAttributes` itself — the literal
detected value stays intact for `describe_search_resource.py`'s display-only "Resource"
preview, which reuses `extract_release_attributes` too. See [[legendarr-match-score-configurable]].

**Deliberately deferred** (explicit user choice during planning, not an oversight):
residual "Proper"/"Repack" and audio-codec/channel tags (`EAC3`, `DDP`, `Atmos`, `5.1`)
still aren't in `release_attributes._VOCABULARY_PATTERNS`, so they survive
`strip_known_attribute_tokens` and keep adding noise to the title-similarity score
whenever none of the 5 scored attributes discriminates between candidates. Revisit only
if it resurfaces as a real ranking complaint — would need a new "stripping-only"
vocabulary (mirroring `describe_search_resource.py`'s own separate audio/HDR/DV
patterns) rather than extending the scored `ATTRIBUTE_WEIGHTS`.
