.PHONY: install lint format test run docker-build docs-install docs-serve docs-build

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

docker-build:
	docker build -t legendarr:local .

docs-install:
	pip install -r docs/requirements.txt

docs-serve:
	mkdocs serve

docs-build:
	mkdocs build --strict
