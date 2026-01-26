import logging

from celery import shared_task
from django.core.management import call_command

log = logging.getLogger(__name__)

from oauth2_provider.models import clear_expired


@shared_task
def run_clear_tokens():
    try:
        clear_expired()
        log.info("Successfully ran cleartokens management command.")
    except Exception:
        log.exception("Error running cleartokens")
