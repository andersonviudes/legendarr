from enum import StrEnum


class JobQueue(StrEnum):
    """Named APScheduler executors jobs register into.

    Each queue is its own thread-pool executor, so one job type's concurrency never
    starves another's. Add a member here when a new job type needs its own queue —
    don't pre-create queues for jobs that don't exist yet.
    """

    SYNC = "sync"
    # Single-item scans triggered by events (webhook, history poll) stay responsive:
    # they never queue behind the bulk full-scan backlog.
    SCAN = "scan"
    # Interval fan-out walks the whole library one item at a time — slow on purpose,
    # the pool sizes are the I/O throttle on network mounts.
    SCAN_BULK = "scan_bulk"
    # Translation calls a real provider API per subtitle line — its own queue so a slow
    # provider never starves (or queues behind) subtitle scans.
    TRANSLATE = "translate"
    # Manual bulk fan-out over every `MediaFile`, same reasoning as `SCAN_BULK`.
    TRANSLATE_BULK = "translate_bulk"
    # Acquisition calls a real subtitle-provider API per media file — its own queue,
    # same reasoning as `TRANSLATE`, so a slow/rate-limited provider never starves scans
    # or translations.
    ACQUIRE = "acquire"
    # Manual bulk fan-out over every `MediaFile`, same reasoning as `TRANSLATE_BULK`.
    ACQUIRE_BULK = "acquire_bulk"
    # Timing sync shells out to `ffsubsync`, which decodes audio and can run for a while —
    # its own queue, same reasoning as `TRANSLATE`/`ACQUIRE`. Manual-only (one subtitle at a
    # time, triggered from the UI), so no `_BULK` variant.
    TIMING_SYNC = "timing_sync"
    # Metadata fetch calls a real provider API per movie/series. Manual-only (no periodic
    # equivalent — metadata is fetched once on discovery, see `fetch_metadata_for_new_items`),
    # triggered by the "Refetch All" button; its own queue, same `_BULK` reasoning as
    # `SCAN_BULK`/`TRANSLATE_BULK`/`ACQUIRE_BULK`.
    METADATA_BULK = "metadata_bulk"
    # Orphaned-temp-file sweep (ROADMAP.md 0.22.0) — filesystem-only work (no subprocess,
    # no provider API call), unrelated to every job type above; its own queue so it never
    # competes with (or is throttled by) a bulk scan/translate/acquire/metadata run.
    MAINTENANCE = "maintenance"
    # Periodic upgrade re-search: walks the whole library looking for a better-scoring
    # release for a subtitle already acquired. Runs on its own daily schedule, fully
    # decoupled from ACQUIRE/ACQUIRE_BULK so acquisition and upgrade never compete for the
    # same executor. Periodic-only, same reasoning as METADATA_BULK — no manual trigger.
    UPGRADE_BULK = "upgrade_bulk"


QUEUE_WORKERS: dict[JobQueue, int] = {
    JobQueue.SYNC: 1,
    JobQueue.SCAN: 2,
    JobQueue.SCAN_BULK: 1,
    JobQueue.TRANSLATE: 2,
    JobQueue.TRANSLATE_BULK: 1,
    JobQueue.ACQUIRE: 2,
    JobQueue.ACQUIRE_BULK: 1,
    JobQueue.TIMING_SYNC: 2,
    JobQueue.METADATA_BULK: 1,
    JobQueue.MAINTENANCE: 1,
    JobQueue.UPGRADE_BULK: 1,
}
