import logging
from django.core.cache import cache
from mitol.google_sheets_deferrals.api import DeferralRequestHandler
from mitol.google_sheets_refunds.api import RefundRequestHandler

from main.celery import app

log = logging.getLogger(__name__)

LOCK_EXPIRE = 60 * 10  # Lock expires in 10 minutes

@contextmanager
def memcache_lock(lock_id, oid):
    timeout_at = time.monotonic() + LOCK_EXPIRE - 3
    # cache.add fails if the key already exists
    status = cache.add(lock_id, oid, LOCK_EXPIRE)
    try:
        yield status
    finally:
        # memcache delete is very slow, but we have to use it to take
        # advantage of using add() for atomic locking
        if time.monotonic() < timeout_at and status:
            # don't release the lock if we exceeded the timeout
            # to lessen the chance of releasing an expired lock
            # owned by someone else
            # also don't release the lock if we didn't acquire it
            cache.delete(lock_id)

@app.task(bind=True)
def process_google_sheets_requests():
    """
    Task to process refund and deferral requests from Google sheets
    """
    feed_url_hexdigest = md5(feed_url).hexdigest()
    lock_id = '{0}-lock-{1}'.format(self.name, feed_url_hexdigest)
    logger.debug('Importing feed: %s', feed_url)
    with memcache_lock(lock_id, self.app.oid) as acquired:
        if acquired:
            return Feed.objects.import_feed(feed_url).url
    logger.debug(
        'Feed %s is already being imported by another worker', feed_url)
    refund_request_handler = RefundRequestHandler()
    deferral_request_handler = DeferralRequestHandler()
    if refund_request_handler.is_configured():
        refund_request_handler.process_sheet()

    if deferral_request_handler.is_configured():
        deferral_request_handler.process_sheet()
