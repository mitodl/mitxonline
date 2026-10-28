# syntax=docker/dockerfile:1
# hadolint global ignore=DL3008

FROM mitodl/ol-python-base:3.11 AS base
LABEL maintainer="ODL DevOps <mitx-devops@mit.edu>"

# App-specific apt extras; common-core packages are in mitodl/ol-python-base:3.11.
# Operator tooling (htop, ngrep, screen, etc.) is also kept here for parity
# with the production image; trim this list if the production image diverges.
#
# The DHI base ships a stripped /etc/group and no update-rc.d, and screen's
# postinst needs both: it creates /run/screen as group `utmp` and registers
# its init script. Create the group (guarded, in case the base restores it)
# and install init-system-helpers so the postinst succeeds.
#
# Don't add -dev packages that depend on `python3` (e.g. libcairo2-dev via
# libglib2.0-dev-bin): DHI's python3 is 3.13, so apt replaces the base
# image's 3.11 interpreter and `uv sync` fails with "No interpreter found".
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    (getent group utmp >/dev/null || groupadd --system utmp) && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
      dnsutils \
      htop \
      init-system-helpers \
      iputils-ping \
      less \
      lsof \
      nano \
      ngrep \
      procps \
      screen \
      wget

FROM base AS deps

# Trusted certs (org PKI + local-dev mkcert root injected at deploy time).
# No COPY --chmod here: BuildKit applies it to directories too, leaving
# /usr/local/share untraversable by mitodl (perl, and so pg_config, then fails).
COPY certs/ /usr/local/share/ca-certificates/
RUN find /usr/local/share/ca-certificates -type f -exec chmod 644 {} + && \
    update-ca-certificates

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
