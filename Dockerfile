FROM python:3.9.18 as base
LABEL maintainer "ODL DevOps <mitx-devops@mit.edu>"

# Add package files, install updated node and pip
WORKDIR /tmp

# Install packages and add repo needed for postgres 9.6
COPY apt.txt /tmp/apt.txt
RUN apt-get update
RUN apt-get install -y $(grep -vE "^\s*#" apt.txt  | tr "\n" " ")

# pip
RUN curl --silent --location https://bootstrap.pypa.io/get-pip.py | python3 -

# Add, and run as, non-root user.
RUN mkdir /app
RUN adduser --disabled-password --gecos "" mitodl
RUN mkdir /var/media && chown -R mitodl:mitodl /var/media

# Poetry env configuration
ENV  \
  # poetry:
  POETRY_VERSION=1.5.1 \
  POETRY_VIRTUALENVS_CREATE=false \
  POETRY_CACHE_DIR='/tmp/cache/poetry' \
  POETRY_HOME='/home/mitodl/.local' \
  VIRTUAL_ENV="/opt/venv"
ENV PATH="$VIRTUAL_ENV/bin:$POETRY_HOME/bin:$PATH"

# Install project packages
COPY pyproject.toml /app
COPY poetry.lock /app
RUN chown -R mitodl:mitodl /app
RUN mkdir ${VIRTUAL_ENV} && chown -R mitodl:mitodl ${VIRTUAL_ENV}

USER mitodl
RUN curl -sSL https://install.python-poetry.org \
  | \
  POETRY_VERSION=${POETRY_VERSION} \
  POETRY_HOME=${POETRY_HOME} \
  python3 -q
# Add project
COPY . /app
WORKDIR /app
RUN python3 -m venv $VIRTUAL_ENV
RUN poetry install

USER root
RUN apt-get clean && apt-get purge

# Set pip cache folder, as it is breaking pip when it is on a shared volume
ENV XDG_CACHE_HOME /tmp/.cache

FROM base as django

USER mitodl

FROM base as django-server

EXPOSE 8013
ENV PORT 8013
CMD uwsgi uwsgi.ini

FROM base as jupyter-notebook

RUN pip install --force-reinstall jupyter

USER mitodl
