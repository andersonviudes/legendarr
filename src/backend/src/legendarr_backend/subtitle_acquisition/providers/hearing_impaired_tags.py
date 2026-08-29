"""Text-tag heuristic for detecting a hearing-impaired/SDH subtitle from free-text
uploader fields (comments, release names) — ported from Bazarr's own `SubdlProvider._is_hi`
and `SubsourceProvider._is_hi` (`/home/viudes/projects/bazarr/custom_libs/
subliminal_patch/providers/subdl.py:423-438`, `subsource.py:376-406`), which carry a
near-identical version of this each. Shared here since both `subdl.py` and `subsource.py`
need it as a fallback for results that don't set their provider's own structured HI field.
"""

_NON_HI_TAGS = (
    "hi remove",
    "non hi",
    "nonhi",
    "non-hi",
    "non-sdh",
    "non sdh",
    "nonsdh",
    "sdh remove",
)

_HI_TAGS = (
    "_hi_",
    " hi ",
    ".hi.",
    "hi ",
    " hi",
    "sdh",
    "𝓢𝓓𝓗",
    "_cc_",
    " cc ",
    ".cc.",
    "closed caption",
)


def contains_hearing_impaired_tag(*texts: str) -> bool:
    """`True` if any of `texts` (comments, release names, ...) contains an HI/SDH tag and
    none of them explicitly says "non-HI"/"SDH removed" — a `non_hi` mention anywhere
    overrides an `hi` one, same precedence Bazarr's own heuristic uses.
    """
    lowered = [text.lower() for text in texts if text]
    if any(tag in text for text in lowered for tag in _NON_HI_TAGS):
        return False
    return any(tag in text for text in lowered for tag in _HI_TAGS)
