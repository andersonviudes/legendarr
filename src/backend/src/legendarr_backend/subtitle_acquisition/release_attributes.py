"""Regex-based extraction of scene-release-name attributes (resolution, source, codec,
release group, edition) — ROADMAP 0.12.0's per-attribute score weighting. A small fixed
vocabulary is enough for the five attributes `match_score.py` weights, so this stays a
hand-rolled parser rather than pulling in a heavier third-party lib (guessit/subliminal)
for a narrow need — the same call `napiprojekt_hash.py`/`opensubtitles_hash.py` made.
"""

import re
from dataclasses import dataclass

_SEPARATOR_TRANSLATION = str.maketrans({".": " ", "_": " ", "(": " ", ")": " ", "-": " "})


@dataclass(frozen=True)
class ReleaseAttributes:
    """Attributes detected in one release name/filename, `None` for whichever weren't
    found — `match_score.py`'s weighted scoring only compares an attribute when the
    reference (the local video's filename) has a value for it.
    """

    resolution: str | None = None
    source: str | None = None
    codec: str | None = None
    release_group: str | None = None
    edition: str | None = None


_RESOLUTION_ALIASES = {"4k": "2160p"}

_VOCABULARY_PATTERNS = {
    "resolution": re.compile(r"\b(2160p|1080p|720p|480p|4k)\b", re.IGNORECASE),
    "source": re.compile(
        r"\b(blu-?ray|brrip|bdrip|web-?dl|webrip|hdtv|dvdrip|dvd|hdrip|pdtv)\b", re.IGNORECASE
    ),
    "codec": re.compile(
        r"\b(x264|x265|h\.?264|h\.?265|hevc|avc|xvid|divx|av1|vp9)\b", re.IGNORECASE
    ),
    "edition": re.compile(
        r"\b(extended|unrated|director'?s\.?\s?cut|theatrical|remastered|imax|ultimate|"
        r"special\.?\s?edition|uncut|criterion)\b",
        re.IGNORECASE,
    ),
}

# The release group isn't a vocabulary word — it's whatever trails the *last* matched
# vocabulary token, once that trailing text starts with a dash. Anchoring on the last
# vocabulary match's end (rather than a naive `rsplit("-", 1)`) is what keeps a source
# token's own internal dash (`WEB-DL`) from being misread as a group separator.
_GROUP_PATTERN = re.compile(r"^-([A-Za-z0-9]{2,15})\b")


def normalize_release_text(value: str) -> str:
    """Lowercased, with `.`/`_`/`(`/`)`/`-` collapsed to spaces and whitespace
    collapsed — the shared text-cleanup both this module's vocabulary matching and
    `match_score.py`'s title-similarity step build on.
    """
    return " ".join(value.lower().translate(_SEPARATOR_TRANSLATION).split())


def extract_release_attributes(value: str) -> ReleaseAttributes:
    """The resolution/source/codec/release-group/edition scene-release tokens found in
    `value` (a candidate's `release_name` or the local video's filename stem), `None`
    for whichever weren't recognized.
    """
    matches, spans = _find_vocabulary_matches(value)
    group, _ = _find_release_group(value, spans)
    resolution = matches.get("resolution")
    if resolution is not None:
        resolution = _RESOLUTION_ALIASES.get(resolution, resolution)
    return ReleaseAttributes(
        resolution=resolution,
        source=matches.get("source"),
        codec=matches.get("codec"),
        release_group=group,
        edition=matches.get("edition"),
    )


def strip_known_attribute_tokens(value: str) -> str:
    """`value` with every recognized vocabulary token and the trailing release-group
    tag blanked out, then normalized — what's left is title+year only, for
    `match_score.py`'s `SequenceMatcher` step to compare without attribute tokens
    skewing a purely textual similarity ratio.
    """
    _, spans = _find_vocabulary_matches(value)
    _, group_span = _find_release_group(value, spans)
    if group_span is not None:
        spans.append(group_span)
    stripped_chars = list(value)
    for start, end in spans:
        for index in range(start, end):
            stripped_chars[index] = " "
    return normalize_release_text("".join(stripped_chars))


def _find_vocabulary_matches(value: str) -> tuple[dict[str, str], list[tuple[int, int]]]:
    """Every vocabulary attribute found in `value`, alongside the `(start, end)` span
    of each match — release-group detection and token-stripping both need the spans,
    not just the matched values.
    """
    matches: dict[str, str] = {}
    spans: list[tuple[int, int]] = []
    for field, pattern in _VOCABULARY_PATTERNS.items():
        found = None
        for match in pattern.finditer(value):
            found = match
        if found is None:
            continue
        matches[field] = found.group(1).lower()
        spans.append(found.span())
    return matches, spans


def _find_release_group(
    value: str, vocabulary_spans: list[tuple[int, int]]
) -> tuple[str | None, tuple[int, int] | None]:
    if not vocabulary_spans:
        return None, None
    last_end = max(end for _, end in vocabulary_spans)
    trailing = value[last_end:]
    group_match = _GROUP_PATTERN.match(trailing)
    if group_match is None:
        return None, None
    group_span = (last_end + group_match.start(), last_end + group_match.end())
    return group_match.group(1), group_span
