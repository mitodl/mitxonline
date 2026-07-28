"""Tests for cms.signals"""

from unittest.mock import patch

import pytest

from cms.factories import CoursePageFactory, ProgramPageFactory, ResourcePageFactory
from cms.signals import purge_fastly_cache_on_publish

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
    # Building the page saves a Course, which fires its own post_save purge.
    mock_purge_delay.reset_mock()

    purge_fastly_cache_on_publish(sender=None, instance=course_page)

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
    # Building the page saves a Program, which fires its own post_save purge.
    mock_purge_delay.reset_mock()

    purge_fastly_cache_on_publish(sender=None, instance=program_page)

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

    purge_fastly_cache_on_publish(sender=None, instance=resource_page)

    mock_purge_delay.assert_not_called()
