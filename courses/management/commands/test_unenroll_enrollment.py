"""Tests for Unenroll Enrollment management command"""

import pytest

from django.core.management.base import CommandError
from types import SimpleNamespace

from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.factories import (
    CourseRunFactory,
    CourseRunEnrollmentFactory,
)
from courses.management.commands import unenroll_enrollment
from ecommerce.models import Order
from users.factories import UserFactory
from ecommerce.factories import LineFactory, OrderFactory, ProductFactory
import reversion
from reversion.models import Version

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def patches(mocker):  # pylint: disable=missing-docstring
    edx_unenroll = mocker.patch("courses.api.unenroll_edx_course_run")
    log_exception = mocker.patch("courses.api.log.exception")
    sync_line_item_with_hubspot = mocker.patch(
        "hubspot_sync.api.sync_line_item_with_hubspot"
    )
    return SimpleNamespace(
        edx_unenroll=edx_unenroll,
        log_exception=log_exception,
        sync_line_item_with_hubspot=sync_line_item_with_hubspot,
    )


def test_unenroll_enrollment_no_argument():
    """Test that command throws error when no input is provided"""

    with pytest.raises(CommandError) as command_error:
        unenroll_enrollment.Command().handle()
    assert str(command_error.value) == "Could not find a user with <username or email>="


def test_unenroll_enrollment_invalid_run():
    """
    Test that unenroll_enrollment management command throws proper error when
    no valid course run is supplied
    """

    test_user = UserFactory.create()
    with pytest.raises(CommandError) as command_error:
        unenroll_enrollment.Command().handle(user=test_user.username)
    assert str(
        command_error.value
    ) == "Could not find course run with courseware_id={}".format(None)

    with pytest.raises(CommandError) as command_error:
        unenroll_enrollment.Command().handle(user=test_user.username, run="test")
    assert (
        str(command_error.value) == "Could not find course run with courseware_id=test"
    )


def test_unenroll_enrollment_invalid_user():
    """Test that the command throws proper error when user is invalid arguments"""
    run = CourseRunFactory.create()

    with pytest.raises(CommandError) as command_error:
        unenroll_enrollment.Command().handle(
            user="test",
            run=run.courseware_id,
        )
    assert (
        str(command_error.value)
        == "Could not find a user with <username or email>=test"
    )


def test_unenroll_enrollment(patches):
    """
    Test that user unenrolled from the course properly
    """
    enrollment = CourseRunEnrollmentFactory.create(edx_enrolled=True)
    with reversion.create_revision():
        product = ProductFactory.create(purchasable_object=enrollment.run)
    version = Version.objects.get_for_object(product).first()
    order = OrderFactory.create(state=Order.STATE.PENDING, purchaser=enrollment.user)
    LineFactory.create(
        order=order, purchased_object=enrollment.run, product_version=version
    )
    assert enrollment.change_status is None
    assert enrollment.active is True
    assert enrollment.edx_enrolled is True
    unenroll_enrollment.Command().handle(
        run=enrollment.run.courseware_id,
        user=enrollment.user.username,
    )
    patches.edx_unenroll.assert_called_once_with(enrollment)
    patches.sync_line_item_with_hubspot.assert_called_once()
    enrollment.refresh_from_db()
    assert enrollment.change_status == ENROLL_CHANGE_STATUS_UNENROLLED
    assert enrollment.active is False
    assert enrollment.edx_enrolled is False


def test_unenroll_enrollment_without_edx(mocker):
    """
    Test that user unenrolled from the course properly without edx
    """
    enrollment = CourseRunEnrollmentFactory.create(edx_enrolled=True)
    with reversion.create_revision():
        product = ProductFactory.create(purchasable_object=enrollment.run)
    version = Version.objects.get_for_object(product).first()
    order = OrderFactory.create(state=Order.STATE.PENDING, purchaser=enrollment.user)
    LineFactory.create(
        order=order, purchased_object=enrollment.run, product_version=version
    )
    sync_line_item_with_hubspot = mocker.patch(
        "hubspot_sync.api.sync_line_item_with_hubspot"
    )
    assert enrollment.change_status is None
    assert enrollment.active is True
    assert enrollment.edx_enrolled is True
    # User will not be unenrolled
    # Unenrolling without mocker and keep_failed_enrollments argument
    unenroll_enrollment.Command().handle(
        run=enrollment.run.courseware_id,
        user=enrollment.user.username,
    )
    enrollment.refresh_from_db()
    # Enrollment will remain as it is
    assert enrollment.change_status is None
    assert enrollment.active is True
    assert enrollment.edx_enrolled is True
    # User will not unenrolled
    # Unenrolling with keep_failed_enrollments argument
    unenroll_enrollment.Command().handle(
        run=enrollment.run.courseware_id,
        user=enrollment.user.username,
        keep_failed_enrollments=True,
    )
    enrollment.refresh_from_db()
    assert enrollment.change_status == ENROLL_CHANGE_STATUS_UNENROLLED
    assert enrollment.active is False
    # Enrollment will remain edx_enrolled
    assert enrollment.edx_enrolled is True
    sync_line_item_with_hubspot.assert_called_once()
