# Contributing

## Setup

```bash
git clone https://github.com/andersonviudes/legendarr.git
cd legendarr
make install
```

## Workflow

```bash
make lint    # ruff check + format --check
make format  # ruff format
make test    # pytest
```

CI runs the same lint, format check, and test suite on every push and pull request to
`main`, plus a Docker build to validate the image still builds.

## Commit messages

Commits follow [Conventional Commits](https://www.conventionalcommits.org/): a `type:`
prefix (`feat`, `fix`, `docs`, `chore`, `ci`, `refactor`, `test`, ...) followed by a short,
imperative summary.

## Code style

Follow the existing [Screaming Architecture + Vertical Slice](architecture/overview.md)
layout: new features get their own top-level slice folder named after the business
capability, inside the module that owns them (`modules/backend` for domain logic,
`modules/web` for UI/routes).

## Documentation

Docs live in `docs/` as Markdown, built with [MkDocs](https://www.mkdocs.org/) and the
[Material theme](https://squidfunk.github.io/mkdocs-material/). Preview locally with:

```bash
make docs-install
make docs-serve
```
