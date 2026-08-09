import logging

from fastapi import APIRouter, HTTPException

from legendarr_backend.system.browse_directory import list_subdirectories
from legendarr_backend.system.read_logs import list_recent_logs
from legendarr_backend.system.schemas import DirectoryListingRead, LogLineRead, LogLinesRead

router = APIRouter(prefix="/system")

_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


@router.get("/directories", response_model=DirectoryListingRead)
def get_directories(path: str = "/") -> DirectoryListingRead:
    try:
        listing = list_subdirectories(path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Directory not found") from exc
    except NotADirectoryError as exc:
        raise HTTPException(status_code=422, detail="Path is not a directory") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Permission denied") from exc
    return DirectoryListingRead(
        path=listing.path, parent=listing.parent, directories=listing.directories
    )


@router.get("/logs", response_model=LogLinesRead)
def get_logs(level: str | None = None, limit: int = 200) -> LogLinesRead:
    min_level = None
    if level is not None:
        try:
            min_level = _LOG_LEVELS[level.upper()]
        except KeyError as exc:
            raise HTTPException(status_code=422, detail="Unknown log level") from exc
    lines = list_recent_logs(min_level=min_level, limit=limit)
    return LogLinesRead(lines=[LogLineRead(text=line.text, level=line.level) for line in lines])
