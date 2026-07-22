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

OpenSubtitles also has three extra options once search is built — use hash-based matching,
and whether to include AI-translated or machine-translated results — saved from the edit form
today, not yet read by anything.

## Known gap (deferred)

Registration doesn't search or download anything yet — there's no `SubtitleProvider` client,
no match scoring, and nothing wired into subtitle discovery or translation. That's future work
building on top of this registration list.
