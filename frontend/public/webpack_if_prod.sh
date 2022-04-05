#!/bin/bash
set -ef -o pipefail
if [[ "$NODE_ENV" != "" && "$NODE_ENV" != "development" ]]
then
    npx webpack --config webpack.config.prod.js --bail
fi