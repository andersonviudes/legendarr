---
name: legendarr-i18n-conventions
description: how legendarr_web's i18n works — t() Jinja global, locale catalogs, ContextVar, where the active locale is stored
type: project
---

ROADMAP.md 0.19.0 added i18n scaffolding to `legendarr_web` (PR #65). Hand-rolled, no
Babel/gettext dependency — matches the project's minimal-dependency style.

- **Catalogs**: `src/web/src/legendarr_web/i18n/locales/{en,es,pt-BR}.json`, flat
  dot-namespaced key → string maps (e.g. `"nav.dashboard"`, `"common.save"`). `en` is
  the reference locale — `src/web/tests/i18n/test_translations.py` fails the build if
  another locale's key set drifts out of sync with it.
- **`t(key, **kwargs)`**: a Jinja global registered in `templates/loader.py`, calling
  `i18n.translator.translate()`. `**kwargs` are `.format()`-interpolated into the
  string (e.g. `t("arr_services.add_server", label="Radarr")`).
- **Why a `ContextVar`, not `request.state`**: a `pass_context` Jinja global tied to
  `request.state` breaks when called from a macro imported via
  `{% from "macros.html" import x %}` (no `with context`) — Jinja doesn't thread the
  caller's `request` var into an imported macro's own context. `i18n.translator.current_locale`
  is a `contextvars.ContextVar` instead, set once per request by the app-wide
  `i18n.resolve_locale.resolve_locale` dependency — works the same whether `t()` is
  called directly in a template or from any macro.
- **Where the locale is stored**: `ui_locale` on `AppConfigFile`/`config.yaml` — an
  instance-wide setting (single shared admin account, no multi-user model), same
  posture as `default_translation_provider`. Edited from Settings → General
  (`/settings/general/`), backed by `GET`/`PUT /settings/general` on the backend.
  `resolve_locale` calls that endpoint on every request (one more loopback call, same
  cost `require_authenticated_session` already pays) — `/login`/`/logout` are exempt
  and always render in `en` (the backend endpoint requires auth once enabled, so those
  pages can't call it).
- **Server-built strings** (toast messages in various `router.py` files, ~8 of them)
  also go through `translate(current_locale.get(), "key")` directly — same `ContextVar`,
  no Jinja context needed since it's plain Python.
- **Adding a new UI string**: use `t("some.key")` in the template, add the key to all
  three locale JSON files. No extraction tooling — hand-maintained.
- **Not translated on purpose**: backend-sourced data (titles, error details, log
  lines), and the login page (see the `/login` exemption above).

See also [[legendarr-lucide-icon-source]] — the new `globe` nav icon for this feature
was hand-written from memory, not sourced from Lucide directly, because both prior
fetch paths were unavailable in that session.
