"""Allow/deny release-name filtering — ROADMAP 0.12.0's per-profile must-contain/
must-not-contain filters, same OR/OR semantics as a Radarr/Sonarr Release Profile.
"""


def passes_release_name_filters(
    release_name: str, must_contain: list[str], must_not_contain: list[str]
) -> bool:
    """`False` if `must_contain` is non-empty and `release_name` contains none of its
    terms, or if it contains any `must_not_contain` term — `True` otherwise, including
    when both lists are empty. Matching is a case-insensitive substring check, same as
    a Release Profile's "Must Contain"/"Must Not Contain" term lists.
    """
    normalized = release_name.lower()
    if must_contain and not any(term.lower() in normalized for term in must_contain):
        return False
    if any(term.lower() in normalized for term in must_not_contain):
        return False
    return True
