FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/backend/pyproject.toml src/backend/pyproject.toml
COPY src/web/pyproject.toml src/web/pyproject.toml
COPY src/bootstrap/pyproject.toml src/bootstrap/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --all-packages --no-install-project --no-dev

COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --all-packages --no-dev

FROM python:3.12-slim-bookworm AS runtime

ARG VERSION=0.0.0-dev
LABEL org.opencontainers.image.title="legendarr" \
      org.opencontainers.image.description="Self-hosted subtitle translation companion for Radarr and Sonarr" \
      org.opencontainers.image.source="https://github.com/andersonviudes/legendarr" \
      org.opencontainers.image.licenses="GPL-3.0-or-later" \
      org.opencontainers.image.version="${VERSION}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-por \
    tesseract-ocr-spa \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    tesseract-ocr-ita \
    tesseract-ocr-jpn \
    gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app /app
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENV PATH="/app/.venv/bin:$PATH" \
    LEGENDARR_DATA_DIR=/config \
    PUID=1000 \
    PGID=1000

VOLUME ["/config", "/media"]
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "legendarr_bootstrap"]
