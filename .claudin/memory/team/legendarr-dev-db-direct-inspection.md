---
name: legendarr-dev-db-direct-inspection
description: dev docker-compose's legendarr.db is bind-mounted to dev/legendarr-config/legendarr.db and queryable directly from the host with sqlite3, no container exec needed
type: reference
---

`docker-compose.dev.yml` bind-mounts `./dev/legendarr-config:/config`, so the live SQLite
DB the running dev container uses is readable straight from the host at
`dev/legendarr-config/legendarr.db` — `sqlite3 -readonly dev/legendarr-config/legendarr.db
"..."` works with no `docker exec` needed. Useful tables when diagnosing subtitle/
translation issues: `translationfailure` and `acquisitionfailure` (error messages +
timestamps), `translationattempt`/`subtitle` (what succeeded and how), `subtitleprovider
config`/`translationproviderconfig` (`enabled`/`connection_verified` per provider),
`languageprofile` (`source_languages`/`target_languages`, match scores).

**Why:** faster and more precise than grepping container logs — the failure tables capture
the exact provider error (e.g. a DeepL 403) instead of just "translation failed" in the
log stream. See [[legendarr-db-migrations]] for how the DB/config location is set up in
general, and [[legendarr-dev-deepl-key-broken]] for the specific issue this technique
uncovered.
