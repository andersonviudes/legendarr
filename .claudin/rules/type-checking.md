---
paths: src/**/*.py
---

# Type checking

- The repo is type-checked with pyright, configured by `pyrightconfig.json` (root) to
  resolve the `uv` workspace's `.venv` — without it pyright can't resolve any workspace
  import and reports hundreds of false positives.
- Run the `Typecheck` tool (or `uv run pyright`) alongside `make lint` and `make test`
  before considering any Python change done — it's not yet wired into
  `.github/workflows/ci.yml`, so nothing else catches these errors.
- Fix real diagnostics at the source rather than suppressing them:
  - A SQLModel primary key (`id: int | None`) that's already been persisted or fetched
    from the DB is never actually `None` at runtime — narrow it with
    `assert obj.id is not None` rather than loosening the parameter type.
  - `Model.column.in_(...)` isn't typed by SQLModel — wrap the column with
    `sqlmodel.col()`: `col(Model.column).in_(...)`.
  - Prefer a `cast()` with a one-line comment explaining why the narrower type is
    guaranteed at runtime (see `arr_clients/base.py`'s `SeriesLibraryClient` Protocol,
    or `sync_media_library.py`'s `MEDIA_MODEL_BY_TYPE`-guarded casts) over `# type:
    ignore`, which silences everything on the line instead of just the one diagnostic.
