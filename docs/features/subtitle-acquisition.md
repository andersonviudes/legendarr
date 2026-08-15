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

Every one of the thirteen catalog kinds now has a real `SubtitleProvider` implementation
(`subtitle_acquisition/providers/opensubtitles.py`, `addic7ed.py`, `yify_subtitles.py`,
`subdl.py`, `tvsubtitles.py`, `legendas_net.py`, `napiprojekt.py`, `subsource.py`,
`animetosho.py`, `supersubtitles.py`, `animekalesi.py`, `greeksubtitles.py`, `betaseries.py`) —
0.6.0 is fully shipped. YIFY Subtitles and Subdl are both movies-only and need an `imdb_id` to
search (neither has a usable title-search path for this app's scope), so — like Addic7ed's
series case — a series search returns no results from either. TVsubtitles, AnimeKalesi, Anime
Tosho, and BetaSeries are the opposite: none has movie content, so each is skipped for a movie
or an unresolved episode and instead needs a real season/episode number to search — Anime
Tosho and BetaSeries additionally require `Series.tvdb_id` to resolve their own per-episode id
(an AniDB episode id and a BetaSeries episode id, respectively), while AnimeKalesi (Turkish
only) resolves the episode from its own scraped season/episode listing instead. legendas.net,
Subsource, and Supersubtitles all have real movie and TV content, searching by `imdb_id` for
a movie and by
season/episode for a series (neither means the search is skipped, same shape as
`LegendasNetProvider`); legendas.net is Brazilian Portuguese only, Supersubtitles is
Hungarian/English only. GreekSubtitles also has both movie and TV content, but with a single
search path (a season/episode suffix is just appended to the title query when both are
resolved) — Greek/English only, and only its first results page is fetched (no "Next"-page
pagination). Napiprojekt is different again: instead of a title search it hashes the local
video's own first 10MB (`subtitle_acquisition/napiprojekt_hash.py`) and asks for an exact
match — Polish only, and it applies equally to a movie or a series file since nothing but the
hash is used. `acquire_subtitle_for_media_file`
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
  `relative_path` against the `MediaFile`), `None` when it can't be resolved. TVsubtitles,
  legendas.net, Subsource, Supersubtitles, AnimeKalesi, GreekSubtitles, Anime Tosho, and
  BetaSeries all anchor their series search on it; the remaining providers still ignore it
  and search by title only, so title-only results from those can include subtitles for other
  episodes of the same show, and the match-score cutoff below is what keeps a clearly-wrong
  one from being accepted for them, not a substitute for real per-episode search.
- Either kind additionally gets `moviehash` search when `use_hash` is enabled on the provider
  and the local video is at least 64KB — the OpenSubtitles-defined checksum of a file's first
  and last 64KB, the most precise signal available since it doesn't depend on any metadata at
  all (`subtitle_acquisition/opensubtitles_hash.py`).
- The local video's path is also passed to every provider's `search()` as `video_path` — every
  provider but Napiprojekt ignores it. Napiprojekt's result sets its `release_name` to the
  video's own filename, so the match-score cutoff below trivially accepts it: an exact hash
  match is definitionally the right subtitle for that file, and the API returns no other
  metadata to score against.

A result is only accepted once it clears a basic match-score cutoff
(`subtitle_acquisition/match_score.py`): a text-similarity ratio between the candidate's
release name and the local video's filename. This is deliberately simple — full per-attribute
weighting (release group, resolution, codec, source, edition) instead of one flat cutoff is
0.12.0 work.

## Known gap (deferred)

Manual search/browse and upload — letting a user pick a result themselves instead of trusting
the automatic match — is 0.11.0 work.
