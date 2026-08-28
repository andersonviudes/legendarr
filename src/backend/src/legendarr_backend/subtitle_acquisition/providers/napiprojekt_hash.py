"""Napiprojekt's own hashing scheme: an MD5 of a file's first 10MB, plus a second
"subhash" derived from it — both required by `NapiprojektProvider`'s search/download
request. Ported from Bazarr's confirmed-working reference (`hash_napiprojekt`,
`/home/viudes/projects/bazarr/custom_libs/subliminal/utils.py:60-71`, and `get_subhash`,
`/home/viudes/projects/bazarr/custom_libs/subliminal/providers/napiprojekt.py:16-37`) —
unrelated to `opensubtitles_hash.py`'s algorithm despite the similar shape.
"""

import hashlib
from pathlib import Path

_READ_SIZE = 1024 * 1024 * 10

# Fixed index/multiplier/addend triples the subhash derivation walks over — Napiprojekt's
# own scheme, not derived from anything else.
_SUBHASH_INDEXES = (0xE, 0x3, 0x6, 0x8, 0x2)
_SUBHASH_MULTIPLIERS = (2, 2, 5, 4, 3)
_SUBHASH_ADDENDS = (0, 0xD, 0x10, 0xB, 0x5)


def compute_napiprojekt_hash(path: Path) -> str:
    """MD5 hex digest of the first 10MB of the file at `path` — works for any file
    size, unlike `opensubtitles_hash.compute_opensubtitles_hash`'s 64KB minimum."""
    with path.open("rb") as file:
        data = file.read(_READ_SIZE)
    return hashlib.md5(data).hexdigest()


def napiprojekt_subhash(napiprojekt_hash: str) -> str:
    """The second hash Napiprojekt's API expects alongside the main hash, derived from
    it by picking one hex digit per `_SUBHASH_INDEXES` entry as an offset into the hash
    itself, then scaling that digit pair by `_SUBHASH_MULTIPLIERS`/`_SUBHASH_ADDENDS`."""
    digits = []
    for index, multiplier, addend in zip(
        _SUBHASH_INDEXES, _SUBHASH_MULTIPLIERS, _SUBHASH_ADDENDS, strict=True
    ):
        offset = addend + int(napiprojekt_hash[index], 16)
        value = int(napiprojekt_hash[offset : offset + 2], 16)
        digits.append(f"{value * multiplier:x}"[-1])
    return "".join(digits)
