FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY modules/backend/pyproject.toml modules/backend/pyproject.toml
COPY modules/web/pyproject.toml modules/web/pyproject.toml
COPY modules/bootstrap/pyproject.toml modules/bootstrap/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --all-packages --no-install-project --no-dev

COPY modules ./modules

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --all-packages --no-dev

FROM python:3.12-slim-bookworm AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    LEGENDARR_DATA_DIR=/config

VOLUME ["/config"]
EXPOSE 8000

CMD ["python", "-m", "legendarr_bootstrap"]
