#!/usr/bin/env bash
#
# This script runs the react devserver, or runs a build, dependent on NODE_ENV
set -e

yarn workspace mitx-online-public install --immutable 

if [[ $NODE_ENV == "production" ]] ; then
    yarn workspace mitx-online-public run build
    echo "Production build complete"
    ./scripts/http-ok.sh
else
    yarn workspace mitx-online-public run dev-server --port 8012
fi
