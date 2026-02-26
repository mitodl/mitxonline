#!/usr/bin/env bash
set -eo pipefail

TMPDIR="$(mktemp -d)"
SPECS_DIR=./openapi/specs/

uv run ./manage.py migrate --noinput
uv run ./manage.py generate_openapi_spec \
	--directory=$TMPDIR --fail-on-warn

diff $TMPDIR $SPECS_DIR

if [ $? -eq 0 ]; then
	echo "OpenAPI spec is up to date!"
	exit 0
else
	echo "OpenAPI spec is out of date. Please regenerate via ./manage.py generate_openapi_spec"
	exit 1
fi
