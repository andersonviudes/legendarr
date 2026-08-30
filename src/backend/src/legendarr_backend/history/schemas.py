from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HistoryEntryRead(BaseModel):
    """One row of the History view — either a successful `TranslationAttempt`/
    `AcquisitionAttempt`, or a `TranslationFailure`/`AcquisitionFailure`
    (ROADMAP.md 0.20.0). `provider`/`error_message` are `None` on the side that
    doesn't apply: a success has no error, a failure has no single winning provider.
    """

    category: Literal["translation", "acquisition", "upgrade"]
    status: Literal["success", "failure"]
    media_title: str
    language: str
    provider: str | None
    error_message: str | None
    occurred_at: datetime
    # The winning candidate's match score (0.0-1.0) — only ever set on an acquisition
    # success, since that's the only source table that scores its candidates
    # (`AcquisitionAttempt.score`); `None` for a translation row (no such concept) and
    # for either failure table (no winning candidate to score).
    score: float | None
    # The replaced subtitle's score (0.0-1.0), set only when `category` is "upgrade" —
    # what the new `score` improved from. `None` on every other row, including a
    # first-ever acquisition.
    previous_score: float | None
