from legendarr_backend.arr_services.models import ArrService


def resolve_local_path(arr_service: ArrService, remote_path: str) -> str:
    """Translate a path reported by Radarr/Sonarr into legendarr's filesystem view.

    Applies the connection's path mapping (remote prefix -> local prefix) when both
    halves are configured and the path actually starts with the remote prefix;
    anything else is returned untouched. Pure string work — the local path is never
    stat'ed, so an unmounted library doesn't blow up callers.
    """
    remote = (arr_service.remote_path_prefix or "").rstrip("/")
    local = (arr_service.local_path_prefix or "").rstrip("/")
    if not remote or not local:
        return remote_path
    if remote_path == remote:
        return local
    if remote_path.startswith(remote + "/"):
        return local + remote_path[len(remote) :]
    return remote_path
