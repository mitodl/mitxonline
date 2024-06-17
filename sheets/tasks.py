import logging
from django.core.cache import cache
from mitol.google_sheets_deferrals.api import DeferralRequestHandler
from mitol.google_sheets_refunds.api import RefundRequestHandler

from main.celery import app
from redis import Redis
from django.conf import settings

log = logging.getLogger(__name__)


@app.task(bind=True)
def process_google_sheets_requests(self):
    """
    Task to process refund and deferral requests from Google sheets
    """
    # revoke all previously scheduled tasks
    import time
    time.sleep(120)
    log.info(self.name)
    log.info(app.signature(self.name))


    redis_client = Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=3)
    print(redis_client.llen(app.default_app.conf.task_default_queue))


    import base64
    import json

    with app.pool.acquire(block=True) as conn:
        tasks = conn.default_channel.client.lrange('celery', 0, -1)
        print(tasks)

    decoded_tasks = []

    for task in tasks:
        j = json.loads(task)
        body = json.loads(base64.b64decode(j['body']))
        decoded_tasks.append(body)

    print(decoded_tasks)
    query = app.events.state.tasks_by_type(self.name)
    for uuid, task in query:
        app.control.revoke(uuid)

    refund_request_handler = RefundRequestHandler()
    deferral_request_handler = DeferralRequestHandler()
    if refund_request_handler.is_configured():
        refund_request_handler.process_sheet()

    if deferral_request_handler.is_configured():
        deferral_request_handler.process_sheet()
