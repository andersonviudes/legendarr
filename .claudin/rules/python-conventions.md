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
- Logging: every module that logs gets its own `logger = logging.getLogger(__name__)` at
  the top of the file (see `scheduling/retry.py`, `media_library/jobs.py`) — never call
  `logging` functions directly at module level. `configure_logging()`
  (`legendarr_backend/logging/setup.py`) is called exactly once, in
  `legendarr_bootstrap`'s entrypoint (`legendarr_bootstrap/__main__.py`), to configure the
  root logger for the whole process; don't call it again elsewhere.
