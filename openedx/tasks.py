"""Courseware tasks"""

import logging

import celery
from django.conf import settings
from mitol.common.utils.collections import chunks

from main.celery import app
from openedx import api
from users.api import get_user_by_id
from users.models import User

log = logging.getLogger()


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


@app.task
def clone_courserun(target_id: int, *, base_id: int | str | None = None):
    """Queue call to clone an existing course run."""

    api.process_course_run_clone(target_id, base_id=base_id)
