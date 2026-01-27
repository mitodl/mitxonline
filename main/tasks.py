import logging

from celery import shared_task
from oauth2_provider.models import clear_expired

log = logging.getLogger(__name__)


@shared_task
def run_clear_tokens():
    try:
        clear_expired()
        log.info("Successfully ran cleartokens management command.")
    except Exception:
        log.exception("Error running cleartokens")
