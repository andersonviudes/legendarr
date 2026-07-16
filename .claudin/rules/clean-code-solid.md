---
paths: modules/**/*.py
---

# Clean Code & SOLID

Apply these when writing or reviewing any Python code in `modules/backend` or
`modules/web`, on top of the Screaming Architecture + Vertical Slice layout
described in `AGENTS.md`.

## Single Responsibility

- One reason to change per module/class/function. A slice folder
  (`subtitle_translation`, `media_library`, `language_profiles`, ...) may
  hold several files, but each file owns one concern (e.g. `client.py` talks
  to the API, `schemas.py` defines DTOs, `service.py` holds orchestration).
- Functions should do one thing. If a function needs a comment to separate
  "sections", split it.
- Don't grow a generic `service.py`/`utils.py` into a god object. If it
  starts coordinating unrelated concerns, split it into new files inside the
  slice.

## Open/Closed

- Extensibility points (subtitle providers, translation providers, Radarr vs
  Sonarr clients, language profile matching) should be added as new
  implementations of an existing `Protocol`/ABC, not by branching on a type
  flag (`if provider == "openai": ... elif ...`) inside shared logic.
- Prefer registering new implementations over editing the dispatch logic
  that already works for existing ones.

## Liskov Substitution

- Any class implementing a shared `Protocol`/base class (e.g. a media
  provider client, a translation backend) must be usable wherever that
  protocol is expected, with the same pre/post-conditions — don't narrow
  accepted inputs or raise on cases the base contract allows.

## Interface Segregation

- Keep `Protocol`/ABC definitions narrow and slice-specific (e.g. a
  `SubtitleProvider` protocol shouldn't also demand translation methods).
  Don't force implementers to satisfy methods they don't need.

## Dependency Inversion

- Business logic in `legendarr_backend` depends on abstractions
  (`Protocol`/ABC) for Radarr/Sonarr clients and translation providers, not
  on concrete HTTP/SDK classes directly — inject the concrete implementation
  at the call site (FastAPI dependency, scheduler wiring), don't construct it
  inline inside domain code.
- `legendarr_web` depends on `legendarr_backend`'s public interfaces; it
  should not reach into backend internals to bypass them.

## Clean Code

- Names say what something is/does; avoid abbreviations beyond what the
  codebase already uses (`db`, `cfg` are fine if already established
  elsewhere — don't invent new ones).
- Prefer small, composable functions over long ones with multiple levels of
  nested branching; extract guard clauses early instead of deep nesting.
- No duplicated logic across slices — if two slices need the same behavior,
  move it to the relevant shared top-level module (`config/`, `database/`,
  `http_client/`, `logging/`), not copy-paste.
- Don't add abstraction (extra interfaces, config flags, indirection) for
  hypothetical future needs — only what the current feature requires (YAGNI).
- Keep functions/files within Ruff's line-length (100) and the existing
  `select = ["E", "F", "I", "UP", "B"]` lint set; run `make lint` before
  considering a change done.
