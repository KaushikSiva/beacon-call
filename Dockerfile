# syntax=docker/dockerfile:1

FROM node:22-bookworm-slim AS web-builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY tsconfig.json vite.config.ts ./
COPY web ./web
RUN npm run build


FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY beacon_call ./beacon_call
COPY main.py ./main.py
COPY scripts/render_start.sh ./scripts/render_start.sh
COPY --from=web-builder /app/web-dist ./web-dist

RUN uv sync --locked --no-dev && chmod 0755 ./scripts/render_start.sh

EXPOSE 10000
CMD ["./scripts/render_start.sh"]
