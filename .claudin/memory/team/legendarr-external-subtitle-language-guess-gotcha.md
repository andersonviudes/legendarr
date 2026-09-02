---
name: legendarr-external-subtitle-language-guess-gotcha
description: _guess_language_from_filename can mistake a release-tag fragment for a subtitle's language when the file keeps the raw scene release name; fixed 2026-08-31
type: project
---

External subtitle discovery (`scan_video_subtitles.py::_guess_language_from_filename`) used to
take the subtitle file's last dot-separated stem segment as its language code, with zero
validation that the segment actually looked like a language code. That convention holds for
legendarr's own downloads (`<video-stem>.<language>.srt`, see `acquire_media_file_subtitle.py`)
and for well-behaved external files, but a subtitle a release group ships alongside the video
under its own raw scene release name (no clean `.<language>.` suffix — just a stray dot
somewhere inside the release tags, e.g. `...HDR10].[H265]-GROUP.srt`) made it grab a fragment
like `1][dv hdr10][h265]` and store/display that as the subtitle's "language" pill. Reported by
the user via a screenshot of the series detail page on 2026-08-31 ("algumas legendas não está
descobrindo direito o nome").

**Why:** `_guess_language_from_filename`'s output flows straight into `Subtitle.language`
(`scan_media_subtitles.py`) with no validation layer anywhere downstream, so any garbage it
produced was persisted and rendered verbatim in `subtitle_pill_list()` (macros.html).

**How to apply:** fixed by validating the candidate segment against
`^[a-z]{2,3}(-[a-z]{2,4})?$` before accepting it, falling back to `"und"` otherwise (same
fallback already used for a stem with no dot at all) — see the docstring on
`_guess_language_from_filename` for the full rationale, and the regression test in
`test_scan_video_subtitles.py`. If a user reports a subtitle language badge showing
filename/release-tag garbage instead of a real language code, that function is the single place
external-subtitle language gets derived; check there first.

Shipped as PR #110 (`fix/subtitle-discovery-language-guess` branch) rather than pushed straight
to `main` — the user explicitly asked to open a PR for this fix, overriding the usual
`fix:`-goes-straight-to-`main` convention ([[legendarr-branch-convention]]) for this one case.
