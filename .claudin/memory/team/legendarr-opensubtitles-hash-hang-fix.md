---
name: legendarr-opensubtitles-hash-hang-fix
description: compute_opensubtitles_hash() did raw blocking file I/O with no timeout, unlike every other subprocess/model call in the acquisition pipeline — wedged acquire_bulk on a stalled network mount
type: project
---

Fixed 2026-09-10. User reported two movies (`Dragon Ball Super: Super Hero`/`Broly`) stuck in
Live Activity as `acquire_bulk` with **no progress info at all** — unlike every other stuck-task
report so far, which at least shows a phase/provider (`report_progress`). Traced to
`resolve_subtitle_search_context` (`subtitle_acquisition/search_context.py:51`) calling
`compute_opensubtitles_hash` (`opensubtitles_hash.py`) — this runs once, unconditionally, before
`acquire_subtitle_for_media_file`'s very first `on_progress()` checkpoint, so a hang here shows
up exactly as "nothing happened yet", never as a stalled phase.

`compute_opensubtitles_hash` did a plain synchronous `path.stat()` + `file.open("rb").read()` —
the *only* blocking call left anywhere in the acquisition pipeline with zero timeout, unlike
`ffprobe`/`ffmpeg` (`subprocess.run(..., timeout=...)`) and now Whisper transcription (see
[[legendarr-hung-job-dedup-fix]]'s daemon-thread pattern). On a stalled network mount (NAS-hosted
library, see [[legendarr-prod-deployment-topology]]), the underlying `read()`/`stat()` syscall
blocks in the kernel in an uninterruptible state that no Python-level timeout can interrupt —
same fundamental issue PR #128 fixed for the Whisper call, just a different call site it didn't
cover.

**Fix:** `compute_opensubtitles_hash(path, *, timeout_seconds=DEFAULT_HASH_TIMEOUT_SECONDS=30.0)`
now runs the actual read (renamed to private `_compute_hash`, which also absorbed the
`path.is_file()` existence check previously done at the call site — that stat call needs the
same bound) on a `daemon=True` thread and `thread.join(timeout=...)`s it, returning `None` on
timeout instead of blocking forever — identical shape to `_transcribe_with_timeout`
(`audio_transcription/transcribe_audio.py`). `search_context.py`'s call site simplified to a bare
`compute_opensubtitles_hash(video_path)` now that the existence check lives inside.

**Still open:** `providers/napiprojekt_hash.py`'s `compute_napiprojekt_hash` has the exact same
shape (plain `path.open("rb").read(10MB)`, no timeout) and wasn't touched — it only runs when
Napiprojekt is in the resolved provider chain, so it wasn't implicated in this specific report,
but it's the same latent risk and should get the same guard if it's ever the confirmed cause of
a future stuck task.
