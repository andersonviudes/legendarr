.PHONY: install lint format test run db-revision db-upgrade docker-build docs-install docs-serve docs-build

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
	uv run --package legendarr-web python -m legendarr_web

db-revision:
	uv run --package legendarr-backend alembic -c modules/backend/alembic.ini revision --autogenerate -m "$(message)"

db-upgrade:
	uv run --package legendarr-backend alembic -c modules/backend/alembic.ini upgrade head

docker-build:
	docker build -t legendarr:local .

docs-install:
	pip install -r docs/requirements.txt

docs-serve:
	mkdocs serve

docs-build:
	mkdocs build --strict
