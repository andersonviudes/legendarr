---
name: legendarr web UI design system
description: legendarr_web's dark theme, sidebar nav shell, and poster-grid component — what exists, why, and how it was verified
type: project
---

Built 2026-07-15, completing the "Dashboard & UI" bullet of `ROADMAP.md` 0.1.0 (see
`refactored-wibbling-glacier.md` under `.claudin/plans/` for the earlier Pico.css/icon-vendoring
step this follows). The framework-only step (Pico v2 classless build vendored at
`static/vendor/pico.min.css`, Lucide SVGs vendored at `static/icons/`) was already done; this
step added the actual nav shell, which that plan explicitly deferred as "a separate follow-up
task".

**Layout** (`templates/base.html`, promoted out of `shared_kernel/` to the module's top
level 2026-07-16, see `legendarr-architecture.md`): a persistent left sidebar (`<aside
class="app-sidebar">` — brand link + `<nav>`) and a right-side `<main class="app-main">`
content area, styled in `static/styles.css`. Matches the requested Sonarr/Radarr convention:
sidebar always visible, active item highlighted via `aria-current="page"` (computed inline in
`base.html` from `request.url.path`, no per-route context var needed). Per-page `<nav>`/"Back"
links were removed from `dashboard.html` and the settings page since the sidebar supersedes
them.

**Nav structure (as of 2026-07-15, Bazarr-style, updated same day with a Dashboard item — see
below)**: the sidebar nav is, in order: a plain `<ul>` with a single "Dashboard" link (`/`), a
collapsible toggle `<button class="app-nav-toggle" aria-expanded=... aria-controls="nav-library">Library<chevron></button>`,
a `<ul id="nav-library" class="app-nav-submenu">` with Movies/Series (indented, `hidden` unless
expanded), then a plain `<ul>` with History/Settings/System. Routes: `/media/movies` and `/media/series` (split
out of the old combined `/media/` page — `media_library` slice, one router with two `GET`s, two
templates `movies.html`/`series.html`, each showing just its own poster grid), `/history/` and
`/system/` (new slices `history/` and `system/`, placeholder pages only — no backend domain for
either exists yet), and `/settings/` (the existing `language_profiles` slice — its capability
name didn't change, only its router's `prefix` moved from `/language-profiles` to `/settings`,
since Language profiles is currently the only setting and Bazarr nests language-profile config
under Settings). If Settings grows more sections later, it'll need real sub-nav; for now it's a
single page. Icons added for this: `history`, `settings`, `server` (System), `tv` (Series),
`clapperboard` (Movies), `chevron-right` (submenu toggle indicator) — fetched from
`https://unpkg.com/lucide-static@1.24.0/icons/<name>.svg`
(same version already vendored) since this sandbox has outbound internet access; no local
lucide-static package was found.

**"Library" collapsible submenu (added same day, second follow-up round)**: the user found the
original always-visible Movies/Series pair "misaligned"/not tree-like and asked for tighter row
spacing, an indent for children, and click-to-expand. `Library` became a real `<button
type="button" class="app-nav-toggle">` (not a link — it doesn't navigate anywhere, just
toggles), server-rendered with `aria-expanded` computed from `request.url.path.startswith("/media")`
so it's auto-open when you're actually on a Movies/Series page and auto-closed elsewhere (this
app is server-rendered multi-page, not an SPA, so there is no client-side state to persist across
navigations — re-deriving expanded-state from the current route on every page load is the
deliberate, simplest-correct answer here, not a stopgap). `static/js/sidebar.js` (new — first
file in what had been an empty `static/js/` dir) does the actual click toggle: flips
`aria-expanded` and the submenu `<ul>`'s `hidden` attribute. It's loaded directly in
`base.html` (not through the per-page `{% block scripts %}` override documented in
`static/js/README.md`) because it's sidebar-wide, sitewide behavior, not a per-page concern —
`README.md` now calls out this one exception. The chevron rotates 90deg via
`.app-nav-toggle[aria-expanded="true"] svg { transform: rotate(90deg) }` — no JS-driven class
needed, the ARIA state IS the CSS state. Child rows get `.app-nav-submenu li a { padding-left:
2.15rem }` (vs the normal 0.9rem) to read as indented children. Row density was also tightened
across the whole sidebar per user request: `.app-sidebar li a` padding 0.65rem→0.5rem block,
`.app-sidebar ul` gap 0.25rem→0.1rem, `.app-sidebar ul + ul` margin-top 1rem→0.6rem.
**How to apply:** if Settings ever needs its own collapsible sub-items, copy this exact pattern
(button+aria-expanded+aria-controls+hidden ul), don't invent a second mechanism.

**Follow-up bug (same day, third round):** the first cut of the indent, `.app-nav-submenu li a
{ padding-left: 2.15rem }`, silently never applied — the user screenshotted it and Movies/Series
were still flush with History/Settings/System. Cause: it has the exact same specificity as
`.app-sidebar li a { padding: 0.5rem 0.9rem; ... }` (both are class+li+a), and the base rule is
declared *later* in `styles.css`, so on an equal-specificity tie the later rule wins and its
`padding` shorthand clobbered the earlier `padding-left` override. Fix: `.app-sidebar
.app-nav-submenu li a` (extra ancestor class bumps specificity so it wins regardless of source
order), declared after `.app-sidebar li a` for readability. **Lesson: two same-specificity rules
setting overlapping/shorthand-vs-longhand properties on the same element is a real, easy-to-miss
bug class in this file — when adding a narrower override for one nav variant, always give it
higher specificity than the general rule, don't rely on source order.**

**Dashboard page (added same day, fourth round)**: the user asked for a "Dashboard" menu with
statistics and something visible "in real time". `dashboard/router.py` (`GET /`) now returns
three real, non-fabricated numbers — deliberately not the movies/series counts, since
`media_library/router.py` still hardcodes `movies=[]`/`series=[]` (nothing persisted yet, that's
ROADMAP 0.2.0) and showing a live Radarr/Sonarr count would mean a new network call with its own
error-handling story that wasn't asked for:
- language profile count via `list_language_profiles(session)` (`legendarr_backend.language_profiles.manage_language_profile`, same call `/settings/` already uses),
- minutes until the next scheduled library sync, and
- the configured sync interval (`settings.sync_interval_minutes`).

The "next sync" number requires reading the live `BackgroundScheduler` from a route, which wasn't
possible before — `scheduler` was a local variable inside `modules/web/src/legendarr_web/app.py`'s
`lifespan`, never attached anywhere reachable. Fixed with a one-line `app.state.scheduler =
scheduler` right after `scheduler.start()`; the router reads `request.app.state.scheduler.get_jobs()[0].next_run_time`
and subtracts `datetime.now(tz)` to get whole minutes remaining. `TestClient(create_app())` used
`with ... as client:` already (runs lifespan for real), so no test mocking was needed.

**Update (rebased onto `main` after the bootstrap-module split, PR #5):** the scheduler/next-sync
and sync-interval numbers described above no longer exist in `dashboard/router.py`. The bootstrap
split (`feat: add bootstrap module, split backend API from web`) moved DB/scheduler access out of
`legendarr_web` entirely — the web module now only reaches the backend through
`legendarr_web.backend_client.client` (an HTTP call to the API app), which has no endpoint
exposing scheduler state. `dashboard/router.py` was rewritten during the rebase to fetch
`profile_count` the same way `/settings/` does (via `service.list_language_profiles(client)`), and
`sync_interval_minutes`/`next_sync_minutes` are passed as `None` (the template already renders
`—` for `None`). Restoring the live sync countdown would need a small backend API endpoint
exposing scheduler status first — that's a follow-up, not done in PR #5.

"Real time" is delivered with **htmx** (mentioned in the architecture docs as the intended stack
but never actually vendored or used until now) — vendored at `static/vendor/htmx.min.js`
(`https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js`, same vendor-don't-CDN reasoning as
Pico/Lucide) and loaded unconditionally in `base.html`'s `<head>` (available sitewide for future
use, not just the dashboard). The stats block re-fetches itself via `hx-get="/" hx-select="#dashboard-stats"
hx-target="this" hx-swap="outerHTML" hx-trigger="every 15s"` — no separate JSON/partial endpoint
needed, htmx just re-requests the existing full page and extracts the one element by selector.
Verified this isn't just decorative markup: Puppeteer with a `page.on('request', ...)` listener
counted exactly 2 requests to `/` after 17s of waiting (1 initial + 1 poll), confirming the
polling loop actually fires end-to-end, not just "renders the right attributes".
`static/icons/layout-dashboard.svg` was vendored (same lucide-static v1.24.0) for the nav entry.
**How to apply:** if another page needs a live-updating fragment, copy the self-select htmx
pattern above rather than building a dedicated JSON endpoint — it's less code for same-page data.
Do not add movies/series counts to the dashboard until `sync_media_library` actually persists
something (0.2.0) — a live per-request Radarr/Sonarr call was deliberately out of scope here.

**Sidebar footer: theme toggle + GitHub link (added same day, fifth round)**: the user pasted a
reference screenshot (a divider line, then a gold sun icon and a coral heart icon side by side at
the bottom of a dark sidebar) and asked to replicate it, with the sun switching the theme "for
now" (their words implied a deliberately rough/temporary toggle, not a full light-theme design
pass). Implementation: `<footer class="app-sidebar-footer">` inside `.app-sidebar`, placed after
`<nav>`; `.app-sidebar` is already `display:flex; flex-direction:column`, so `margin-top: auto`
on the footer pushes it to the bottom for free, no extra layout code needed. Two icon buttons,
both `.app-icon-btn` (an unstyled 2rem square, `all: unset` base): `#theme-toggle` (a `<button>`,
not a link — it doesn't navigate) is a **static** sun icon that never swaps to a moon on click —
deliberately matching the plain static icon in the reference rather than adding icon-swap
"current state" polish that wasn't shown or asked for. The heart is an `<a>` to
`https://github.com/andersonviudes/legendarr` (this project's real, confirmed-from-`git remote
-v` GitHub URL — deliberately not a fabricated `/sponsors/...` URL, since GitHub Sponsors isn't
known to be set up for this repo) with `aria-label="Support legendarr on GitHub"`,
`target="_blank" rel="noopener"`. Colors: sun reuses the existing `--pico-primary` gold (no new
color introduced); heart gets one new, one-off color `#e0707c` (coral) to match the reference —
the only new hardcoded color added, everything else in this pass reuses existing tokens.

Toggle mechanics live in `static/js/theme.js` (third sitewide script loaded directly in
`base.html`, not per-page — `static/js/README.md` updated to name it alongside `sidebar.js`):
flips `document.documentElement`'s `data-theme` attribute between `"dark"`/`"light"` and persists
the choice to `localStorage["legendarr-theme"]`. A tiny inline `<script>` was added as the very
first thing in `base.html`'s `<head>` (before both stylesheet `<link>`s) that reads that same
`localStorage` key and re-applies it to `<html>` before first paint — without this, a saved
"light" preference would flash dark on every reload before the deferred `theme.js` ran. Verified
both the click-toggle and the reload-persistence with Puppeteer
(`page.click('#theme-toggle')` → attribute flips synchronously; `page.reload()` → attribute is
still `"light"`, confirming the anti-flash script actually re-reads storage, not just the
in-memory toggle). **Only `[data-theme="dark"]` has custom palette overrides in `styles.css`
(see Theme section below) — switching to `"light"` currently falls all the way back to Pico's
stock light theme (white background, blue primary), with zero custom-branding overrides.** This
is the literal, intended state of "só por enquanto" (temporary/rough for now) per the user's own
framing — if a proper on-brand light palette is ever requested, it needs a new `[data-theme="light"]`
block mirroring the dark one, not a fix to this toggle mechanism itself.

**Theme**: dark neutral-graphite palette with a muted gold accent (`#c9974f`) overriding Pico's
default blue via `[data-theme="dark"]` CSS custom properties in `styles.css`. No webfont
vendored (deliberately — app is meant to run without container internet egress, same reasoning
as the pico/CDN decision). This went through a second design pass on 2026-07-15 after the user
called the first version "esquisito" (off/weird) and asked for something more elegant and
professional: the initial cut had a fully-saturated amber (`#e8b34a`), a solid-filled active-nav
pill, an amber-tinted brand-icon badge, uppercase/letter-spaced nav labels, and a decorative
repeating-gradient "sprocket tick" strip down the sidebar's edge. All of that was walked back —
current state is sentence-case nav labels (no letter-spacing), a neutral (not accent-tinted)
brand-icon badge, no sprocket decoration, and an active nav item indicated by **text color
only** (`.app-sidebar li a[aria-current="page"] { color: var(--pico-primary); }`, no
background/box-shadow at all — the user explicitly asked to strip the tinted-background +
left-bar treatment down to just the color change). Sidebar nav font-size is `0.8rem` (down from
an initial `0.9rem`, per user request to shrink it). **Lesson for future styling requests in
this project:** this user's taste runs toward restrained/understated — prefer subtle, sparing
accent color and plain text-based state indicators over solid fills, saturated color blocks, or
decorative flourishes, and check with a screenshot before assuming a bolder treatment lands well.

**Poster grid** (`movies.html`/`series.html`, `.poster-grid`/`.poster-card`/`.poster-art` in
`styles.css`): renders `movies`/`series` as Sonarr/Radarr-style cards, but only using fields
that actually exist today (`MediaFile`/`SeriesFile` have only `id`/`title`/`path` —
`sync_media_library()` doesn't persist synced media yet, that's ROADMAP 0.2.0). Every card
shows the vendored `image-off` icon as a placeholder — there's no poster art, monitored
status, episode counts, or quality-profile field to show yet, and none were fabricated.

**Why:** avoids re-explaining the nav-shell/theme decisions or re-deriving that the poster
grid intentionally omits Sonarr-style badges (episode counts, monitored flag, quality
profile) — those need real persisted fields, not this UI pass.

**How to apply:** when adding a new top-level page, extend `base.html` and add its link to the
sidebar `<nav>` (icon + label, matching the existing entries, in whichever of the two `<ul>`
groups fits) rather than inventing a
per-page nav. When Movie/Series gain more persisted fields (0.2.0+), extend `.poster-card`
rather than replacing it. Verification note: this sandbox has no `chromium-cli`/Playwright, but
`/usr/bin/chromium` exists — `chromium --headless --disable-gpu --no-sandbox --screenshot=out.png
--window-size=1600,1000 <url>` is a working fallback for one-shot screenshots without a CDP
driver. **The MCP playwright browser tools (`mcp__playwright__browser_*`) do NOT work here** —
they error `Chromium distribution 'chrome' is not found at /opt/google/chrome/chrome`. For
anything needing DOM/computed-style reads or click interaction (not just a screenshot), write a
standalone node script instead: `npx playwright`'s `chromium.launch({executablePath:
'/usr/bin/chromium'})` (used this session to reproduce a Test-button click and read
`#test-result` innerHTML + `getComputedStyle` visibility) or the `puppeteer-core` variant noted
below — both drive `/usr/bin/chromium` directly.

**Pico.css gotchas hit while building this sidebar** (non-obvious, cost real debugging time —
check for these first if the sidebar nav ever looks subtly wrong again):
- Pico sets `nav ul { align-items: center }`. Our sidebar nav is a flex column
  (`.app-sidebar ul { flex-direction: column }`), so on the cross axis (horizontal) that rule
  centers every `<li>` instead of stretching it full-width — the nav items end up indented and
  misaligned with the brand logo above. Fix: `.app-sidebar ul` must explicitly set
  `align-items: stretch`.
- Pico sets `ul li { list-style: square }` directly on the `<li>` element. Setting
  `list-style: none` only on the parent `<ul>` (e.g. `.profile-list`) does not remove a visible
  bullet, because Pico's rule targets the `<li>` itself and a same-element rule always beats an
  inherited value from the parent regardless of the parent selector's specificity. Fix:
  `list-style: none` must be set on the `li` rule itself (e.g. `.profile-list li`).
- Pico sets `nav { justify-content: space-between }`. Once the sidebar `<nav>` itself became a
  flex column (needed to stack the "Library" label + two `<ul>` groups), that rule spread the
  label and both `<ul>`s apart to fill the sidebar's full height instead of stacking them at the
  top — looked like a huge blank gap under "Library". Fix: `.app-sidebar nav` must explicitly
  set `justify-content: flex-start`. General lesson: whenever a new `display: flex` is added to
  an element Pico already targets, explicitly set both `justify-content` and `align-items` —
  don't assume "unset" means browser-default, Pico's classless rules fill in the unset ones.
- Pico sets `nav ul:first-of-type { margin-left: calc(var(--pico-nav-element-spacing-horizontal)
  * -1) }` and the mirror `:last-of-type { margin-right: ... }` — meant to flush a horizontal
  navbar's first/last link group against the nav's own edges. With two stacked vertical `<ul>`s
  in a column nav, this silently shifted the *first* `<ul>` (Movies/Series) ~10px left of the
  second (History/Settings/System), and Pico's separate `nav li :where(a){ margin: ... * -1 }`
  trick (canceled by that link's own padding in a normal horizontal navbar) did the same to
  every `<a>` — so icons/text didn't line up with the plain `<p class="app-nav-label">` heading
  above them either, even though both used the same `0.9rem` inset in our CSS. Confirmed via
  Puppeteer (`getBoundingClientRect`/`getComputedStyle`, no MCP driver needed — `npm install
  puppeteer-core` + `puppeteer.launch({executablePath: '/usr/bin/chromium', headless: 'new',
  args: ['--no-sandbox']})` works standalone) since pixel-diffing screenshots alone couldn't
  distinguish "real CSS bug" from "icons just have different glyph ink". Fix: reset both —
  `.app-sidebar nav ul:first-of-type, .app-sidebar nav ul:last-of-type { margin-left: 0;
  margin-right: 0; }` (specificity (0,2,2) beats Pico's (0,1,2)) and `margin: 0;` directly on
  `.app-sidebar li a` (Pico's version uses `:where()` there, which carries zero specificity, so
  a plain classed selector already wins). General lesson: Pico's nav rules assume a *horizontal*
  navbar and lean on paired negative-margin/padding tricks for edge-flushing; turning `<nav>`
  into a vertical stack requires auditing every margin Pico sets on `nav`, `nav ul`, and `nav li
  a`, not just `align-items`/`justify-content`.

**Update (2026-07-16, sixth round — sidebar polish pass, PR #10 `feat/arr-services-settings`):**
several small follow-up tweaks, each driven by a reference screenshot and shipped as its own
commit:
- Top-level "Library" and "Settings" `<button class="app-nav-toggle">` items got leading icons
  (`library`/`settings`) — they'd shipped icon-less while the `<a>` items always had one.
  `.app-nav-toggle` switched from `justify-content: space-between` to `gap: 0.75rem` +
  `margin-left: auto` on the trailing chevron (`svg:last-child`) to fit 3 children (icon, label,
  chevron) instead of 2; the `[aria-expanded="true"] svg` rotate rule also had to be scoped to
  `svg:last-child`, or it rotated the new leading icon too.
- All structural borders were removed from the sidebar per user request (`.app-sidebar`'s right
  border, `.app-brand`'s bottom border, `.app-sidebar-footer`'s top border), and `.app-sidebar`'s
  background was then unified to `var(--pico-background-color)` (same as `.app-main`).
  **The two-tone/bordered sidebar described earlier in this file (2026-07-15 build —
  `--lg-sidebar-background-color: #2a2a2a` nav area vs. header/footer bands, plus a right border)
  no longer exists; that CSS variable was deleted. The current sidebar is one flat background
  color with no dividing borders at all.**
- New per-slice nav count badge pattern (`.app-nav-badge`, gold pill: `var(--pico-primary)` text
  on `var(--lg-primary-dim-background-color)`): "Arr Services" shows how many Radarr/Sonarr
  connections are registered. Implemented as `GET /settings/arr-services/count`
  (`arr_services/router.py`) returning a small partial (`_count_badge.html`); `base.html` renders
  an empty placeholder `<span hx-get=... hx-trigger="load" hx-swap="outerHTML">` next to the
  link. Chosen over threading a count through every router's template context, so the count stays
  owned by the `arr_services` slice (VSA) instead of leaking into unrelated routers
  (dashboard/history/system/language_profiles). **htmx gotcha:** the swapped-in partial must NOT
  itself carry `hx-get`/`hx-trigger="load"` — if it does, every swap re-triggers its own load,
  causing an infinite refetch loop. The trigger lives only on the `base.html` placeholder; the
  server-rendered partial response is static markup.
- Sidebar nav font-size and icon size (icons are `1em`, so they scale with the element's
  font-size) were bumped ~1px per user request. **The "uniform 0.8rem" font-size claimed in the
  Theme section above is stale** — `.app-sidebar li a` and `.app-nav-toggle` have always had two
  different font-sizes (regular nav links vs. the Library/Settings toggle buttons), not one
  shared value; check current `styles.css` rather than trusting that old number.

**Dev-server restart gotcha (updated 2026-07-16 for the bootstrap split):** `make run` is now
`uv run --package legendarr-bootstrap python -m legendarr_bootstrap` (the old `legendarr_web`
entrypoint below is pre-split — the process to look for is `legendarr_bootstrap`, not
`legendarr_web`). It does NOT hot-reload: **Jinja template edits show up live per-request, but
Python/router edits do NOT take effect until the process is restarted.** Re-running a
curl/browser check against unrestarted code silently exercises the OLD behavior — this bit a
live-verification pass this session (a create succeeded without the just-added connection check
because the pre-edit code was still serving). `ps aux | grep legendarr_bootstrap` shows both a
`make run` wrapper PID and the real `uv run ... python -m legendarr_bootstrap` child; `pkill -f
legendarr_bootstrap` reliably stops the real server (killing only the captured wrapper/background
PID leaves it running). Relaunch detached with `nohup make run > /tmp/legendarr-run.log 2>&1 &
disown`, then poll `curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/...` until it
returns 200 (the app runs Alembic migrations on startup, so give it ~8s).

**Sandbox caveat (seen 2026-07-16, PR #10):** in some sessions the harness reaps any
backgrounded `make run` almost immediately — every launch call returns `Exit code 144`
(128+16, SIGSTKFLT to the process group) and the server never binds the port (empty log, no
`legendarr_bootstrap` process). `nohup`, `disown`, `setsid`, and Bash `run_in_background` all
failed the same way. When this happens, live-browser verification is simply unavailable that
session — fall back to the in-process render path (`fastapi.testclient.TestClient` against
`create_app()` with a `stub_backend_client` MockTransport) to assert rendered HTML, and lean
on the fact that CSS `var()` token swaps resolve to identical computed values. Earlier sessions
the same launch pattern worked, so it's environmental/flaky, not a code problem.
