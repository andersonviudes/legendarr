---
name: legendarr shared HTTP client conventions
description: ProviderHttpClient in http_client/client.py — the required base for any new outbound HTTP integration (Radarr/Sonarr today, subtitle-provider/translation-API clients later)
type: project
---

Built 2026-07-16, completing the "Media providers" bullet of `ROADMAP.md` 0.1.0 (shared HTTP
client conventions — timeout/retry/error handling). `RadarrClient`/`SonarrClient` used to each
construct their own `httpx.Client` inline with a hardcoded `timeout=10.0` and no retry/error
wrapping (`response.raise_for_status()` let raw `httpx.HTTPStatusError` escape).

**What exists:** `legendarr_backend/http_client/client.py` (moved into its own `http_client/`
subject folder 2026-07-16, promoted out of `shared_kernel/` to the module's top level in a
second reorg the same day — see `legendarr-architecture.md`) — `ProviderHttpClient(provider,
base_url, headers=None)` wraps an `httpx.Client` with `DEFAULT_TIMEOUT = 10.0` and
`httpx.HTTPTransport(retries=DEFAULT_RETRIES)` (`DEFAULT_RETRIES = 2`, retries connection-level
failures only — httpx's transport-level retry doesn't retry on HTTP status codes). Its
`get_json(path)` does the request and raises `ProviderClientError` (wrapping both
`httpx.HTTPStatusError` and `httpx.RequestError`) with the provider name and status/reason in the
message, instead of leaking raw httpx exceptions to callers. `RadarrClient`/`SonarrClient` now
just build a `ProviderHttpClient("Radarr"/"Sonarr", base_url, headers={...})` and call
`get_json(...)`.

**Why a shared top-level folder and not media_library:** the roadmap bullet explicitly says
this is meant for "later subtitle-provider and translation-API clients" too, which live in
different slices (`subtitle_acquisition`, `subtitle_translation`) — putting it inside
`media_library/` would mean those slices reaching into an unrelated slice's internals, which
the Dependency Inversion rule in `.claudin/rules/clean-code-solid.md` forbids. `http_client/`
(a top-level folder outside any domain slice, promoted out of `shared_kernel/` 2026-07-16) is
the only place both current and future integrations can import from.

**How to apply:** any new outbound integration to an external HTTP API (a subtitle provider,
DeepL/OpenAI-style translation API, etc.) should build a `ProviderHttpClient` instead of
constructing `httpx.Client` directly, and only add `post_json`/other verbs to
`http_client.py` if/when a real caller needs them (YAGNI — `get_json` was the only verb an
actual caller needed as of 2026-07-16). Tests for it use `httpx.MockTransport` (built into
`httpx`, no extra dependency) — see `modules/backend/tests/http_client/test_http_client.py`
for the pattern (swap `client._client` for one built with `MockTransport`), and
`modules/backend/tests/media_library/providers/test_radarr_client.py`/`test_sonarr_client.py`
for the monkeypatch-`get_json` pattern used to test callers without hitting the network.

**Update 2026-07-22 (`post_json`, `ping`, `request`, shared `_send`):** added while building
`subtitle_acquisition`'s connection tests — `post_json(path, json)` (JSON body, JSON response,
for legendas.net's login), `ping(path="/")` (confirms reachability without parsing a body, for
providers with no JSON API), and `request(method, path, data=None, follow_redirects=False)`
(returns the raw `httpx.Response`, for Addic7ed's cookie-based HTML login flow). All four
public methods now funnel through one private `_send(send_fn, check_status=True)` that does
the try/except wrapping once. **Gotcha:** `httpx.Response.raise_for_status()` raises on *any*
non-2xx status, including 3xx redirects — not just 4xx/5xx like the name suggests. `request()`
passes `check_status=False` because of this: Addic7ed's login treats a 302 as the *success*
case and needs to inspect it, not have it raised as an error. If you add another verb that
needs to see a non-2xx response on purpose, default it to `check_status=False` too.
