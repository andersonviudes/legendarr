.PHONY: install lint format test run docker-build

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
