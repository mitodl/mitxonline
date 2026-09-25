"""Courseware tasks"""

import logging
import random

import celery
from django.conf import settings
from django.core.cache import cache
from edx_api.course_runs.exceptions import CourseRunAPIError
from mitol.common.utils.collections import chunks
from requests.exceptions import HTTPError, RequestException

from main.celery import app
from openedx import api
from openedx.exceptions import OpenEdXOAuth2Error
from openedx.models import CourseRunClone
from users.api import get_user_by_id
from users.models import User

log = logging.getLogger()

# Longer than one clone attempt (the edX clone call plus pushing run data and
# modes). If a worker dies holding it, the next delivery waits this long.
CLONE_COURSERUN_LOCK_TIMEOUT = 3600


def get_clone_courserun_retry_countdown(current_retry: int) -> int:
    """Return the countdown in seconds for the next clone retry attempt."""

    attempt_number = current_retry + 1
    base_delay = settings.OPENEDX_COURSE_CLONE_RETRY_DELAY * attempt_number
    jitter = random.randint(0, settings.OPENEDX_COURSE_CLONE_RETRY_JITTER)  # noqa: S311

    return base_delay + jitter


@app.task(acks_late=True)
def create_user_from_id(user_id):
    """Loads user by id and calls the API method to create the user in edX"""
    user = get_user_by_id(user_id)
    api.create_user(user)


# To be removed after this has been deployed in all envs
@app.task()
def create_edx_user_from_id(user_id):
    """Backwards-compatibility for celery to forward to the new task name"""
    create_user_from_id.delay(user_id)


@app.task(acks_late=True)
def retry_failed_edx_enrollments():
    """Retries failed edX enrollments"""
    successful_enrollments = api.retry_failed_edx_enrollments()
    return [
        (enrollment.user.email, enrollment.run.courseware_id)
        for enrollment in successful_enrollments
    ]


@app.task(acks_late=True)
def repair_faulty_openedx_users():
    """Calls the API method to repair faulty openedx users"""
    if settings.DISABLE_USER_REPAIR_TASK:
        log.info("Skipping repair_faulty_openedx_users task as it is disabled")
        return
    api.repair_all_faulty_openedx_users()


@app.task(bind=True)
def repair_faulty_openedx_users_parallel(self):
    """Repair a set of users in parallel"""

    chunked_tasks = [
        repair_faulty_openedx_users_chunk.s(list(user_ids[0]))
        for user_ids in chunks(
            User.faulty_openedx_users.user_ids_with_grace_period(),
            chunk_size=1000,
        )
    ]
    raise self.replace(celery.group(chunked_tasks))


@app.task(acks_late=True)
def repair_faulty_openedx_users_chunk(user_ids):
    """Sync a group of users"""
    users = User.objects.filter(id__in=user_ids)
    api.repair_faulty_openedx_users(users)


@app.task(acks_late=True)
def regenerate_openedx_auth_tokens(user_id):
    """Calls the API method to repair A faulty Open edX user"""
    user = User.objects.get(id=user_id)
    api.create_edx_auth_token(user)
    return user.email


@app.task(acks_late=True)
def change_edx_user_email_async(user_id):
    """
    Task to change edX user email in the background to avoid database level locks
    """
    user = User.objects.get(id=user_id)
    api.update_edx_user_email(user)


@app.task(acks_late=True)
def change_edx_user_name_async(user_id):
    """
    Task to change edX user name in the background to avoid database level locks
    """
    user = User.objects.get(id=user_id)
    api.update_edx_user_name(user)


@app.task(acks_late=True)
def update_edx_user_profile(user_id):
    """
    Task to update the edX user profile. This doesn't change the name or email.
    """
    user = User.objects.get(id=user_id)
    api.update_edx_user_profile(user)


@app.task(
    bind=True,
    acks_late=True,
    max_retries=settings.OPENEDX_COURSE_CLONE_MAX_RETRIES,
)
def clone_courserun(self, target_id: int, base_key: str):
    """
    Queue call to clone an existing course run.

    Every attempt is recorded on the run's CourseRunClone, which is created
    here if whoever queued the task did not create it.

    acks_late means a message can be delivered twice, so attempts for one run
    are serialized on a cache lock. A delivery that finds the lock held leaves
    the record alone: the attempt holding it will record the outcome. The
    record is loaded after the lock is taken, so the clone_requested_at check
    in process_course_run_clone sees the previous attempt's stamp.
    """

    from courses.models import CourseRun  # noqa: PLC0415

    lock_key = f"clone_courserun_lock:{target_id}"
    if not cache.add(lock_key, self.request.id, timeout=CLONE_COURSERUN_LOCK_TIMEOUT):
        log.info(
            "clone_courserun already running for course run %s, skipping this delivery",
            target_id,
        )
        return

    try:
        _clone_courserun_attempt(
            self, CourseRun.all_objects.get(pk=target_id), base_key
        )
    finally:
        cache.delete(lock_key)


def _clone_courserun_attempt(task, target_course, base_key: str):
    """Run one clone attempt for clone_courserun while it holds the run's lock."""

    clone, _ = CourseRunClone.objects.get_or_create(
        course_run=target_course, defaults={"source_courseware_id": base_key}
    )
    clone.start_attempt()

    try:
        api.process_course_run_clone(target_course, base_key, clone=clone)
    except (
        CourseRunAPIError,
        HTTPError,
        OpenEdXOAuth2Error,
        RequestException,
    ) as exc:
        retry_count = getattr(task.request, "retries", 0)
        attempt_number = retry_count + 1

        if retry_count >= task.max_retries:
            clone.mark_error(exc, final=True)
            log.exception(
                "clone_courserun exhausted retries for target=%s base=%s after "
                "%s attempts",
                target_course.readable_id,
                base_key,
                attempt_number,
            )
            raise

        clone.mark_error(exc, final=False)
        countdown = get_clone_courserun_retry_countdown(retry_count)

        log.warning(
            "Retrying clone_courserun for target=%s base=%s after %s seconds "
            "because the Open edX clone request failed on attempt %s/%s: %s",
            target_course.readable_id,
            base_key,
            countdown,
            attempt_number,
            task.max_retries + 1,
            exc,
        )
        raise task.retry(exc=exc, countdown=countdown) from exc
    except Exception as exc:
        clone.mark_error(exc, final=True)
        raise

    clone.mark_cloned()
