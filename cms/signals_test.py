"""Tests for cms.signals"""

from unittest.mock import patch

import factory
import pytest
from django.db.models.signals import post_save

from cms.factories import CoursePageFactory, ProgramPageFactory, ResourcePageFactory

pytestmark = pytest.mark.django_db

LEARN_SERVICE_ID = "test-learn-service-id"


@pytest.fixture
def learn_service_id(settings):
    """Point the purge at a known MIT Learn Fastly service."""
    settings.MIT_LEARN_FASTLY_SERVICE_ID = LEARN_SERVICE_ID
    return settings.MIT_LEARN_FASTLY_SERVICE_ID


@patch("cms.signals.transaction.on_commit", side_effect=lambda callback: callback())
@patch("cms.tasks.queue_fastly_surrogate_key_purge.delay")
def test_purge_fastly_cache_on_publish_course_page(
    mock_purge_delay, mock_on_commit, learn_service_id
):
    """Publishing a CoursePage purges the key for its course."""
    course_page = CoursePageFactory.create()
    mock_purge_delay.reset_mock()

    # Publishing saves the Course as well, which purges the same key via its own
    # post_save receiver; mute post_save so only the publish path is counted.
    # This mutes every post_save receiver, Wagtail's index updates included, so
    # the publish is not a fully faithful one -- adequate for these assertions.
    with factory.django.mute_signals(post_save):
        course_page.save_revision().publish()

    mock_purge_delay.assert_called_once_with(
        f"mitxonline:course:{course_page.course.readable_id}", learn_service_id
    )


@patch("cms.signals.transaction.on_commit", side_effect=lambda callback: callback())
@patch("cms.tasks.queue_fastly_surrogate_key_purge.delay")
def test_purge_fastly_cache_on_publish_program_page(
    mock_purge_delay, mock_on_commit, learn_service_id
):
    """Publishing a ProgramPage purges the key for its program."""
    program_page = ProgramPageFactory.create()
    mock_purge_delay.reset_mock()

    with factory.django.mute_signals(post_save):
        program_page.save_revision().publish()

    mock_purge_delay.assert_called_once_with(
        f"mitxonline:program:{program_page.program.readable_id}", learn_service_id
    )


@patch("cms.signals.transaction.on_commit", side_effect=lambda callback: callback())
@patch("cms.tasks.queue_fastly_surrogate_key_purge.delay")
def test_purge_fastly_cache_on_publish_ignores_other_pages(
    mock_purge_delay, mock_on_commit
):
    """Publishing a page that is not a product page purges nothing."""
    resource_page = ResourcePageFactory.create()
    mock_purge_delay.reset_mock()

    # A ResourcePage has no Course or Program, so there is no post_save purge to
    # suppress here; muted only to keep the three tests the same shape.
    with factory.django.mute_signals(post_save):
        resource_page.save_revision().publish()

    mock_purge_delay.assert_not_called()
