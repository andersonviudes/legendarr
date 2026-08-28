from collections.abc import Iterator

from fastapi import APIRouter, Depends
from sqlmodel import Session

from legendarr_backend.database.engine import get_session
from legendarr_backend.statistics.compute_statistics import compute_statistics
from legendarr_backend.statistics.schemas import StatisticsRead

router = APIRouter(prefix="/statistics", tags=["Statistics"])


def _get_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


@router.get("", response_model=StatisticsRead)
def get_statistics(session: Session = Depends(_get_session)) -> StatisticsRead:
    return compute_statistics(session)
