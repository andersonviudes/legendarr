# Subtitle Acquisition

Before legendarr can translate a subtitle it doesn't already have, it needs somewhere to get
one from. This page covers the first step: registering which subtitle-provider sites
legendarr is allowed to use, and confirming their credentials work.

## Provider registration

Settings → Subtitle Providers lists a fixed catalog of thirteen general-purpose subtitle
sources — OpenSubtitles, Addic7ed, YIFY Subtitles, Subdl, TVsubtitles, legendas.net,
Napiprojekt, Subsource, Anime Tosho, Supersubtitles, AnimeKalesi, GreekSubtitles, and
BetaSeries. Each one can be enabled or disabled, and configured with the credential it needs
(an API key, a username/password pair, or none at all, depending on the provider).

"Test connection" runs a lightweight check per provider — for five of the six with a real API
key or login (OpenSubtitles, Subdl, legendas.net, Addic7ed, BetaSeries), it validates the
credential against the provider's own service; for a provider with no credential (YIFY
Subtitles, TVsubtitles, Napiprojekt, Anime Tosho, Supersubtitles, AnimeKalesi, GreekSubtitles),
it only confirms the site is reachable. Subsource is the exception: it needs an API key like
the others, but its API docs are Cloudflare-protected, so its "test connection" is
reachability-only too — the key itself isn't validated yet.

OpenSubtitles also has three extra search options: hash-based matching (`use_hash`), and
whether to include AI-translated or machine-translated results — see below, this is the
feature that reads them.

## Search and download

OpenSubtitles is the one provider kind with a real `SubtitleProvider` implementation so far
(`subtitle_acquisition/providers/opensubtitles.py`) — the rest of the catalog stays
registration-only until 0.11.0 adds a second and third. `acquire_subtitle_for_media_file`
(`subtitle_acquisition/acquire_media_file_subtitle.py`) is the entry point: given a
`MediaFile` that has no subtitle yet in any of its `LanguageProfile`'s source languages, it
searches each source language in priority order, downloads the best-scoring result, writes it
next to the video (`{video}.{language}.srt`), and re-scans so it shows up as a normal external
subtitle. It's callable ad-hoc via `subtitle_acquisition/jobs.py`
(`enqueue_acquisition`/`enqueue_full_acquisition_scan`, same shape as
`subtitle_translation/jobs.py`) — nothing schedules it automatically yet (0.10.0), and
`translate_media_file` still doesn't fall back to it on a missing source subtitle: that
automatic, unified strategy is explicitly 0.11.0/0.12.0 roadmap work, not this.

Search precision differs by media type:

- **Movies** search OpenSubtitles by `imdb_id` — a precise, single-title lookup.
- **Series** search by title only. A `MediaFile` doesn't carry its episode's season/episode
  number (only `Series`-level data is synced today), so there's no way to anchor the search to
  one specific episode. This is a known limitation: title-only results can include subtitles
  for other episodes of the same show, and the match-score cutoff below is what keeps a
  clearly-wrong one from being accepted, not a substitute for real per-episode search.
- Either kind additionally gets `moviehash` search when `use_hash` is enabled on the provider
  and the local video is at least 64KB — the OpenSubtitles-defined checksum of a file's first
  and last 64KB, the most precise signal available since it doesn't depend on any metadata at
  all (`subtitle_acquisition/opensubtitles_hash.py`).

A result is only accepted once it clears a basic match-score cutoff
(`subtitle_acquisition/match_score.py`): a text-similarity ratio between the candidate's
release name and the local video's filename. This is deliberately simple — full per-attribute
weighting (release group, resolution, codec, source, edition) instead of one flat cutoff is
0.12.0 work.

## Known gap (deferred)

Manual search/browse and upload — letting a user pick a result themselves instead of trusting
the automatic match — is 0.11.0 work. A second and third real `SubtitleProvider`
implementation (beyond OpenSubtitles) is also 0.11.0.
