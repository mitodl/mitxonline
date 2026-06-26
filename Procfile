release: bash scripts/heroku-release-phase.sh
web: bin/start-nginx bin/start-pgbouncer newrelic-admin run-program granian --interface wsgi --host 0.0.0.0 --port 8013 --workers 2 main.wsgi:application
worker: bin/start-pgbouncer newrelic-admin run-program celery -A main.celery:app worker -E -Q hubspot_sync,celery -B -l $MITX_ONLINE_LOG_LEVEL
extra_worker: bin/start-pgbouncer newrelic-admin run-program celery -A main.celery:app worker -E -Q hubspot_sync,celery -l $MITX_ONLINE_LOG_LEVEL
