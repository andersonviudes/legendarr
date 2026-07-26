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


QUEUE_WORKERS: dict[JobQueue, int] = {
    JobQueue.SYNC: 1,
    JobQueue.SCAN: 2,
    JobQueue.SCAN_BULK: 1,
}
