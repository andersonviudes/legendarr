PROVIDER_LABELS = {
    "tvdb": "TheTVDB",
    "imdb": "IMDb",
    "tmdb": "TMDb",
}


def provider_label(kind: str) -> str:
    return PROVIDER_LABELS.get(kind, kind)
