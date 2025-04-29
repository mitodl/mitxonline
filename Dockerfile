FROM python:3.10.16-slim AS base

LABEL maintainer "ODL DevOps <mitx-devops@mit.edu>"

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

FROM system AS poetry

# Poetry env configuration
ENV  \
  # poetry:
  PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  POETRY_VERSION=1.8.5 \
  POETRY_VIRTUALENVS_CREATE=false \
  POETRY_CACHE_DIR='/tmp/cache/poetry' \
  POETRY_HOME='/home/mitodl/.local' \
  VIRTUAL_ENV="/opt/venv"
ENV PATH="$VIRTUAL_ENV/bin:$POETRY_HOME/bin:$PATH"

RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

COPY pyproject.toml /src
COPY poetry.lock /src
COPY mitol_*.gz /src

RUN chown -R mitodl:mitodl /src && \
    mkdir ${VIRTUAL_ENV} && chown -R mitodl:mitodl ${VIRTUAL_ENV}

USER mitodl
RUN curl -sSL https://install.python-poetry.org \
  | \
  POETRY_VERSION=${POETRY_VERSION} \
  POETRY_HOME=${POETRY_HOME} \
  python3 -q
WORKDIR /src
RUN python3 -m venv $VIRTUAL_ENV
RUN poetry install


FROM poetry as code

COPY . /src
WORKDIR /src

# Set pip cache folder, as it is breaking pip when it is on a shared volume
ENV XDG_CACHE_HOME /tmp/.cache

FROM node:17.9 as node

COPY --from=code /src /src
WORKDIR /src

RUN yarn workspace mitx-online-public install --immutable && \ 
    yarn workspace mitx-online-public run build

FROM code as django-server

EXPOSE 8013
ENV PORT 8013
CMD uwsgi uwsgi.ini

FROM django-server as production

copy --from=node /src /src

FROM code as jupyter-notebook

RUN pip install --force-reinstall jupyter

USER mitodl
