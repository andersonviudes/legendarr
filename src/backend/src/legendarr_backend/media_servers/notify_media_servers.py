import logging
from pathlib import Path

from sqlmodel import Session

from legendarr_backend.media_servers.client_factory import build_media_server_provider
from legendarr_backend.media_servers.manage_media_server import list_media_servers
from legendarr_backend.media_servers.models import MediaServerConfig

logger = logging.getLogger(__name__)


def notify_media_servers_of_subtitle_write(session: Session, video_path: Path) -> None:
    """Best-effort refresh of every enabled+configured media server after a subtitle was
    just written next to `video_path`. Called from `subtitle_acquisition.jobs` and
    `subtitle_translation.jobs` right after a download/upgrade/translation actually
    writes a file — never for a skipped/no-op run.

    One server failing (unreachable, rejected credential, ...) never blocks another,
    and never blocks the acquisition/translation job that just succeeded — same
    isolation as `media_metadata/fetch_metadata.py::_safe_fetch`.
    """
    for config in _enabled_servers(session):
        _safe_notify(config, video_path)


def _enabled_servers(session: Session) -> list[MediaServerConfig]:
    return [
        config
        for config in list_media_servers(session)
        if config.enabled and config.has_credentials
    ]


def _safe_notify(config: MediaServerConfig, video_path: Path) -> None:
    provider = build_media_server_provider(config)
    try:
        provider.notify_subtitle_written(video_path)
    except Exception:
        logger.exception("media server refresh failed for %r via %s", video_path, config.kind)
    finally:
        provider.close()
