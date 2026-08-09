PROVIDER_LABELS = {
    "tvdb": "TheTVDB",
    "imdb": "IMDb",
}


def provider_label(kind: str) -> str:
    return PROVIDER_LABELS.get(kind, kind)
