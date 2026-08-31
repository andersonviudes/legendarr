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
Dashboard movies/series counts were blocked on `sync_media_library` persisting something —
that landed 2026-07-20 (PR #12: `Movie`/`Series` tables, per-connection sync), so counts
from the DB are now unblocked (a live per-request Radarr/Sonarr call is still out of scope).

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

**Form-control specificity gotcha (2026-07-20, language-profile tag multiselect, PR
#13-ish `feat/language-profile-crud`):** the custom `.lang-multiselect-search` input (part of
a tag-multiselect widget replacing free-text language fields) rendered visibly taller/shorter
than plain Pico inputs no matter what padding/line-height was set on the lone class. Cause:
Pico's own rule is `input:not([type=checkbox],[type=radio],[type=range],...)`, and a
`:not()` chain of attribute selectors out-specifies a single class selector — so the class-only
override never won. Fix pattern: scope the override with an extra ancestor class, e.g.
`.lang-multiselect-control .lang-multiselect-search { ... }`, not `.lang-multiselect-search`
alone. **General lesson (extends the nav-specificity gotchas above to form controls):** any
custom `<input>`-based widget in this app needs an ancestor-scoped selector to beat Pico's
`input:not(...)` rule — a bare class will silently lose.

Also on this widget: its container `.lang-multiselect-control`'s `min-height` is a **literal,
user-specified `38px`**, not a value derived from Pico's own input-height formula (`1rem *
line-height + spacing-vertical*2 + border-width*2`, which computes to 47.25px at this app's
pinned 18px root and would pixel-match plain text inputs exactly). An agent tried the
formula-derived value first; the user explicitly asked to replace it with a flat `38px`
instead, even though that leaves the control a few px shorter than sibling text inputs.
**How to apply:** if this field's height looks "wrong" again, don't reflexively re-derive
the Pico formula — check with the user first, since the current mismatch vs. plain inputs is
an intentional, explicit choice, not an unnoticed bug.

**Update (2026-07-21, seventh round — `.service-form` width + Sonarr-style page toolbar):**
two related fixes to the two full-form pages (`language_profile_form.html`,
`arr_service_form.html`), both driven by reference screenshots of Sonarr's UI.

1. `.service-form { max-width: 22rem }` (`styles.css`) left a huge empty gap on the right of
   wide viewports — `.app-main` itself is correctly `flex: 1` with no cap, the narrow width was
   purely the form's own hardcoded max-width. Bumped to `max-width: 36rem; width: 100%` (36rem
   chosen to stay close to `.stat-grid`'s existing `40rem`, avoiding an unreadably long input
   row on ultrawide screens rather than going fully fluid). No other page uses `.service-form`
   besides these two, so this was a single-rule fix. The only real responsive breakpoint in the
   app is still the pre-existing `@media (max-width: 48rem)` sidebar-stacking rule — nothing new
   was needed for mobile since `width: 100%` + `max-width` is inherently fluid down to any
   viewport.

2. New `.page-toolbar`/`.page-toolbar-btn` component: a Sonarr-style icon-over-label button row
   sitting between the `<h1>` and the `<form>`, replacing the old bottom-of-form `.form-actions`
   Save/Test buttons entirely (no page keeps both). Buttons live **outside** the `<form>` element
   and reconnect to it via the HTML `form="<form-id>"` attribute (`language-profile-form` /
   `arr-service-form` ids added to the two `<form>`s) so native submit still works. New vendored
   icons: `save.svg` (Save) and `plug-zap.svg` (arr-service Test), sourced the same way as
   documented in `legendarr-lucide-icon-source.md`.
   - **Pico specificity gotcha hit here, new one, not covered by the gotcha list above:** Pico
     sets a global `button[type=submit], input:not(...), select, textarea { width: 100% }`.
     This selector's specificity is `(0,1,1)` (element + attribute) — a plain class selector
     like `.page-toolbar-btn { width: auto }` is only `(0,1,0)` and **loses even though it's
     declared later in the file**, because specificity beats source order. Only the
     `type="submit"` Save button was affected (the `type="button"` Test button was fine, since
     no equivalent Pico rule targets `[type=button]`). Fix: qualify the override with the
     element too — `button.page-toolbar-btn { ... }` — matching Pico's `(0,1,1)` and then
     winning on source order (styles.css loads after pico.min.css). **General lesson: matching
     specificity isn't enough to guarantee a win by declaring the override "later" — check
     whether Pico's rule already includes an element-type selector (not just `:not()`
     exclusions) and mirror that in the override, not just add a class.**
   - Also had to rewire the arr-service "Test" button's htmx/JS now that it's no longer a DOM
     descendant of `<form>`: `hx-include="closest form"` → `hx-include="#arr-service-form"` (an
     ID selector, since `closest` can't reach a sibling), and `arr-service-form.js`'s
     `event.detail.elt.closest("form")` → `document.getElementById("arr-service-form")` for the
     same reason. **Lesson: any button moved out of a `<form>` and reconnected via `form="id"`
     for native submit purposes still needs every `closest("form")`/`hx-include="closest form"`
     reference (JS or htmx) updated to an explicit ID selector — the `form` attribute only wires
     up submission, not DOM ancestry.**
   - Verified end-to-end with Playwright (not just visual): clicked the toolbar Test button and
     got a real backend validation response ("The server rejected the API Key..."), and clicked
     both toolbar Save buttons and confirmed each redirected to its list page — confirms the
     `form="..."` wiring actually submits, not just renders correctly.
   - **Playwright/browser-cache gotcha hit while verifying:** repeated `page.goto()` calls to the
     same origin during one session can silently reuse a stale cached `styles.css` (Chromium's
     heuristic freshness caching keys off `Last-Modified`, so edits made *after* the first load
     in a session don't always trigger a real refetch). Screenshots showed stale (pre-fix)
     layout even though `curl`ing `/static/styles.css` directly confirmed the served file was
     already correct. Fix used to force a real refetch mid-session:
     `page.evaluate(() => { link.href = new URL(link.href); url.searchParams.set('v', Date.now()); ... })`
     (cache-bust the `<link>` href) before each screenshot. **Don't trust a Playwright screenshot
     that looks unchanged after a CSS edit without cache-busting first — verify against `curl`
     on the actual served file before concluding a fix didn't work.**

**Immediate follow-up, same round:** the user saw a screenshot of the toolbar-below-`<h1>`
layout above and asked to flip the order — toolbar first, then the divider line, then the
title ("coloca os botoes para cima do titulo... separa com uma linha"). Both templates now
render `<div class="page-toolbar">` before `<h1>`, not after. `.page-toolbar`'s `margin` lost
its `1.25rem` top value (was `1.25rem 0 1.75rem`, now `0 0 1.75rem`) since it's the first
element in `.app-main`'s content block and `.app-main` already has `padding: 3rem 3.5rem` —
keeping the old top margin would have doubled the gap above the buttons. **How to apply:** if
another form page adopts this toolbar, put it as literally the first thing after `{% block
content %}`, before the page's `<h1>`, matching this final layout — not the earlier
title-then-toolbar order this same round briefly shipped.

**Update (2026-07-21, eighth round — toast notifications, replacing the static inline
error banner and adding a save-success signal that didn't exist before):** the user asked to
standardize success/error/warning feedback as a bottom-right floating toast, rounded border,
auto-dismissing after 3s, green/red/yellow by type. Scope was deliberately limited to the two
real message-producing flows (create/update on `arr_service_form.html` and
`language_profile_form.html`) — the arr-service "Test connection" result (`_test_result.html`,
swapped into a persistent `#test-result` div under the toolbar) was **not** converted; that's
an intentionally lasting status the user is actively looking at while adjusting fields, and
turning it into a 3s-then-gone toast would be a UX regression, not an improvement.

- **New sitewide component**: `#toast-container` (`base.html`, `position: fixed` bottom-right,
  added once as a sibling of `.app-shell`) + `static/js/toast.js` (third sitewide-exception
  script alongside `sidebar.js`/`theme.js`, per `static/js/README.md`) + `.toast`/`.toast--success`
  `/--error`/`--warning` in `styles.css`. Pill shape via `border-radius: 999px`; color is
  border+text only (reusing `--pico-ins-color`/`--pico-del-color`, same as the pre-existing
  `.test-result--success`/`--error`, plus one new token `--lg-warn-color: #d9b23c` for the
  warning state — no wired warning trigger exists yet, added ready for future use per the
  user's own "quando houver" framing). `window.showToast(message, type)` is exposed globally
  so any future page script can call it directly, not just the two built-in triggers below.
- **The hard part: this app is PRG (POST-redirect-GET, see `router.py` in both slices) with no
  session/flash-cookie mechanism**, so a toast has to survive two different transports depending
  on whether the response is a redirect or a same-page re-render:
  - Same-page (4xx validation error, form re-rendered with the submitted values so the user can
    fix them): the old `<p class="test-result test-result--error">{{ error }}</p>` was replaced
    with a hidden `<div hidden data-toast-message="{{ error }}" data-toast-type="error"></div>`
    (same `hidden`-placeholder idiom as the `#arr-services-count-badge` span in `base.html`).
    `toast.js` finds it on load, fires the toast, and removes the element.
  - Cross-redirect (successful create/update, which didn't show *any* feedback before this
    round): the router appends `?toast=<message>&toast_type=success` to the 303 `Location`
    (`urlencode()`, both routers) instead of introducing session/cookie flash infrastructure —
    proportional to the need, matches this app's existing "no server-side session state" shape.
    `toast.js` reads `toast`/`toast_type` from `location.search` on load, fires the toast, then
    strips both params via `history.replaceState` so a manual reload doesn't repeat it.
- **Verification hit two *already-documented* gotchas again, back to back — both are logged
  above in this same file, and both bit again despite that:**
  1. **Dev-server Python-reload gotcha** (see the "Dev-server restart gotcha" entry above): the
     first live test showed the redirect `Location` header as plain `/settings/` with no toast
     query string at all, even though the router source clearly had it — `make run`'s
     `legendarr_bootstrap` process was still the one started before this round's router.py
     edits (Python changes don't hot-reload, only Jinja does). Fixed by `pkill -f
     legendarr_bootstrap` + relaunch (`nohup make run > /tmp/legendarr-run.log 2>&1 & disown`).
     **This will keep happening every session that edits a `router.py`/`service.py`/any
     non-template file — check `ps aux | grep legendarr_bootstrap`'s start time against the
     edit time before trusting a live redirect/response body.**
  2. **Browser-cache gotcha** (see the "Playwright/browser-cache gotcha" note above), but a
     stronger form of it this time: manually cache-busting the `<link>` `href` with a `?v=`
     query param (the fix used earlier this session) only forces a fresh fetch *for that one
     document* — the moment the flow does a real navigation (e.g. clicking Save, which POSTs
     and redirects to a new page), the freshly-loaded document's own `<link href="/static/styles.css">`
     (no query param) goes straight back to the browser's stale cached copy, so the toast
     rendered as an unstyled, unpositioned plain block (no `position: fixed`, no border-radius,
     stuck at the literal bottom of the document instead of floating bottom-right) even though
     `curl`ing the file directly, and even a mid-page fetch(), both confirmed the served CSS
     was already correct. Query-string busting doesn't survive a navigation; what actually fixed
     it: a CDP session — `const client = await page.context().newCDPSession(page); await
     client.send('Network.clearBrowserCache'); await client.send('Network.setCacheDisabled',
     {cacheDisabled: true});` — run once, before navigating, disables the cache for the rest of
     that page's navigations. **Also caught a false alarm from the same latency this causes at
     the tool layer**: a screenshot taken via a *separate* tool call after `click()` + the 3s
     auto-dismiss can easily land after the toast has already been removed (each Playwright MCP
     round-trip has real wall-clock latency) — that looked like "the toast didn't render" but
     was actually "the toast rendered, did its job, and left before the next tool call ran".
     Fix: do the `click()` + `waitForSelector('.toast')` + `page.screenshot()` **inside a single
     `browser_run_code_unsafe` call**, not as three separate tool round-trips, whenever the
     thing being screenshotted is time-limited.
- **How to apply:** if a future flow needs a warning toast, call
  `showToast("message", "warning")` from that page's own script, or set
  `data-toast-type="warning"` on a same-page hidden trigger — no CSS/JS changes needed, the
  three color variants already exist. If a new page needs the same save-success behavior,
  copy the `urlencode({"toast": ..., "toast_type": "success"})` pattern onto its redirect
  rather than inventing a second flash mechanism.

**Immediate follow-up, same round:** the user then asked for the arr-service "Test connection"
button's result (`_test_result.html`, swapped into `#test-result` via HTMX, `hx-target`/`hx-swap`
on `[data-test-connection]` in `arr_service_form.html`) to *also* toast — reversing the
deliberate exclusion two paragraphs up. Kept the persistent `#test-result` panel as-is (still
useful while the user is mid-edit) and additionally added a `data-toast-message`/`data-toast-type`
trigger to `_test_result.html`, success or error, alongside the existing `<p class="test-result
...">`. **The gotcha this exposed:** `toast.js`'s `[data-toast-message]` scan originally only ran
once, at `DOMContentLoaded`/script-load time (`document.querySelectorAll(...)` at the top level)
— it never saw a trigger element that arrived later via an HTMX swap, since HTMX doesn't reload
the page. Fixed by extracting the scan into `fireToastTriggersIn(root)`, calling it once for
`document` on load (unchanged), and adding `document.addEventListener("htmx:afterSwap", (event) =>
fireToastTriggersIn(event.detail.target))` so any future `hx-swap` target carrying a
`[data-toast-message]` picks it up automatically — no per-page wiring needed, htmx.min.js is
already loaded sitewide in `base.html`. **How to apply:** any future HTMX partial (a new
`_*.html` swapped by `hx-target`/`hx-swap`) gets a toast for free just by including the same
`<div hidden data-toast-message="..." data-toast-type="...">` — no JS changes needed, that path
is now generic. Also added Python-level tests for all three toast triggers (`test_arr_services_page.py`,
`test_settings_page.py`) — since this repo's web tests are `TestClient` + HTML-string assertions
with no JS execution, "does the toast show" is tested as "does the redirect URL carry
`toast=`/`toast_type=success`" (success case, `TestClient` follows redirects by default so
`response.request.url` is the final GET) and "does the response body contain the
`data-toast-message`/`data-toast-type` element" (error and HTMX-swap cases) — there's no
browser-level toast-rendering test in this suite, that gap was covered manually via Playwright
during this same round instead.

**Immediate follow-up, same round:** the user then decided the inline `<p class="test-result
test-result--success/--error">{{ result.message }}</p>` in `_test_result.html` was now redundant
with the toast and asked to drop it, toast-only. `_test_result.html` is now just the one hidden
`data-toast-message` trigger div — the `#test-result` swap target in `arr_service_form.html`
still exists (still a valid `hx-target`) but ends up empty after `toast.js` fires and removes the
trigger, so nothing renders there anymore. Removed the now-dead `.test-result--success`/
`.test-result--error` CSS rules; kept the base `.test-result` rule since `#test-indicator`
("Testing connection…", shown only while `.htmx-request` is toggled by htmx) still uses it for
`font-size`/`margin`. **How to apply:** if the persistent panel gets removed for the two form
pages' validation errors too, check `styles.css` again — nothing currently reads their inline
error text, it's toast-only there too, so no similar cleanup is pending. If a future page still
wants a lasting (non-3s) inline result alongside the toast, don't reuse `_test_result.html`'s
old shape — this round intentionally collapsed it to toast-only per explicit request.

**Immediate follow-up, same round:** shape tweak — `.toast`'s `border-radius` went from `999px`
(full pill) to `0.75rem`, matching the radius already used by card-like surfaces
(`.service-card` and friends use the same `0.75rem`) instead of the badge/pill radius. Squared
off but still visibly rounded, per the user's "mais quadrado... mas ainda com canto arredondado".

**Update (2026-08-24 — per-subtitle actions menu, movie/series detail tables):** the user asked
for a Bazarr-style per-badge dropdown (screenshot: clicking a subtitle language badge opens a
small menu grouped into "Tools"/"Actions"). Classified our own actions the same way: per-subtitle
(Sync timing, Translate from this, Blacklist-if-external — tied to one existing `subtitle` row)
vs. per-episode/file (Translate now, Manual search, Upload subtitle — act on the whole
`MediaFile`, no specific subtitle). This replaced an earlier same-session attempt at aligning two
separate `<td>` columns (Subtitles pills / Actions icons) line-by-line via matching `<li>` counts
and a fixed `min-height` — confirmed fragile (broke from an unrelated browser-cache issue, and
still read as "esquisito" once fixed) and was abandoned in favor of this design.
`macros.html::subtitle_pill_list()` now renders each pill as a `<span role="button" tabindex="0"
data-subtitle-menu-toggle>` that toggles a sibling `.subtitle-pill-menu` (`hidden` attribute,
`position: absolute`, same popover shape as `.lang-multiselect-options`) holding that subtitle's
own 3 actions — no more `subtitle_action_list()`/`actions-subtitle-list-*` div, no more
`.subtitle-line`/`vertical-align:top` cross-column alignment hack. The Actions `<td>` went back
to being a single un-stacked `.file-row-actions` row, file-level only. Open/close JS
(`static/js/subtitle-pill-menu.js`) follows the same open-on-click/close-on-outside-click shape
as `language-profile-form.js`'s multiselect, plus manual `keydown` Enter/Space handling since the
trigger is a `<span>`, not a real `<button>` (browsers don't auto-fire `click` for
Enter/Space on `role="button"` elements the way they do for real buttons/links).

- **New Pico gotcha, not covered by the list above:** Pico's own base
  `button, [role="button"], [type="button"], ...` rule (`vendor/pico.min.css`) **redefines the
  custom property `--pico-color` locally** on every button-like element (to
  `var(--pico-primary-inverse)`, the dark text needed for contrast against Pico's default
  gold-filled button background) and also sets `color: var(--pico-color)`. A custom `all: unset`
  button (like `.subtitle-pill-menu-item`) that then does `color: var(--pico-color)` picks up
  that *locally redefined* value, not the `:root`-level light gray — even though the custom
  button's own selector has higher specificity, it never re-declares `--pico-color` itself, so
  Pico's declaration (the only one that touches that custom property on this element) wins by
  default. Rendered as near-invisible dark-on-dark text; not a caching or specificity-tie issue,
  a different, subtler class of Pico shadowing than the `list-style`/`width:100%` ones above.
  Fix: use `var(--pico-muted-color)` instead (already the pattern `.page-toolbar-btn` uses for
  exactly this reason) and `var(--pico-primary)` for the `:hover` state, never `--pico-color`, on
  any custom-styled button/`[role="button"]` element. **How to apply:** before reaching for
  `var(--pico-color)` on any element that is (or has `role=`) a button, check this — it will
  silently resolve to the wrong, low-contrast value.
- Confirmed (again) the browser-cache gotcha documented above bites even with a live Playwright
  MCP tab kept open across a long multi-round session — `Network.clearBrowserCache` +
  `Network.setCacheDisabled` via a CDP session (`page.context().newCDPSession(page)`) before each
  re-verification `page.goto()` is the reliable fix; a plain `page.reload()`, even after
  `setCacheDisabled`, was NOT enough on its own once the stale entry already existed — needed the
  explicit `clearBrowserCache` call too.

**Immediate follow-up, same round:** the user then asked (terse, "traz o search e translate para
subtitle") to move Translate now and Manual search *out* of `.file-row-actions` too — confirmed
via `AskUserQuestion` (per [[ask-before-guessing-terse-ui-numbers]]) that this meant relocating
both into every pill's own `.subtitle-pill-menu`, not duplicating them in both places. **This
contradicts the per-subtitle-vs-per-file classification the paragraph above just established** —
the user wants these two shown per-pill even though neither actually depends on which subtitle
you clicked (`trigger_file_translation`/the manual-search panel are both keyed only by
`media_file_id`, confirmed in `media_library/router.py` — there is no per-language variant, that's
what "Translate from this" is already for). Implemented literally as asked: both buttons now
render identically in *every* pill's dropdown for a given file (same `hx-post`/`hx-get` URLs
repeated verbatim per pill) via a new private helper macro,
`_subtitle_pill_file_actions(media_file_id)`, called from both branches of
`subtitle_pill_list()`. `.file-row-actions` now holds only Upload subtitle.
**Regression this surfaced and had to fix in the same pass:** `subtitle_pill_list()` renders a
non-interactive `<span class="badge-empty">—</span>` (no menu at all) whenever a `MediaFile` has
zero subtitles — which meant a file with nothing on it yet would have *lost* Translate now/Manual
search entirely (no pill exists to host them), even though a subtitle-less file is arguably the
single most common case for reaching for either action. Fixed by giving the empty-state badge a
menu of its own: `<span class="subtitle-pill-item"><span class="badge-empty" role="button"
data-subtitle-menu-toggle>—</span><div class="subtitle-pill-menu">{{
_subtitle_pill_file_actions(...) }}</div></span>` — same wrapper shape as a real pill (needs
`.subtitle-pill-item`'s `position: relative` for the popover, and `trigger.parentElement` in
`subtitle-pill-menu.js` to find the sibling menu), just without the 3 subtitle-specific items.
Verified with a throwaway `TestClient` render (a movie file with `subtitles: []`) rather than
live-seeded data — none of the current Sonarr dev-stack fixture's episodes happen to have a
`media_file` with zero subtitles, so this path wasn't reachable to screenshot live.
**New Pico gotcha, second instance, hit immediately by this same fix:** `.badge-empty` picking up
`role="button"` (to become a menu trigger) means it now matches the bare `[role="button"]`
exclusion list too — same shadowing as `.subtitle-pill-menu-item` above — so its `:hover` state
needed `var(--pico-primary)`, not `var(--pico-color)`, for the same reason. **General lesson,
now confirmed twice: any element in this codebase that gains `role="button"` for a11y reasons
(not to opt into Pico's button chrome) needs its own selector added to the
`[role="button"]:not(...)` exclusion list in `styles.css` (~line 899) if it needs `display`,
sizing, or `--pico-color`-derived styling Pico shouldn't touch — `.lang-pill` already had this,
`.badge-empty` did not need the full exclusion (its only Pico-shadowed property, `--pico-color`,
  was dodged by using `--pico-primary` instead) but the *next* one probably will.**

**Immediate follow-up, same round (episode-table column widths):** the user then flagged the
series-detail episode table itself (screenshot): the Episode column (2-digit numbers) was taking
as much width as Title, because default browser table auto-layout distributes leftover width
proportionally to each column's own preferred content width — including the header text, not
just the data. Added `.episode-table { table-layout: fixed }` plus a `<colgroup>` in
`series_detail.html` giving `.episode-table-col-episode`/`-subtitles`/`-actions` explicit widths
and leaving Title unsized so it absorbs whatever's left (an unsized column only reliably grabs
"everything else" under `table-layout: fixed` when it's the *sole* one left unsized). First
attempt (5rem Episode / 3.5rem Actions) undershot and wrapped both headers onto multiple lines
("Episode"→"Episo/de", "Actions"→3 lines) — `table-layout: fixed` does not shrink-to-fit header
text the way auto-layout does, so a width below the header's own rendered width silently wraps
instead of overflowing. Settled on 6.5rem Episode / 6rem Actions (measured via a throwaway
off-screen `<span>` + `getComputedStyle` probe: "Episode" text ≈70px + 36px cell padding ≈106px
minimum at this app's 18px root font-size, so gave it a comfortable single-line margin above
that) — then, after a second follow-up screenshot from the user ("subtitles ficou esprimido"),
bumped `.episode-table-col-subtitles` from 12rem to 18rem since the language pills read as
cramped. **How to apply:** this `episode-table` colgroup pattern is `series_detail.html`-only —
`movie_detail.html`'s 3-column table (File/Subtitles/Actions) wasn't touched and has different
needs (the File column holds a full relative path, not a 2-digit number, so it shouldn't be
squeezed the same way). If Subtitles/Actions need adjusting again, remember header text sets a
hard minimum under `table-layout: fixed` — check rendered header width before picking a number,
don't just eyeball a smaller rem value.

**Same round, next follow-up: pills laid out vertically → horizontal, then 3-state pill coloring
(2026-08-24).** First `.subtitle-pill-list` was `flex-direction: column` (one pill per line);
user wanted them side by side like a reference screenshot from another app — changed to
`flex-wrap: wrap` (`styles.css` ~447), pill menus still anchor correctly since each still opens
relative to its own `.subtitle-pill-item`. Then a bigger ask, still terse but with clear
*direction* per [[ask-before-guessing-terse-ui-numbers]]'s refinement (named 3 states + named
colors, not a bare number) — acted on directly rather than asking: "legenda embedded amarelo,
external laranja forte, cinza a do profile mas não tem ainda" (embedded=yellow, external=strong
orange, profile-target-but-not-yet-acquired=gray). `subtitle.origin` was already exactly
"embedded"/"external" (`SubtitleOrigin` enum,
`subtitle_discovery/scan_video_subtitles.py:19-21`) so the real-pill half was just
`class="lang-pill lang-pill--{{ subtitle.origin }}"` in `subtitle_pill_list()`
(`templates/macros.html`) plus two new modifier rules — `.lang-pill--embedded` uses the
already-existing `--lg-warn-color`/(new) `--lg-warn-dim-background-color` pair (mirrors how the
base `.lang-pill` pairs `--pico-primary` with `--lg-primary-dim-background-color`), `external`
needed no new rule since the pre-existing base `.lang-pill` orange already was the "strong
orange". The gray "missing" state needed real backend work, not just CSS: `MediaFileRead` had no
notion of "this file's profile target languages it doesn't have a subtitle for yet" per-file
(`MediaDetailRead.target_languages` only existed at the whole movie/series level). Added
`MediaFileRead.missing_languages: list[str]`, computed in `get_media_detail.py::_media_file_reads`
using the same lowercase-compare convention `_missing_subtitles_count` already used (which got
simplified to `sum(1 for file in files if file.missing_languages)` once the per-file field existed
— avoids the same compare logic living in two places). `subtitle_pill_list()` renders one extra
`<li>` per missing language, gray (`.lang-pill--missing`, `--pico-muted-color` +
`--lg-neutral-dim-background-color`), clickable with the same file-level Translate-now/Manual-search
menu the empty-state `—` badge uses (not the 3 subtitle-specific items, since there's no real
`Subtitle` row to act on). **Gotcha caught only by live-testing, not by the unit tests:** the two
HTMX out-of-band partials that re-swap the Subtitles `<td>` after an action —
`_subtitle_acquire_result.html` and `_subtitle_blacklist_result.html` — call
`subtitle_pill_list()` too, and would've silently dropped the gray pills after every
upload/download/blacklist (macro's new 3rd arg defaults to `[]`) until the next full page load.
Fixed by adding `missing_languages` to `SubtitleAcquisitionResult`/`SubtitleBlacklistResult`
too, computed via a new single-file `missing_target_languages_for_media_file()` in
`subtitle_discovery/list_missing_subtitles.py` (a per-file sibling of the existing
whole-library `list_missing_target_languages_by_media_file()` — reused resolving one file's
profile instead of every media file's, since the router only has one `media_file_id` at that
point). **How to apply:** any *new* place that swaps a Subtitles `<td>` back in via
`subtitle_pill_list()` must also pass `missing_languages` through its result schema, or the gray
pills will vanish from that row until reload — check both HTMX OOB-swap call sites are still the
only ones before assuming a plain 2-arg call is safe. Live-verified by creating a demo
`LanguageProfile` (ja→pt-BR,en,fr, default) in the dev container's UI, since the seeded dev
Sonarr/Radarr fixture data ships with **no** language profile configured at all — left that demo
profile in place afterward (trivially deletable, low-risk on a local dev stack).

**Update (2026-08-27→2026-08-29 — per-file modal added, external pill's dropdown lost then
restored):** commit `61ee03c` (2026-08-27, "show acquisition detail and file size for every
subtitle") replaced each external subtitle pill's own dropdown (the one documented in the
2026-08-24 entries above) with a shared per-file `<dialog>` (`subtitle-file-modal.js`) listing
every external+embedded subtitle as a Language/Provider/Release/Match/Score/Size table — the
embedded pill (now a single collapsed count) opens it. The next morning, `f0e0e56` additionally
stopped the external pill from opening that dialog at all (made it a plain, inert label; a new
`.subtitle-file-title-trigger` on the row's title/file name became the other way in), and two
follow-up commits (`35b4c5f`, `a5b290e`) fixed that trigger's own Pico-button-chrome look
(gold-filled box) and font-size mismatch. Later the same day the user asked for the per-badge
dropdown back specifically for external/downloaded subtitles (pasted a Bazarr "Tools" menu
screenshot as a *shape* reference, confirmed via `AskUserQuestion` they wanted the existing
Sync timing/Translate from this/Blacklist trio in a pill dropdown, not a new subtitle-editing
feature set) — `4afe5a7` brought it back by reusing the exact same `subtitle-pill-menu.js` +
`.subtitle-pill-menu`/`data-subtitle-menu-toggle` mechanism the missing-language pill already
used (zero JS changes needed, it was already generic), via a new `_subtitle_pill_subtitle_actions(subtitle)`
macro. **Current (as of `4afe5a7`) state, both exist side by side:** the external pill's own
dropdown for quick single-subtitle actions, and the per-file dialog (title or embedded pill) for
the full acquisition-detail table — not a straight revert, the modal from `61ee03c` stayed.
**4th instance of the Pico-shadowing gotcha class** (see `--pico-color`/`.lang-pill`-exclusion
entries above): the app's own generic "content buttons" rule
(`button:not(...), [role="button"]:not(.lang-pill):..., styles.css` ~line 1300) resets every
`[role="button"]` to `font-size: var(--lg-font-xs)`, at higher specificity than a bare
`.subtitle-file-title-trigger` class rule — needed adding to that `:not()` exclusion list (same
place `.lang-pill` already is) *and* `font-size: inherit`/`line-height: inherit` locally to also
beat Pico's own `[role=button]{font-size:1rem}`. **How to apply:** any future element that gains
`role="button"` for a11y/menu-trigger reasons only (not to opt into Pico's or this app's button
chrome) needs adding to *both* exclusion points — Pico's shadowed custom properties (per the
gotcha above) AND this app's own `[role="button"]:not(...)` content-buttons rule — checking only
one is not enough, as this round found out the hard way via a live-screenshot pixel comparison.

**Update (2026-08-29, same day, PR #80 `feat/subtitle-pill-search-and-cleanup`) — the external
pill's dropdown grew from 3 to 5 items.** User pasted the same Bazarr Tools-menu screenshot again
and asked which of those items legendarr's backend already had, cross-referenced by grepping the
whole backend rather than guessing: only Sync/Translate/Search/Delete mapped to existing
capabilities (Search and Delete existed but as *file-level* actions — manual-search panel,
Blacklist), plus one more, Remove Style Tags, whose regex existed
(`clean_subtitle_text.py`/`_TAG_PATTERN`) but only ran automatically pre-translation, never as a
standalone action on an already-downloaded subtitle. Everything else on Bazarr's list (Remove HI
tags, Remove emoji, OCR fixes, Common fixes, Fix uppercase, Reverse RTL, Add color, Change frame
rate, Adjust times, Two-point fit) had zero backend code — filed as **ROADMAP 0.23.0**, not
built. The two "we have it" items landed in `_subtitle_pill_subtitle_actions(subtitle,
media_file_id)` (macro signature grew a `media_file_id` param for this): **Search** reuses the
*existing* file-level manual-search panel (`_subtitle_search_panel.html`,
`GET /files/{id}/subtitle-search`) rather than building a second one — the only change was an
optional `?language=` query param the pill passes (that subtitle's own language) so
`select_field()` pre-picks it, matched case-insensitively against `SUPPORTED_LANGUAGES` since a
subtitle's stored casing ("pt-br") isn't guaranteed to match the option value ("pt-BR"). **Remove
style tags** is new backend surface: `subtitle_discovery/strip_subtitle_style_tags.py` calls the
same `clean_subtitle_lines()` against an existing `.srt` file's parsed/composed content and
overwrites it in place (a no-op returning `False`, not an error, for `.ass`/`.ssa`/`.vtt` —
`subtitle_format.py` only parses SRT), wired through a new **synchronous** `POST
/subtitles/{id}/remove-style-tags` route (unlike sync-timing/translate, no scheduler job — it's
a local regex rewrite with nothing to wait on, same posture as the existing synchronous
blacklist route). New icon vendored: `code.svg` (`</>` glyph, matches Bazarr's own icon for this
exact action) — sourced from a local `lucide-react@0.577.0` install found under
`/home/viudes/projects/aargau/aargau-app/node_modules/...` per [[legendarr-lucide-icon-source]],
unpkg still blocked. **Branch-convention note:** this round's earlier fix commits had
accumulated on a non-main branch (`chore/ui-fine-tuning`, 6 `fix:` commits, no divergence from
main otherwise) — fast-forwarded straight into `main` (fix commits don't need a PR per
`AGENTS.md`) before branching this genuinely-new feature off the now-updated `main`, so the PR
diff wouldn't include unrelated prior fixes.

**Update (2026-08-29, next round — 4th `lang-pill` state, `--pending`, blue):** the
`PendingSubtitle` staging feature (PR #81, "search and upload subtitles for episodes Sonarr
hasn't downloaded yet") had a real bug hiding its own result: a language searched/downloaded for
an undownloaded episode still rendered the plain gray `.lang-pill--missing` pill, looking
untouched even right after a successful download. Root cause was backend, not CSS —
`download_pending_subtitle.py`/`upload_pending_subtitle.py` lowercased the target language
before storing it on `PendingSubtitle` (`"pt-BR"` → `"pt-br"`), so it never string-matched
`series.target_languages` and the read model never saw the episode as covered. Fixed by keeping
the original casing in the DB `language` column (matching the sibling file-based download path's
existing behavior — only the on-disk filename segment still gets lowercased) and adding a real
`pending_languages` field to the per-file/episode read model (`get_media_detail.py`). CSS-side,
this is now a genuine 4th `.lang-pill` state (`--missing` gray / `--embedded` yellow /
`--external` orange / new `--pending` blue) alongside the 3 documented in the 2026-08-24 entry
above. **How to apply:** any future "does this file/episode have a subtitle for language X yet"
check needs to consider pending as a distinct third bucket from missing/acquired, not fold it
into either — and if a new per-language state is ever added to `PendingSubtitle` or a sibling
table, store/compare it with its original casing, not lowercased, or it'll silently fail the
same string-match the way this one did.

**Update (2026-08-29, PR #83 — first `<input type="range">` in the app, Edit Language
Profile's new match-score sliders):** the user pasted a generic reference screenshot (a purple
slider, filled track + circular thumb, `0`/`100` labels) asking for per-media-type subtitle
match-cutoff configurability — confirmed via `AskUserQuestion` this meant the existing hardcoded
`DEFAULT_CUTOFF = 0.4` in `subtitle_acquisition/candidate_evaluation/match_score.py`, and that the
*color* in the reference was illustrative (this app's own gold `--pico-primary` was used, not a
new purple token — consistent with this file's own established restrained-accent taste, not a
literal copy of the pasted mockup). New `match_score_field()` macro
(`templates/macros.html`), `.match-score-field`/`.match-score-slider`/`-range-labels` in
`styles.css`.
- **New gotcha, not a specificity issue this time:** `accent-color: var(--pico-primary)` alone
  (the simplest modern way to theme a native range input) computed correctly
  (`getComputedStyle(...).accentColor` really was `rgb(201, 151, 79)`) but *painted* as a
  washed-out gray-blue in this sandbox's headless Chromium under this app's `color-scheme: dark`
  — confirmed by sampling actual rendered pixels (`(82, 95, 122)`, not the gold token) after the
  computed-style check falsely looked fine. Root cause not fully isolated (headless/software
  rendering path for native form controls vs. a real Chromium quirk), so `accent-color` was
  abandoned rather than trusted. Fix: fully custom rendering — `appearance: none` on the
  `<input>`, `::-webkit-slider-thumb`/`::-moz-range-thumb` for the gold thumb, and the filled
  portion of the track painted by hand as an inline `linear-gradient(to right, var(--pico-primary)
  {value}%, var(--pico-form-element-background-color) {value}%)` — set once on load and again on
  every `input` event (`language-profile-form.js`), alongside the same live `<output>` text update
  a native range input doesn't give you for free. **How to apply:** don't reach for bare
  `accent-color` to theme a range input in this app based on `getComputedStyle` alone — verify
  against actual rendered pixels (sample the screenshot, don't just trust the computed style) or
  default straight to the manual gradient-paint approach above, which is now the proven pattern.
- Verified end-to-end with Playwright against the rebuilt dev container (`docker compose -f
  docker-compose.dev.yml build legendarr && ... up -d legendarr`, per
  [[legendarr-docker-compose-dev-stack-staleness]]): dragging (simulated via `.value` +
  dispatching a real `input` event, not just setting the attribute) live-updates the `<output>`
  and the gradient fill, the two sliders are independent, and Save → reload round-trips both
  fields through the backend correctly. Needed a CDP `Network.clearBrowserCache` +
  `setCacheDisabled` session (`browser_run_code_unsafe`, not a plain reload) to see the rebuilt
  JS/CSS, per the browser-cache gotcha logged earlier in this file — still applies, still bites.

**Update (2026-08-31 — external pill's "Blacklist" item relabeled to "Delete"):** the user
screenshotted the same external-pill dropdown from the 2026-08-29 entries above and flagged a
missing delete option. Confirmed via `AskUserQuestion` (after finding ROADMAP.md 0.23.0's own gap
analysis already states Bazarr's "Delete" tool maps onto legendarr's existing "Blacklist" action,
not a separate capability) that no new action was wanted — just relabel the existing 5th item so
its delete behavior reads clearly. `_subtitle_pill_subtitle_actions()`/the file-modal row actions
block in `macros.html` now use `t("common.delete")` instead of `t("common.blacklist")` (that key
had exactly one caller, so it was deleted from all three locale catalogs rather than left dead);
icon stays `ban.svg` — unlike every other icon swap logged in this file, no new one was vendored,
since `backups.html`'s existing delete button already pairs `icon("ban")` with `t("common.delete")`,
confirming "ban" is this app's established delete icon, not something specific to blacklisting.
**The underlying behavior is unchanged**: the button still posts to
`/media/subtitles/{id}/blacklist`, still calls `blacklist_subtitle()`, and still both deletes the
file *and* adds a `SubtitleBlacklistEntry` so the release isn't re-fetched — only the visible
label/tooltip changed. **How to apply:** if a future ask wants a delete that *doesn't* also block
re-fetching (a real second action, not a relabel), that's new backend surface — a plain
unlink-and-rescan without `add_blacklist_entry`, most naturally in `subtitle_discovery/` since it
isn't acquisition-specific — not something the rename above already covers.
