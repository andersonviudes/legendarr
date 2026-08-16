---
name: legendarr-alembic-filecfg-logging-gotcha
description: Alembic's env.py fileConfig() silently disables pre-existing Python loggers process-wide, breaking pytest caplog in the full suite
type: project
---

`src/backend/db/migrations/env.py:27` calls `fileConfig(config.config_file_name)`
(stdlib `logging.config.fileConfig`) to set up logging from `alembic.ini`. This function
defaults to `disable_existing_loggers=True` — the first time it runs in a test process
(triggered by anything using the `isolated_database` fixture / real `init_db()` /
Alembic migration path), it sets `.disabled = True` on every `Logger` object that
already existed in `logging.Logger.manager.loggerDict` and isn't explicitly declared in
`alembic.ini`'s `[loggers]` section. That includes any module's
`logger = logging.getLogger(__name__)` created at import time. The disabled flag sticks
for the rest of the process (loggers are cached by name), so `pytest`'s `caplog` fixture
silently captures nothing (`caplog.text == ""`) for that logger in any test that runs
afterward — reproduced with `subtitle_translation.plugins`'s logger: `caplog`-based
assertions passed when running `test_plugins.py`/the `subtitle_translation` folder alone,
but failed with an empty `caplog.text` when running the full backend suite, because an
earlier test elsewhere used `isolated_database` first.

**Why:** not caused by anything in [[legendarr-db-migrations]] itself — it's stock
Alembic env.py boilerplate — but it's a real, order-dependent footgun for any future test
using `caplog` on a `legendarr_backend`/`legendarr_web` logger.

**How to apply:** either (a) fix at the source — pass
`fileConfig(config.config_file_name, disable_existing_loggers=False)` in `env.py`, which
is the commonly-recommended safe default and a one-line, low-risk change — or (b) when
writing a `caplog`-based test in the meantime, don't rely on it running reliably as part
of the full `make test` suite; assert on the function's return value/side effects instead
of on `caplog.text`. Chosen (b) — skipped the log-message assertions — for the
ROADMAP.md 0.9.0 plugin-loader tests (`test_plugins.py`) rather than touching shared
Alembic bootstrap code out of scope for that feature.
