PROVIDER_LABELS = {
    "plex": "Plex",
    "jellyfin": "Jellyfin",
}


def provider_label(kind: str) -> str:
    return PROVIDER_LABELS.get(kind, kind)
