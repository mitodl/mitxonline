#!/usr/bin/env bash
#
# This script runs the django app, waiting on the react applications to build

python3 manage.py collectstatic --noinput --clear
python3 manage.py migrate --noinput
python3 manage.py configure_wagtail

health_urls=(
	"http://watch:8012/health"
	"http://refine:8016/health"
)
wait_time=300

# kick off healthchecks as background tasks so they can check concurrently
for url in "${health_urls[@]}"; do
	echo "Waiting on: ${url}"
	./scripts/wait-for.sh ${url} --timeout ${wait_time} -- echo "${url} is available"

	if [[ $? -ne 0 ]]; then
		echo "Service at ${url} failed to start"
		exit 1
	fi
done

uwsgi uwsgi.ini --honour-stdin
