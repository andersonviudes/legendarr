---
name: legendarr-animetosho-anidb-key
description: Whether Anime Tosho subtitle search genuinely needs an AniDB API key — confirmed against Bazarr source and web research, plus an untaken no-auth alternative
type: project
---

legendarr's `AnimeToshoProvider` (`subtitle_acquisition/providers/animetosho.py`) requires
`SubtitleProviderConfig.api_key` to hold an AniDB HTTP API client name, because it resolves
TVDB series/season/episode → AniDB anime id (via the free community `anime-lists` XML) → AniDB
episode id (`eid`) via a real authenticated call to `api.anidb.net:9001/httpapi` — only that
last step needs the key. Ported from Bazarr, whose own `AnimeToshoProvider` class takes no API
key (it only calls `feed.animetosho.org?eid=`), but Bazarr externalizes AniDB resolution into a
separate global refiner (`bazarr/subtitles/refiners/anidb.py`) gated the same way: no API
credentials means `series_anidb_episode_id` stays `None` and Anime Tosho search returns nothing
(`providers_requiring_anidb_api = {'animetosho'}` in that file). Confirmed 2026-08-27 by reading
the local Bazarr checkout (`/home/viudes/projects/bazarr`) and web research on Anime Tosho's own
API — the requirement is real in both codebases, not a legendarr-specific bug.

**Untaken alternative, still open as of 2026-08-27:** `feed.animetosho.org`'s API is fully
public and also supports `q=` (free-text title search) and `aid=` (AniDB anime id, client-side
episode filtering) — neither needs any AniDB credential. legendarr could make the API key
optional by falling back to one of those, trading exact-episode precision for no-auth search.
No decision has been made on building that fallback.

**Why:** the user asked to revert the UI hint explaining this requirement, believing it was
wrong ("anime tosho eh free" / doesn't need an api-key) — investigation showed the hint was
accurate for the current `eid=`-based implementation, so the original fix's premise holds; see
[[legendarr-branch-convention]] for how the revert itself was handled.

**How to apply:** if asked to make animetosho's API key optional, the `q=`/`aid=` fallback above
is the concrete path — no need to re-research Anime Tosho's API. If the "AniDB key required"
premise is questioned again, it's already confirmed against both Bazarr's source and Anime
Tosho's own API; only revisit if the implementation itself changes.
