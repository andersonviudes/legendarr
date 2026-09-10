from collections.abc import Iterator

from fastapi import APIRouter, Depends
from sqlmodel import Session

from legendarr_backend.database.engine import get_session
from legendarr_backend.history.list_history import DEFAULT_PAGE_SIZE, list_history
from legendarr_backend.history.schemas import HistoryPageRead

router = APIRouter(prefix="/history", tags=["History"])


def _get_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


@router.get("", response_model=HistoryPageRead)
def get_history(
    q: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    session: Session = Depends(_get_session),
) -> HistoryPageRead:
    result = list_history(session, search=q, page=page, page_size=page_size)
    return HistoryPageRead(
        entries=result.entries, total=result.total, page=page, page_size=page_size
    )
