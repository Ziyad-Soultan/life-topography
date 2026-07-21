# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
COPY packages ./packages
RUN uv sync --frozen --no-dev --package life-topography

FROM python:3.12-slim-bookworm AS runtime
RUN groupadd --system topography && useradd --system --gid topography --home /app topography
WORKDIR /app
COPY --from=builder --chown=topography:topography /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" TOPOGRAPHY_DATABASE=/data/vault.db
RUN mkdir /data && chown topography:topography /data
USER topography
VOLUME ["/data"]
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/health', timeout=2)"]
CMD ["uvicorn", "life_topography.api:app", "--host", "0.0.0.0", "--port", "8787"]
