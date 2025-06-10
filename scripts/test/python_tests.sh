#!/usr/bin/env bash
status=0

echohighlight() {
	# shellcheck disable=SC2145
	echo -e "\x1b[32;1m$@\x1b[0m"
}

function run_test {
	# shellcheck disable=SC2145
	echohighlight "[TEST SUITE] $@"
	poetry run "$@"
	local test_status=$?
	if [ $test_status -ne 0 ]; then
		status=$test_status
	fi
	return $status
}

run_test ./scripts/test/detect_missing_migrations.sh
run_test ./scripts/test/no_auto_migrations.sh
run_test ./scripts/test/openapi_spec_check.sh
run_test pytest -n logical

exit $status
