from pathlib import Path

from legendarr_backend.media_servers import notify_media_servers as notify_module
from legendarr_backend.media_servers.manage_media_server import update_media_server
from legendarr_backend.media_servers.models import MediaServerConfig
from legendarr_backend.media_servers.notify_media_servers import (
    notify_media_servers_of_subtitle_write,
)
from legendarr_backend.media_servers.schemas import MediaServerConfigInput


class _RecordingProvider:
    def __init__(self, name: str, calls: list, fail: bool = False) -> None:
        self.name = name
        self._calls = calls
        self._fail = fail
        self.closed = False

    def notify_subtitle_written(self, video_path: Path) -> None:
        self._calls.append((self.name, video_path))
        if self._fail:
            raise RuntimeError("boom")

    def close(self) -> None:
        self.closed = True


def _configured_server(session, kind: str) -> MediaServerConfig:
    server = MediaServerConfig(kind=kind)
    session.add(server)
    session.commit()
    session.refresh(server)
    assert server.id is not None
    updated = update_media_server(
        session,
        server.id,
        MediaServerConfigInput(enabled=True, base_url="http://host:1234", token="tok"),
    )
    assert updated is not None
    return updated


def test_notifies_every_enabled_configured_server(in_memory_session, monkeypatch):
    _configured_server(in_memory_session, "plex")
    _configured_server(in_memory_session, "jellyfin")
    calls: list = []
    monkeypatch.setattr(
        notify_module,
        "build_media_server_provider",
        lambda config: _RecordingProvider(config.kind, calls),
    )

    notify_media_servers_of_subtitle_write(in_memory_session, Path("/movies/Foo/Foo.mkv"))

    assert {name for name, _ in calls} == {"plex", "jellyfin"}
    assert all(path == Path("/movies/Foo/Foo.mkv") for _, path in calls)


def test_skips_disabled_and_unconfigured_servers(in_memory_session, monkeypatch):
    unconfigured = MediaServerConfig(kind="jellyfin", enabled=True)  # no base_url/token
    in_memory_session.add(unconfigured)
    in_memory_session.commit()
    disabled = _configured_server(in_memory_session, "plex")
    disabled.enabled = False
    in_memory_session.add(disabled)
    in_memory_session.commit()
    calls: list = []
    monkeypatch.setattr(
        notify_module,
        "build_media_server_provider",
        lambda config: _RecordingProvider(config.kind, calls),
    )

    notify_media_servers_of_subtitle_write(in_memory_session, Path("/movies/Foo/Foo.mkv"))

    assert calls == []


def test_one_server_failing_does_not_block_another(in_memory_session, monkeypatch):
    _configured_server(in_memory_session, "plex")
    _configured_server(in_memory_session, "jellyfin")
    calls: list = []

    def _build(config):
        return _RecordingProvider(config.kind, calls, fail=(config.kind == "plex"))

    monkeypatch.setattr(notify_module, "build_media_server_provider", _build)

    # Must not raise even though the Plex provider fails.
    notify_media_servers_of_subtitle_write(in_memory_session, Path("/movies/Foo/Foo.mkv"))

    assert {name for name, _ in calls} == {"plex", "jellyfin"}
