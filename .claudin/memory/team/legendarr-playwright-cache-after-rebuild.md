---
name: legendarr-playwright-cache-after-rebuild
description: Playwright MCP's browser keeps serving stale styles.css/JS after the legendarr dev container is rebuilt mid-session
type: project
---

Found 2026-08-26 doing a mobile-CSS fix pass: after `docker compose -f docker-compose.dev.yml
build legendarr && ... up -d legendarr` (see [[legendarr-docker-compose-dev-stack-staleness]])
mid-conversation, a fresh `browser_navigate` to a page already visited earlier in the same
Playwright MCP session kept rendering the OLD `/static/styles.css` and `/static/js/*.js` —
`curl` against the server showed the new bytes immediately, but `document.styleSheets`
inside the page showed the pre-rebuild rules. Starlette's `StaticFiles` sends no
`Cache-Control` header, so Chromium falls back to heuristic freshness off `Last-Modified`,
and a synthetic `page.keyboard.press('ControlOrMeta+Shift+r')` does **not** trigger a real
hard-reload/cache-bypass the way an actual user keypress does.

**Why:** without this, a UI fix looks unverified or "not applied" even though the server is
already serving the corrected file — wasted time re-diffing code that was already correct.

**How to apply:** after rebuilding the container while a Playwright MCP page from before the
rebuild is still open, force a real refetch of just the stale asset(s) instead of trusting a
plain navigate or a synthetic hard-reload key combo:

```js
// CSS
const link = document.querySelector('link[href*="styles.css"]');
link.href = '/static/styles.css?bust=' + Date.now();

// JS (re-run a <script> that already executed on load)
const s = document.createElement('script');
s.src = '/static/js/sidebar.js?bust=' + Date.now();
document.body.appendChild(s);
```

Do this once per open tab right after the rebuild, before screenshotting/asserting on
computed styles or behavior wired up by that script.

**Refinement (2026-08-26, poster-grid padding fix):** confirmed opening a fresh CDP session
and calling `Network.setCacheDisabled({cacheDisabled: true})` before `page.goto` is NOT
enough by itself — the stale stylesheet still won. What worked as a one-line alternative to
the href-swap trick above: call `Network.clearBrowserCache()` on that CDP session *before*
`setCacheDisabled` and the `page.goto`. Either technique is fine; `clearBrowserCache` is
less surgical (drops the whole browser cache, not just one asset) but is a single call with
no per-file wiring.

**Refinement (2026-08-29, Save-button dirty-badge feature):** this one wasn't the browser's
own HTTP cache at all — `Network.setCacheDisabled` + a brand-new `page.goto` (not just a
reload of an already-open tab) still returned the pre-rebuild bytes for `/static/js/*.js`,
confirmed by reading the raw network response body (`browser_network_request` with
`part: "response-body"`), while a plain host-side `curl` against the same URL at the same
moment returned the fixed file — so the staleness lives somewhere in the Playwright MCP
browser's own request path, not in Chromium's cache heuristics. What worked: register a
`page.route('**/static/js/*.js', ...)` handler (via `browser_run_code_unsafe`) that rewrites
the request URL to append `?bust=<Date.now()>` via `route.continue({ url })`, installed
*before* `page.goto`. Reach for this whenever a `<script src>` fix doesn't seem to take
effect even after the `clearBrowserCache` refinement above — confirm with the
network-response-body check first, since that's the only way to tell this apart from an
ordinary stale-cache case.
