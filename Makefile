.PHONY: install lint format test run db-revision db-upgrade bump-version docker-build docs-install docs-serve docs-build

install:
	uv sync --all-packages

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .

test:
	uv run pytest

run:
	uv run --package legendarr-bootstrap python -m legendarr_bootstrap

db-revision:
	uv run --package legendarr-backend alembic -c src/backend/alembic.ini revision --autogenerate -m "$(message)"

db-upgrade:
	uv run --package legendarr-backend alembic -c src/backend/alembic.ini upgrade head

bump-version:
	./scripts/bump_version.sh $(part)

docker-build:
	docker build -t legendarr:local .

docs-install:
	pip install -r docs/requirements.txt

docs-serve:
	mkdocs serve

docs-build:
	mkdocs build --strict
