from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.arr_services.path_mapping import resolve_local_path


def _service(remote: str | None = None, local: str | None = None) -> ArrService:
    return ArrService(
        name="radarr",
        service_type="radarr",
        host="radarr",
        port=7878,
        api_key="api-key",
        remote_path_prefix=remote,
        local_path_prefix=local,
    )


def test_returns_path_unchanged_without_mapping():
    assert resolve_local_path(_service(), "/movies/Foo") == "/movies/Foo"


def test_returns_path_unchanged_with_only_half_the_mapping():
    assert resolve_local_path(_service(remote="/movies"), "/movies/Foo") == "/movies/Foo"
    assert resolve_local_path(_service(local="/media/movies"), "/movies/Foo") == "/movies/Foo"


def test_replaces_matching_prefix():
    service = _service(remote="/movies", local="/media/movies")

    assert resolve_local_path(service, "/movies/Foo/file.mkv") == "/media/movies/Foo/file.mkv"


def test_path_equal_to_the_prefix_maps_to_the_local_prefix():
    service = _service(remote="/movies", local="/media/movies")

    assert resolve_local_path(service, "/movies") == "/media/movies"


def test_tolerates_trailing_slashes_in_the_prefixes():
    service = _service(remote="/movies/", local="/media/movies/")

    assert resolve_local_path(service, "/movies/Foo") == "/media/movies/Foo"


def test_does_not_match_a_prefix_that_is_only_a_partial_segment():
    service = _service(remote="/movies", local="/media/movies")

    assert resolve_local_path(service, "/movies2/Foo") == "/movies2/Foo"


def test_returns_path_unchanged_when_it_starts_elsewhere():
    service = _service(remote="/movies", local="/media/movies")

    assert resolve_local_path(service, "/tv/Bar") == "/tv/Bar"
