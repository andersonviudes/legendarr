---
name: legendarr-htmx-nested-poller-outerhtml-swap-gotcha
description: htmx 1.9.12 bug — a fast-polling child nested inside a periodically self-outerHTML-swapping parent ends up empty after the first swap cycle
type: feedback
---

Never nest an independently-polling element (`hx-trigger="every Ns"` on itself) as a
*child* of an ancestor that periodically replaces its own `outerHTML`
(`hx-select="#self-id" hx-swap="outerHTML" hx-trigger="every Ms"` targeting itself). In
the vendored htmx 1.9.12 (`src/web/src/legendarr_web/static/vendor/htmx.min.js`), the
ancestor's self-swap starts coming back genuinely empty (confirmed via
`el.innerHTML.length === 0` and a node-identity check in a real browser) after the first
cycle once a fast-polling child lives inside it — even though the server's own response
for that URL is always correct.

**Why:** Found while adding the ROADMAP 0.20.0 "Live progress" dashboard section — nested
a `hx-trigger="load, every 3s"` div inside `#dashboard-content` (which self-swaps every
15s, see `dashboard/templates/dashboard.html`). Confirmed via `git stash` + rebuild: the
*original* `#dashboard-content` (stat cards only, no nested poller) survives repeated 15s
cycles fine in a real browser left open; adding the nested fast-poller broke it every
time. Automated tests (`TestClient`, no real timers/browser) never catch this — it only
shows up with a real browser tab left open past the first refresh interval.

**How to apply:** Keep every independently-polling element as a **sibling** of any
ancestor that self-swaps its own `outerHTML`, never a descendant — exactly how the
topbar's `#notifications-panel-body` (`hx-get="/system/tasks/running" hx-trigger="load,
every 3s, refresh-tasks"`, `templates/base.html`) already does it: it lives in the
header, which itself is never periodically outerHTML-swapped. When adding a new "live"
section to a page that already has a periodic self-refresh wrapper (like the Dashboard's
`#dashboard-content`), put the new poller *outside* that wrapper as a separate
`<section>`, not inside it. See [[legendarr-playwright-mcp-numeric-param-schema-bug]] for
the harness quirks encountered debugging this live.
