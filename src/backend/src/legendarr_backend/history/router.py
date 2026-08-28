from collections.abc import Iterator

from fastapi import APIRouter, Depends
from sqlmodel import Session

from legendarr_backend.database.engine import get_session
from legendarr_backend.history.list_history import DEFAULT_LIMIT, list_history
from legendarr_backend.history.schemas import HistoryEntryRead

router = APIRouter(prefix="/history", tags=["History"])


def _get_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


@router.get("", response_model=list[HistoryEntryRead])
def get_history(
    limit: int = DEFAULT_LIMIT, session: Session = Depends(_get_session)
) -> list[HistoryEntryRead]:
    return list_history(session, limit=limit)
