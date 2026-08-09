PROVIDER_LABELS = {
    "opensubtitles": "OpenSubtitles",
    "addic7ed": "Addic7ed",
    "yify_subtitles": "YIFY Subtitles",
    "subdl": "Subdl",
    "tvsubtitles": "TVsubtitles",
    "legendas_net": "legendas.net",
    "napiprojekt": "Napiprojekt",
    "subsource": "Subsource",
    "animetosho": "Anime Tosho",
    "supersubtitles": "Supersubtitles",
    "animekalesi": "AnimeKalesi",
    "greeksubtitles": "GreekSubtitles",
    "betaseries": "BetaSeries",
}

# Which credential fields the edit form shows for each provider kind — matches the auth
# shapes `legendarr_backend.subtitle_acquisition.connection_tests` checks against. A kind
# with no entry here needs no credential at all (reachability-only "test connection").
PROVIDER_CREDENTIAL_FIELDS = {
    "opensubtitles": ("api_key",),
    "addic7ed": ("username", "password"),
    "subdl": ("api_key",),
    "legendas_net": ("username", "password"),
    "subsource": ("api_key",),
    "betaseries": ("api_key",),
}

# Provider-specific search options shown on the edit form, beyond credentials — currently
# only OpenSubtitles has any (mirrors Bazarr's opensubtitlescom provider settings). Search
# itself isn't built yet, so these are saved but not yet read back out anywhere.
PROVIDER_SEARCH_OPTIONS = {
    "opensubtitles": ("use_hash", "include_ai_translated", "include_machine_translated"),
}


def provider_label(kind: str) -> str:
    return PROVIDER_LABELS.get(kind, kind)


def provider_credential_fields(kind: str) -> tuple[str, ...]:
    return PROVIDER_CREDENTIAL_FIELDS.get(kind, ())


def provider_search_options(kind: str) -> tuple[str, ...]:
    return PROVIDER_SEARCH_OPTIONS.get(kind, ())
