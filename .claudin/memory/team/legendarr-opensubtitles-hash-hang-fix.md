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

**Follow-up 2026-09-11 (branch `fix/acquire-bulk-wedged-workers`):** the same two movies came
back stuck the next day. The screenshot pinned it precisely — `_running_tasks_list.html` only
renders the progress bar when `task.phase` is set, and there was none, so the wedge was *before*
`acquire_media_file_subtitle.py`'s first `on_progress` (line ~180). For a **movie** that path is
all DB work except the hash, so the instance was simply running a build older than v0.22.10 (the
release that first carried the 30s timeout). Four things landed off the back of that:

1. `compute_napiprojekt_hash` got the same daemon-thread guard (60s, scaled for its 10MB read),
   returns `str | None`, and absorbed the `path.is_file()` check from `napiprojekt.py`'s call
   site — closing the "still open" item this memory used to carry.
2. `provider_search.py`'s `with ThreadPoolExecutor(...) as executor: executor.map(...)` was the
   real amplifier: `__exit__` is `shutdown(wait=True)`, so *any* provider thread that never
   returns wedges the acquisition worker permanently, and its non-daemon pool threads block
   interpreter shutdown too. Replaced by `_search_all` — one `Thread(daemon=True)` per provider
   plus a single shared-deadline `join()`, `DEFAULT_PROVIDER_SEARCH_TIMEOUT_SECONDS = 120.0`.
   A timed-out provider is reported as its own `TimeoutError` *and* recorded as a circuit-breaker
   failure, so a chronically unresponsive provider opens its circuit instead of costing 120s per
   media file.
3. The hash is no longer computed unconditionally: `search_context.py` asks
   `provider_chain.moviehash_search_enabled(session)` first (OpenSubtitles enabled +
   credentialed + `use_hash`). It's the only step in the pre-progress path that touches the
   video at all, so gating it keeps an unresponsive mount from stalling acquisition for users
   who don't even hash.
4. There is **no watchdog and cannot be one** — a thread blocked in an uninterruptible syscall
   can't be killed from Python, and `running_tasks.py` only drops an entry on a
   `JobExecutionEvent` that a wedged job never fires. So instead: `RunningTask.stalled`
   (computed in `tasks()` like `queued`, threshold `STALLED_TASK_THRESHOLD_SECONDS = 7200.0`),
   a one-time WARNING per stalled task, and a "Stalled" badge in the Tasks/Live Activity list.
   Visibility only — restarting the process is still the only way to get the worker slot back.
