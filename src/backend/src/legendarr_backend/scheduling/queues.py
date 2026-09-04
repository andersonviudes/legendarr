import os
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
    # Interval fan-out walks the whole library — deliberately capped well below the
    # CPU-scaled bulk queues, the pool size is the I/O throttle on network mounts.
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
    # Metadata fetch calls a real provider API per movie/series. Bulk fan-out over every
    # synced item, same `_BULK` reasoning as `SCAN_BULK`/`TRANSLATE_BULK`/`ACQUIRE_BULK` —
    # shared by the periodic refresh job and the manual "Refetch All" button.
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


def cpu_scaled_workers(minimum: int = 1, maximum: int = 2) -> int:
    """The host's CPU count, capped at `maximum` (never below `minimum`) — the default
    sizing for a bulk queue's worker pool instead of a hardcoded constant, so a modest
    host doesn't over-commit while a beefier host still doesn't spawn more workers than
    useful. Capped lower than Bazarr's `concurrent_jobs` default (`app/config.py`:
    `4 if os.cpu_count() >= 4 else os.cpu_count()`) on purpose — `PROVIDER_MAX_CONCURRENCY`
    already limits any one provider to 3 concurrent calls, so a couple of bulk-queue
    workers is enough to keep several different files/providers in flight without a
    modest host over-committing. Safe to use even for a provider-facing queue:
    `provider_concurrency.limit_concurrency` caps how many of those concurrent workers
    can hit the *same* provider at once, independent of how many vCPUs the host has.
    """
    return max(minimum, min(maximum, os.cpu_count() or 1))


QUEUE_WORKERS: dict[JobQueue, int] = {
    JobQueue.SYNC: 2,
    JobQueue.SCAN: 2,
    JobQueue.SCAN_BULK: 2,
    JobQueue.TRANSLATE: 2,
    JobQueue.TRANSLATE_BULK: cpu_scaled_workers(),
    JobQueue.ACQUIRE: 2,
    JobQueue.ACQUIRE_BULK: cpu_scaled_workers(),
    JobQueue.TIMING_SYNC: cpu_scaled_workers(),
    JobQueue.METADATA_BULK: cpu_scaled_workers(),
    JobQueue.MAINTENANCE: 2,
    JobQueue.UPGRADE_BULK: cpu_scaled_workers(),
}
