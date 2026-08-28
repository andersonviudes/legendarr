from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HistoryEntryRead(BaseModel):
    """One row of the History view — either a successful `TranslationAttempt`/
    `AcquisitionAttempt`, or a `TranslationFailure`/`AcquisitionFailure`
    (ROADMAP.md 0.20.0). `provider`/`error_message` are `None` on the side that
    doesn't apply: a success has no error, a failure has no single winning provider.
    """

    category: Literal["translation", "acquisition"]
    status: Literal["success", "failure"]
    media_title: str
    language: str
    provider: str | None
    error_message: str | None
    occurred_at: datetime
