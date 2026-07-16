---
paths: modules/**/*.py
---

# Python conventions

- Ruff config (root `pyproject.toml`): line length 100, `target-version py312`, and an
  explicit lint `select` list (`E, F, I, UP, B`) — narrower than Ruff's default rule set.
  Run `make lint` / `make format` rather than invoking `ruff` directly so both modules'
  configs are picked up consistently.
- Config is env vars prefixed `LEGENDARR_`, loaded via `pydantic-settings` (see
  `.env.example` and `docs/configuration/environment-variables.md`). Don't hardcode
  Radarr/Sonarr URLs or keys — add a new `Settings`/`WebSettings` field instead.
