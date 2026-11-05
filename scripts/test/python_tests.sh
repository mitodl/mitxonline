#!/usr/bin/env bash
set -e
set -o pipefail
status=0

echohighlight() {
	# shellcheck disable=SC2145
	echo -e "\x1b[32;1m$@\x1b[0m"
}

function run_test {
	# shellcheck disable=SC2145
	echohighlight "[TEST SUITE] $@"
	uv run "$@"
	local test_status=$?
	if [ $test_status -ne 0 ]; then
		status=$test_status
	fi
	return $status
}

run_test pytest "$@"

exit $status
