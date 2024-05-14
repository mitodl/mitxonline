#!/usr/bin/env bash
#
# This script runs the refine devserver, or runs a build, dependent on NODE_ENV
set -e

yarn workspace mitx-online-staff-dashboard install --immutable

# craco will fail if we try to run the devserver in production mode
if [[ $NODE_ENV == "production" ]]; then
	yarn workspace mitx-online-staff-dashboard run build
	./scripts/http-ok.js
else
	yarn workspace mitx-online-staff-dashboard run dev
fi
