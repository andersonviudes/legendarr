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

# One-line "what is this" blurb shown on the provider list card, below the name — every
# kind in PROVIDER_LABELS needs an entry here. i18n keys, not raw strings, like every
# other user-facing string in this module's templates.
PROVIDER_DESCRIPTIONS = {
    "opensubtitles": "subtitle_acquisition.description.opensubtitles",
    "addic7ed": "subtitle_acquisition.description.addic7ed",
    "yify_subtitles": "subtitle_acquisition.description.yify_subtitles",
    "subdl": "subtitle_acquisition.description.subdl",
    "tvsubtitles": "subtitle_acquisition.description.tvsubtitles",
    "legendas_net": "subtitle_acquisition.description.legendas_net",
    "napiprojekt": "subtitle_acquisition.description.napiprojekt",
    "subsource": "subtitle_acquisition.description.subsource",
    "animetosho": "subtitle_acquisition.description.animetosho",
    "supersubtitles": "subtitle_acquisition.description.supersubtitles",
    "animekalesi": "subtitle_acquisition.description.animekalesi",
    "greeksubtitles": "subtitle_acquisition.description.greeksubtitles",
    "betaseries": "subtitle_acquisition.description.betaseries",
}

# Which credential fields the edit form shows for each provider kind — matches the auth
# shapes `legendarr_backend.subtitle_acquisition.connection_tests` checks against. A kind
# with no entry here needs no credential at all (reachability-only "test connection").
PROVIDER_CREDENTIAL_FIELDS = {
    "addic7ed": ("username", "password"),
    # `Api-Key` is a legendarr-side application credential (see
    # `subtitle_acquisition.providers.opensubtitles`'s module docstring), never the
    # user's own — the user only ever supplies their OpenSubtitles.com username/password.
    "opensubtitles": ("username", "password"),
    "subdl": ("api_key",),
    "legendas_net": ("username", "password"),
    "subsource": ("api_key",),
    "betaseries": ("api_key",),
    # Anime Tosho's "api_key" holds an AniDB API client key, not a credential for
    # animetosho.org itself — see `legendarr_backend.subtitle_acquisition.providers.
    # animetosho` for why one's needed.
    "animetosho": ("api_key",),
}

# Label shown for the "username" credential field — most providers log in with a real
# username/handle, so the generic "Username" label fits. legendas.net's own login form
# (`type="email" name="email"`) only ever accepts the account's email address, and a
# site handle there 401s with the same generic "Invalid username/password" the API
# gives for any wrong credential — a kind with no entry here keeps the generic label.
PROVIDER_USERNAME_LABELS = {
    "legendas_net": "common.email",
}

# Extra explanation shown under a credential field for a kind whose field isn't
# self-explanatory from its generic label alone, or (Anime Tosho's case) isn't actually
# required — a kind with no entry here shows no extra hint.
PROVIDER_CREDENTIAL_HINTS = {
    "animetosho": "subtitle_acquisition.animetosho_api_key_hint",
    "legendas_net": "subtitle_acquisition.legendas_net_email_hint",
}

# Provider-specific search options shown on the edit form, beyond credentials — currently
# only OpenSubtitles has any (mirrors Bazarr's opensubtitlescom provider settings). Search
# itself isn't built yet, so these are saved but not yet read back out anywhere.
PROVIDER_SEARCH_OPTIONS = {
    "opensubtitles": ("use_hash", "include_ai_translated", "include_machine_translated"),
}


def provider_label(kind: str) -> str:
    return PROVIDER_LABELS.get(kind, kind)


def provider_description(kind: str) -> str | None:
    return PROVIDER_DESCRIPTIONS.get(kind)


def provider_username_label(kind: str) -> str:
    return PROVIDER_USERNAME_LABELS.get(kind, "common.username")


def provider_credential_fields(kind: str) -> tuple[str, ...]:
    return PROVIDER_CREDENTIAL_FIELDS.get(kind, ())


def provider_credential_hint(kind: str) -> str | None:
    return PROVIDER_CREDENTIAL_HINTS.get(kind)


def provider_search_options(kind: str) -> tuple[str, ...]:
    return PROVIDER_SEARCH_OPTIONS.get(kind, ())
