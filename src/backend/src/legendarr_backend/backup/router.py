from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from legendarr_backend.backup.manage_backups import (
    backups_dir,
    create_backup,
    delete_backup,
    is_valid_backup_filename,
    list_backups,
)
from legendarr_backend.backup.restore_backup import InvalidBackupArchiveError, restore_backup
from legendarr_backend.backup.schemas import BackupRead, RestoreResult
from legendarr_backend.config.settings import get_settings

router = APIRouter(prefix="/backup", tags=["Backup"])


@router.get("/", response_model=list[BackupRead])
def get_backups() -> list[BackupRead]:
    return list_backups(get_settings())


@router.post("/", response_model=BackupRead, status_code=201)
def post_backup() -> BackupRead:
    return create_backup(get_settings())


@router.get("/{filename}/download")
def download_backup(filename: str) -> FileResponse:
    if not is_valid_backup_filename(filename):
        raise HTTPException(status_code=404, detail="Backup not found")
    settings = get_settings()
    path = backups_dir(settings) / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Backup not found")
    return FileResponse(path, media_type="application/zip", filename=filename)


@router.delete("/{filename}", status_code=204)
def delete_backup_route(filename: str) -> None:
    if not delete_backup(get_settings(), filename):
        raise HTTPException(status_code=404, detail="Backup not found")


@router.post("/restore")
async def post_restore(
    file: UploadFile = File(...),  # noqa: B008 — FastAPI's own multipart dependency idiom
) -> RestoreResult:
    content = await file.read()
    try:
        return restore_backup(get_settings(), content)
    except InvalidBackupArchiveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
