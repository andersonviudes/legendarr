# Commit message convention

Conventional Commits (`AGENTS.md`), with the exact shape this repo's history actually uses:

- `type(scope): summary` — imperative mood, lowercase after the colon, no trailing period
  (e.g. `feat(subtitle-acquisition): wire up Subsource search and download`).
- `scope` is the vertical slice/module the change lives in (`media-library`,
  `subtitle-translation`, `authentication`, ...), matching its folder name under
  `src/backend`/`src/web` — not a generic layer name. Use `web` (no more specific scope)
  for changes that span the UI shell rather than one slice. Omit the scope entirely only
  for changes that don't belong to a single module (e.g. `feat: cascade Arr webhook
  imports through discovery, acquisition, and translation`).
- If the change implements a `ROADMAP.md` milestone, append `(ROADMAP x.y.z)` right after
  the summary: `feat(media-server-integration): notify Plex/Jellyfin after a subtitle is
  written (ROADMAP 0.18.0)`.
- Don't hand-type a `(#NN)` PR suffix — GitHub adds it automatically on squash-merge into
  `main`. A `fix:`/`docs:`/`chore:` commit pushed straight to `main` (see
  `commit-rules-with-feature.md`) never gets one, since it skips the PR step.
