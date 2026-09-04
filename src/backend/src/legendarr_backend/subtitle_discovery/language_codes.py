"""Best-effort ISO 639 normalization so an embedded track's ffprobe language tag
(ISO 639-2, e.g. "eng", "por") can be compared against the codes the rest of the app
uses (language profiles, external subtitle filenames, e.g. "en", "pt-BR").

Region subtags (the "BR" in "pt-BR") aren't derivable from a *bare* ISO 639-2 tag, so
`normalize_language_code` intentionally collapses to the primary language only for
matching purposes — an embedded generic "por" track is treated as matching a "pt-BR"
profile target, since ffprobe has no way to tell Brazilian from European Portuguese in
that case. But a container can also carry an already region-qualified IETF tag (e.g.
"pt-BR" itself, written by `mkvmerge --language`) — `display_language_code` keeps that
subtag instead of collapsing it away, so the UI can still tell two such tracks apart.
"""

# ISO 639-2 (bibliographic and terminological forms) -> ISO 639-1, for the languages a
# subtitle/translation workflow is realistically going to see. Not exhaustive.
_ISO_639_2_TO_1 = {
    "eng": "en",
    "por": "pt",
    "spa": "es",
    "fre": "fr",
    "fra": "fr",
    "ger": "de",
    "deu": "de",
    "ita": "it",
    "jpn": "ja",
    "kor": "ko",
    "chi": "zh",
    "zho": "zh",
    "rus": "ru",
    "ara": "ar",
    "dut": "nl",
    "nld": "nl",
    "swe": "sv",
    "nor": "no",
    "dan": "da",
    "fin": "fi",
    "pol": "pl",
    "tur": "tr",
    "heb": "he",
    "hin": "hi",
    "tha": "th",
    "vie": "vi",
    "ind": "id",
    "cze": "cs",
    "ces": "cs",
    "gre": "el",
    "ell": "el",
    "hun": "hu",
    "rum": "ro",
    "ron": "ro",
    "ukr": "uk",
    "bul": "bg",
    "hrv": "hr",
    "srp": "sr",
    "slo": "sk",
    "slk": "sk",
    "slv": "sl",
    "lit": "lt",
    "lav": "lv",
    "est": "et",
    "per": "fa",
    "fas": "fa",
    "urd": "ur",
    "ben": "bn",
    "tam": "ta",
    "tel": "te",
    "may": "ms",
    "msa": "ms",
    "fil": "tl",
    "cat": "ca",
    "baq": "eu",
    "eus": "eu",
    "glg": "gl",
}


def normalize_language_code(code: str) -> str:
    """Collapse a language code to its primary ISO 639-1 subtag for comparison.

    "en" -> "en", "eng" -> "en", "pt-BR" -> "pt", "por" -> "pt". Falls back to the
    lowercased primary subtag unchanged when it isn't in the table (e.g. an ISO 639-1
    code this table doesn't list, or "und").
    """
    primary = code.strip().lower().split("-")[0]
    if len(primary) == 2:
        return primary
    return _ISO_639_2_TO_1.get(primary, primary)


def display_language_code(code: str) -> str:
    """Map a language tag to a UI-friendly form without discarding a region/script subtag
    the way `normalize_language_code` does for matching. Only the primary subtag is looked
    up in the ISO 639-2 table; any subtag after the first "-" is kept as-is.

    "en" -> "en", "eng" -> "en", "pt-BR" -> "pt-br", "por" -> "pt".
    """
    primary, _, rest = code.strip().lower().partition("-")
    primary = primary if len(primary) == 2 else _ISO_639_2_TO_1.get(primary, primary)
    return f"{primary}-{rest}" if rest else primary
