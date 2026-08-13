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

OpenSubtitles, Addic7ed, YIFY Subtitles, Subdl, TVsubtitles, and legendas.net are the provider
kinds with a real `SubtitleProvider` implementation so far
(`subtitle_acquisition/providers/opensubtitles.py`, `addic7ed.py`, `yify_subtitles.py`,
`subdl.py`, `tvsubtitles.py`, `legendas_net.py`) — the rest of the catalog stays
registration-only until the remaining 0.6.0 bullets land. YIFY Subtitles and Subdl are both
movies-only and need an `imdb_id` to search (neither has a usable title-search path for this
app's scope), so — like Addic7ed's series case — a series search returns no results from
either. TVsubtitles is the opposite: it has no movie content at all, so it's the first
provider that needs a real season/episode number to search and is skipped for a movie or an
unresolved episode instead. legendas.net has both movie and TV content with a real
season/episode search for the latter, but is Brazilian Portuguese only — a search for any
other language returns no results. `acquire_subtitle_for_media_file`
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
- **Series** also get a real season/episode number now — resolved via
  `media_library.locate.resolve_media_file_episode` (a live Sonarr call, matched by
  `relative_path` against the `MediaFile`), `None` when it can't be resolved. TVsubtitles is
  the only provider that actually anchors its search on it today; every other provider still
  ignores it and searches by title only, so title-only results from those can include
  subtitles for other episodes of the same show, and the match-score cutoff below is what
  keeps a clearly-wrong one from being accepted for them, not a substitute for real
  per-episode search.
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
the automatic match — is 0.11.0 work. The remaining real `SubtitleProvider` implementations
(beyond OpenSubtitles, Addic7ed, YIFY Subtitles, Subdl, TVsubtitles, and legendas.net) are
0.6.0 work.
