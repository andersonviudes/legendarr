---
name: legendarr-opensubtitles-login-auth
description: OpenSubtitles now authenticates via username/password login like Bazarr, not a user-supplied API key — and the app-level API key is a placeholder that needs a real value
type: project
---

Built 2026-08-27 on `feat/opensubtitles-login-auth`, following a direct user comparison against
Bazarr's own OpenSubtitles.com provider (`bazarr/custom_libs/subliminal_patch/providers/
opensubtitlescom.py`) — user's own token turned out to be a JWT login token, not an API key
(see [[legendarr-opensubtitles-search-options-kept]] for the pre-existing provider context).

**Key insight, confirmed against Bazarr's source**: OpenSubtitles.com's `Api-Key` header
identifies the *calling application*, not the end user. Bazarr hardcodes its own key
(`get_providers.py:261`, `'s38zmzVlW7IlYruWi7mHwDYl2SfMQoC1'`) and only ever asks its users for
their own OpenSubtitles.com username/password, which it exchanges for a bearer token via
`POST /api/v1/login`.

**What changed**: `opensubtitles` moved from `_API_KEY_KINDS` to `_USERNAME_PASSWORD_KINDS` in
`subtitle_acquisition/models.py` (same bucket as Addic7ed/legendas.net now). `providers/
opensubtitles.py` gained `opensubtitles_client()`/`opensubtitles_login()` (mirrors
`legendas_net.py`'s `legendas_net_login` pattern) and `OpenSubtitlesProvider` now holds one
lazily-created, logged-in `ProviderHttpClient` for its lifetime (`close()` releases it) instead
of building a fresh anonymous client per call. Ported Bazarr's VIP-routing nuance too: a login
response's `base_url` starting with `vip` means the account is VIP, and subsequent calls
(including the download-link fetch) route through that dedicated host with `Authorization:
Bearer <token>` baked into the client at construction — a non-VIP account gets no bearer token
at all, sending only `Api-Key`, exactly like Bazarr's `login()` (`opensubtitlescom.py:214-243`).
No template/DB migration changes needed — `username`/`password` columns and the web form's
generic `credential_fields`-driven rendering already existed for Addic7ed/legendas.net.

**Unresolved blocker**: `_APP_API_KEY` in `providers/opensubtitles.py` is a placeholder
(`"REPLACE_WITH_LEGENDARR_OPENSUBTITLES_API_KEY"`) — legendarr has no registered OpenSubtitles.com
API consumer of its own yet. Every real login call 401s until someone (the account owner,
`andersonviudes`, confirmed VIP) registers one at https://www.opensubtitles.com/en/consumers and
the real key gets dropped in. Until then this feature is implemented but non-functional.

**Why:** avoids re-deriving the Api-Key-vs-login distinction, the VIP `base_url` routing detail,
or the "app key is hardcoded, only username/password is per-user" design decision from scratch.

**How to apply:** if a real key gets registered, it's a one-line change to `_APP_API_KEY`
(remove the TODO comment above it too). If extending the login flow (e.g. token refresh/caching
across restarts — today's token is per-provider-instance, not persisted), start from
`_authenticated_client()`.
