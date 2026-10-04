# syntax=docker/dockerfile:1
# Match the Codex CLI protocol version used by the working local integration.
# Linux live inference still requires an independent server-side sign-in.
FROM node:24-bookworm-slim AS codex
ARG CODEX_VERSION=0.158.0-alpha.2.1
RUN npm install --global --prefix /opt/codex --omit=dev "@openai/codex@${CODEX_VERSION}" \
    && /opt/codex/bin/codex --version

FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.12.2 /uv /uvx /usr/local/bin/
COPY --from=codex /usr/local/bin/node /usr/local/bin/node
COPY --from=codex /opt/codex /opt/codex

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    PATH="/app/.venv/bin:/opt/codex/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin" \
    OMNIGENT_CODEX_PATH=/opt/codex/bin/codex \
    OMNIGENT_DATA_DIR=/var/lib/falsify/omnigent \
    OMNIGENT_NO_UPDATE_CHECK=1 \
    FALSIFY_DATA_DIR=/app/data \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 falsify \
    && useradd --uid 10001 --gid 10001 --create-home --shell /bin/sh falsify

WORKDIR /app
COPY pyproject.toml uv.lock ./
# Compile immutable dependency bytecode during the build to reduce startup CPU
# on the shared one-core droplet, where the runtime cannot write .pyc files.
RUN uv sync --locked --no-dev --no-install-project --compile-bytecode \
    && uv cache clean

# Explicit copy list and .dockerignore prevent local credentials, PDFs, data,
# logs, the resume, and development environments from entering the image.
COPY falsify/*.py ./falsify/
COPY agents/falsify.yaml ./agents/falsify.yaml
COPY static/index.html static/app.js static/styles.css ./static/
RUN mkdir -p /app/data /app/artifacts/runs /app/.codex-tmp /var/lib/falsify/omnigent /home/falsify/.codex \
    && chown -R 10001:10001 /app/data /app/artifacts /app/.codex-tmp /var/lib/falsify /home/falsify \
    && chmod 700 /home/falsify /home/falsify/.codex

USER 10001:10001
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/status', timeout=4).read()"]
CMD ["uvicorn", "falsify.server:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "1", "--no-proxy-headers"]
