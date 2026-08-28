---
name: legendarr-ffmpeg-temp-suffix-format-gotcha
description: ffmpeg subprocess calls that write to a .tmp-suffixed temp sibling must pass -f explicitly, or muxer autodetection fails
type: project
---

Any `subprocess.run(["ffmpeg", ...])` call in `subtitle_discovery` that writes to an
atomic-rename temp path (`<output>.<ext>.tmp`, replaced via `os.replace()` only on
success) must pass `-f <format>` explicitly. ffmpeg picks its output muxer from the
filename extension alone — `-c:s <codec>` only selects the codec inside that
container — and `.tmp` isn't a format it recognizes, so it fails outright with
`Unable to find a suitable output format for '<path>.tmp'` before touching any
stream.

`extract_pgs_subtitle_stream` (`probe_embedded_subtitles.py`) already did this right
(`-f sup`). `extract_embedded_subtitle_track`'s SubRip path didn't, so *every*
embedded-subtitle-extraction attempt failed — silently crashing the whole
`subtitle_scan` job (unhandled `CalledProcessError`), since none of the existing
tests exercise the real `ffmpeg` binary (they monkeypatch `subprocess.run`). Fixed
2026-08-27 by adding `-f srt` to match. Confirmed against real files: previously
every scan crashed before it could reconcile a deleted subtitle's still-present DB
row; after the fix, scans extract every embedded text track and correctly detect a
removed external file as missing again.

Lesson for any future ffmpeg-invoking code here: if the destination path doesn't end
in a real container extension, don't rely on ffmpeg to infer one.
