"""Best-effort ISO 639 normalization so an embedded track's ffprobe language tag
(ISO 639-2, e.g. "eng", "por") can be compared against the codes the rest of the app
uses (language profiles, external subtitle filenames, e.g. "en", "pt-BR").

Region subtags (the "BR" in "pt-BR") aren't derivable from a container's language tag,
so normalization intentionally collapses to the primary language only — an embedded
generic "por" track is treated as matching a "pt-BR" profile target, since ffprobe has
no way to tell Brazilian from European Portuguese.
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
