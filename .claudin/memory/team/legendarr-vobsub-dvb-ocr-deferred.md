---
name: legendarr vobsub dvb ocr deferred
description: VobSub/DVB bitmap subtitle OCR scoped out of ROADMAP 0.14.0 — no maintained library, needs its own from-scratch parser, not currently on the roadmap.
type: project
---

ROADMAP 0.14.0 ("Image-based embedded tracks (OCR)") only wires up PGS
(`hdmv_pgs_subtitle`, Blu-ray) — a hand-rolled `.sup` parser
(`subtitle_discovery/pgs_format.py`) plus per-cue Tesseract OCR
(`subtitle_discovery/ocr_embedded_subtitles.py`), gated by a dedicated
`LanguageProfile.ocr_embedded_subtitles` toggle. VobSub (`dvd_subtitle`, DVD
`.idx`/`.sub`) and DVB (`dvb_subtitle`) stay excluded from
`probe_embedded_subtitles.IMAGE_BASED_SUBTITLE_CODECS`, same as before — they
are not currently a roadmap item.

**Why:** researched during planning (2026-08-24) — no maintained,
pip-installable OCR library exists for VobSub comparable to `pgsrip` for PGS;
the realistic paths are a from-scratch `.idx`/`.sub` bitmap parser (a
different binary format than PGS, no code sharing) or vendor-building a C++
tool (`vobsub2srt`) from source. Doubling the parser work for a rarer,
older format wasn't worth bundling into the same PR as PGS support.

**How to apply:** if a user requests VobSub OCR, treat it as a new roadmap
item (not a 0.14.0 follow-up) — it needs its own binary-format parser design
pass, most likely mirroring `pgs_format.py`'s shape (pure parse/decode
module feeding the existing `ocr_embedded_subtitles.py` OCR orchestration).
