FROM python:3.14-slim AS base

LABEL maintainer="ODL DevOps <mitx-devops@mit.edu>"

# Add package files, install updated node and pip
WORKDIR /tmp

# Install packages and add repo needed for postgres 9.6
COPY apt.txt /tmp/apt.txt
RUN apt-get update && \
    apt-get install --no-install-recommends -y $(grep -vE "^\s*#" apt.txt  | tr "\n" " ") && \
    apt-get clean && \
    apt-get purge -y && \
    rm -rf /var/lib/apt-lists/*

FROM base AS system

# Add, and run as, non-root user.
RUN mkdir /src && \
    adduser --disabled-password --gecos "" mitodl && \
    mkdir /var/media && chown -R mitodl:mitodl /var/media

FROM system AS uv

# copy in trusted certs
COPY --chmod=644 certs/*.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates

# uv env configuration
ENV  \
  PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  UV_PROJECT_ENVIRONMENT="/opt/venv"
ENV PATH="/opt/venv/bin:$PATH"

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

COPY pyproject.toml /src
COPY uv.lock /src
COPY mitol_*.gz /src

RUN chown -R mitodl:mitodl /src && \
    mkdir -p /opt/venv && \
    chown -R mitodl:mitodl /opt/venv

USER mitodl
WORKDIR /src
RUN uv sync --frozen --no-install-project --group prod


FROM uv AS code

COPY . /src
WORKDIR /src

# Set pip cache folder, as it is breaking pip when it is on a shared volume
ENV XDG_CACHE_HOME=/tmp/.cache

FROM node:17.9 AS node

COPY --from=code /src /src
WORKDIR /src

ENV NODE_ENV=production
RUN yarn workspace mitx-online-public install --immutable && \
    yarn workspace mitx-online-public run build && \
    yarn workspace mitx-online-staff-dashboard install --immutable && \
    yarn workspace mitx-online-staff-dashboard run build

FROM code AS django-server

EXPOSE 8013
ENV PORT=8013
CMD ["uwsgi", "uwsgi.ini"]

FROM django-server AS production

COPY --from=node /src /src

FROM code AS jupyter-notebook

RUN uv pip install --force-reinstall jupyter

USER mitodl
