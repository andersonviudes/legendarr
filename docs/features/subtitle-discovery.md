# Subtitle Discovery

Before a subtitle can be translated, legendarr needs to find it. `scan_video_subtitles()`
discovers every subtitle available for a video file and reports where each one came from.

## External subtitles

Sibling files next to the video (matching its filename stem) are always considered.
Recognized extensions: `.srt`, `.ass`, `.ssa`, `.vtt`. The language of an external subtitle
is guessed from its filename suffix (e.g. `movie.pt-BR.srt` → `pt-BR`); files without a
language suffix are reported as `und` (undetermined).

## Embedded subtitles

Subtitle tracks embedded inside the video container are also modeled
(`SubtitleOrigin.EMBEDDED`), with probing via the container wired in as the feature
matures.
