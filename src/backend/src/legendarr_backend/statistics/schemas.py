from datetime import date

from pydantic import BaseModel


class DailyCount(BaseModel):
    date: date
    count: int


class BreakdownEntry(BaseModel):
    label: str
    count: int


class CategoryStatistics(BaseModel):
    """One data source's (translation or acquisition) Statistics view breakdown —
    ROADMAP.md 0.20.0. `daily` covers the fixed 30-day trend window (zero-filled, oldest
    first); `by_profile`/`by_provider` are all-time cumulative totals, same precedent as
    the dashboard's other stat cards.
    """

    total: int
    daily: list[DailyCount]
    by_profile: list[BreakdownEntry]
    by_provider: list[BreakdownEntry]


class StatisticsRead(BaseModel):
    translated: CategoryStatistics
    acquired: CategoryStatistics
