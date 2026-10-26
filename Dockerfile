# Стадия сборки: зависимости в .venv (слой кэшируется, пока не меняется uv.lock)
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# Стадия запуска: без uv, пользователь не root
FROM python:3.12-slim-bookworm
ENV TZ=Europe/Moscow PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY app ./app
COPY config ./config
RUN mkdir -p data && chown app:app data
USER app
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-m", "app.healthcheck"]
CMD ["python", "-m", "app.main"]
