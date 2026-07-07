# syntax=docker/dockerfile:1
# hadolint global ignore=DL3008

FROM mitodl/ol-python-base:3.11 AS base
LABEL maintainer="ODL DevOps <mitx-devops@mit.edu>"

# App-specific apt extras; common-core packages are in mitodl/ol-python-base:3.11.
# Operator tooling (htop, ngrep, screen, etc.) is also kept here for parity
# with the production image; trim this list if the production image diverges.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends \
      dnsutils \
      htop \
      iputils-ping \
      less \
      libcairo2-dev \
      lsof \
      nano \
      ngrep \
      procps \
      screen \
      wget

FROM base AS deps

# Trusted certs (org PKI + local-dev mkcert root injected at deploy time).
COPY --chmod=644 certs/ /usr/local/share/ca-certificates/
RUN update-ca-certificates

# Install Python dependencies before copying source.
# mitol_*.gz are local wheels that uv resolves from the lock file.
COPY --chown=mitodl:mitodl pyproject.toml uv.lock /src/
COPY --chown=mitodl:mitodl mitol_*.gz /src/

USER mitodl
WORKDIR /src
# BuildKit cache mount keeps the uv download cache across builds.
RUN --mount=type=cache,target=/opt/uv-cache,uid=1000,gid=1000 \
    uv sync --frozen --no-install-project --no-dev

FROM deps AS code

COPY . /src
WORKDIR /src

ENV XDG_CACHE_HOME=/tmp/.cache

# ─── Node / frontend asset build ─────────────────────────────────────────────
FROM node:17.9 AS node

COPY --from=code /src /src
WORKDIR /src

ENV NODE_ENV=production
RUN yarn workspace mitx-online-public install --immutable && \
    yarn workspace mitx-online-public run build && \
    yarn workspace mitx-online-staff-dashboard install --immutable && \
    yarn workspace mitx-online-staff-dashboard run build

# ─── Runtime targets ─────────────────────────────────────────────────────────
FROM code AS django-server

EXPOSE 8013
ENV PORT=8013
CMD ["sh", "-c", "exec granian --interface wsgi --host 0.0.0.0 --port ${PORT:-8013} --workers 2 main.wsgi:application"]

FROM django-server AS production

COPY --from=node /src /src

# ─── Local-dev target (ol-infrastructure local-dev k8s/Tilt stack) ───────────
# Runtime user owns /src (live-synced source), plus dev deps (pytest, ipdb, …)
# and watchfiles for granian --reload.
FROM production AS local-dev

USER root
RUN chown -R mitodl:mitodl /src
USER mitodl

RUN --mount=type=cache,target=/opt/uv-cache,uid=1000,gid=1000 \
    uv sync --frozen --no-install-project

FROM code AS jupyter-notebook

RUN uv pip install --force-reinstall jupyter

USER mitodl

# ─── Development target (docker compose) ─────────────────────────────────────
FROM django-server AS development

RUN --mount=type=cache,target=/opt/uv-cache,uid=1000,gid=1000 \
    uv sync --frozen --no-install-project
