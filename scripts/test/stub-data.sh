#!/usr/bin/env bash

SCRIPTPATH="$(
	cd -- "$(dirname "$0")" >/dev/null 2>&1 || exit 1
	pwd -P
)"

SRC="${SCRIPTPATH}/data/*"
DEST=$(dirname $SCRIPTPATH | xargs dirname)

# Copy static stub data for tests
cp -R $SRC $DEST
