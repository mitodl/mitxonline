import logging
from celery import shared_task
from django.core.management import call_command

log = logging.getLogger(__name__)

@shared_task
def run_cleartokens():
    try:
        call_command("cleartokens")
        log.info("Successfully ran cleartokens management command.")
    except Exception as e:
        log.error(f"Error running cleartokens: {e}")
