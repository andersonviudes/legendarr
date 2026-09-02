---
name: legendarr-conftest-missing-model-import-gotcha
description: src/backend/tests/conftest.py must import every table module or in_memory_session's create_all fails with a confusing FK error when tests run outside the full suite
type: project
---

`tests/conftest.py`'s `in_memory_session` fixture builds its schema from
`SQLModel.metadata.create_all(engine)`, which only contains tables for model modules that
have actually been imported somewhere in the process by the time it runs. `conftest.py`
already imports most slices' `models.py` explicitly for this reason (see its own comment:
"Every table module must register on SQLModel.metadata before `in_memory_session` calls
create_all"), but `legendarr_backend.subtitle_proxies.models` was missing from that list —
found 2026-09-02 while running `src/backend/tests/subtitle_acquisition/` in isolation via
`RunTests`, which failed on fixture setup with `sqlalchemy.exc.NoReferencedTableError:
Foreign key associated with column 'subtitleproviderconfig.proxy_id' could not find table
'subtitleproxy'`. Fixed by adding `from legendarr_backend.subtitle_proxies import models as
_subtitle_proxies_models  # noqa: F401` alongside the other explicit imports.

**Why:** when the *whole* test suite runs, some other test module's own imports happen to
register every table before any test executes, masking the gap — it only surfaces when a
narrower subset of test files is collected (a common workflow: scoping `RunTests`/`pytest`
to just the slice being changed).

**How to apply:** when a new top-level slice gains a `table=True` SQLModel (especially one
with a foreign key another table references), add its `models` module to
`tests/conftest.py`'s explicit import block in the same change — don't rely on another test
file's import order to make `in_memory_session` work. If a narrowly-scoped test run ever
fails with `NoReferencedTableError`/`NoReferencedColumnError` in fixture setup rather than
in the test body, suspect this gap before suspecting the change under test.
