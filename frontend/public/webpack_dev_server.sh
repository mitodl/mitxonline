#!/bin/bash
set -ef -o pipefail

if [[ "$1" == "--install" ]] ; then
pushd ../../
yarn install --immutable && echo "Finished yarn install"
popd
fi
# Start the webpack dev server on the appropriate host and port
yarn workspace mitx-online-public run dev-server
