# Subtitle Discovery

Before a subtitle can be translated, legendarr needs to find it. `scan_video_subtitles()`
discovers every subtitle available for a video file and reports where each one came from.

## External subtitles

Sibling files next to the video (matching its filename stem) are always considered.
Recognized extensions: `.srt`, `.ass`, `.ssa`, `.vtt`. The language of an external subtitle
is guessed from its filename suffix (e.g. `movie.pt-BR.srt` → `pt-BR`); files without a
language suffix are reported as `und` (undetermined).

## Embedded subtitles

Subtitle tracks embedded inside the video container (`SubtitleOrigin.EMBEDDED`) are probed
via `ffprobe` and, for text-based codecs (SubRip, ASS/SSA, `mov_text`), extracted to a `.srt`
sibling next to the video (`{stem}.embedded.{track_index}.{ffprobe language tag}.srt`) so
they drop into the same round-trip pipeline external files use. The `Subtitle` row's
`language`, unlike the filename, is normalized (see below) rather than ffprobe's raw tag.
Image-based codecs (PGS, VobSub, DVB) aren't extracted yet — that needs OCR, a future item.
Each track's forced/hearing-impaired disposition flags are read from the container and
stored on its `Subtitle` row.

Extraction writes to a temporary file next to `output_path` and only replaces it once
`ffmpeg` exits successfully, so a killed or timed-out run can't leave a corrupt `.srt`
mistaken for a completed extraction on a later scan. A missing `ffmpeg` binary is skipped
like a missing `ffprobe` — logged and left out of the discovery result, not raised.

Probing/extraction is per media file, gated by its effective `LanguageProfile`
(`extract_embedded_subtitles`, see [Language Profiles](language-profiles.md)) — a file with
no effective profile, or a profile with the toggle off, only gets external discovery. An
already-extracted file is reused on a later scan instead of re-running `ffmpeg`.

A track is only extracted if its language doesn't already have an external subtitle (found
in the same scan, or already on record) — if it does, the embedded track is left alone: the
language is already covered, possibly by a better/manual translation, so there's nothing an
extraction would add. Language codes are compared loosely (ffprobe's ISO 639-2 tags, e.g.
`por`, against the app's ISO 639-1-ish codes, e.g. `pt-BR`), collapsed to their primary
subtag — `language_codes.normalize_language_code()`. Region is ignored in that comparison
since a container's language tag can't distinguish e.g. Brazilian from European Portuguese.
