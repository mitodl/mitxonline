"""Tests for hubspot_sync.task_helpers"""

import pytest
import reversion
from reversion.models import Version

from b2b.factories import ContractPageFactory
from courses.factories import CourseRunFactory, ProgramEnrollmentFactory, ProgramFactory
from courses.models import ProgramRequirementNodeType
from ecommerce.factories import LineFactory, OrderFactory, ProductFactory
from hubspot_sync.task_helpers import (
    sync_hubspot_cart_add,
    sync_hubspot_deal,
    sync_hubspot_product,
    sync_hubspot_user,
)
from users.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_exception_log(settings, mocker):
    """Return a mocked log.exception object"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "faketoken"  # noqa: S105
    return mocker.patch("hubspot_sync.task_helpers.log.exception")


@pytest.mark.parametrize("raise_exc", [True, False])
def test_sync_hubspot_deal_uai_order_with_uai_token(
    mocker, mock_exception_log, hubspot_order, raise_exc, settings
):
    """sync_hubspot_deal should use UAI token for UAI orders when available"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "regular-token"  # noqa: S105
    settings.UAI_MITOL_HUBSPOT_API_PRIVATE_TOKEN = "uai-token"  # noqa: S105

    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_deal_with_hubspot_targeted.apply_async",
        side_effect=(ConnectionError if raise_exc else None),
    )
    mocker.patch("hubspot_sync.task_helpers.is_uai_order", return_value=True)

    sync_hubspot_deal(hubspot_order)
    mock_sync.assert_called_once_with(
        args=(hubspot_order.id,), kwargs={"is_uai": True}, countdown=10
    )

    if raise_exc:
        mock_exception_log.assert_called_once_with(
            "Exception calling sync_deal_with_hubspot_targeted for order %d",
            hubspot_order.id,
        )
    else:
        mock_exception_log.assert_not_called()


@pytest.mark.parametrize("raise_exc", [True, False])
def test_sync_hubspot_deal_non_uai_order(
    mocker, mock_exception_log, hubspot_order, raise_exc, settings
):
    """sync_hubspot_deal should use regular token for non-UAI orders"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "regular-token"  # noqa: S105
    settings.UAI_MITOL_HUBSPOT_API_PRIVATE_TOKEN = "uai-token"  # noqa: S105

    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_deal_with_hubspot_targeted.apply_async",
        side_effect=(ConnectionError if raise_exc else None),
    )
    mocker.patch("hubspot_sync.task_helpers.is_uai_order", return_value=False)

    sync_hubspot_deal(hubspot_order)
    mock_sync.assert_called_once_with(
        args=(hubspot_order.id,), kwargs={"is_uai": False}, countdown=10
    )

    if raise_exc:
        mock_exception_log.assert_called_once_with(
            "Exception calling sync_deal_with_hubspot_targeted for order %d",
            hubspot_order.id,
        )
    else:
        mock_exception_log.assert_not_called()


@pytest.mark.parametrize("raise_exc", [True, False])
def test_sync_hubspot_user(mocker, mock_exception_log, user, raise_exc):
    """sync_hubspot_user should call tasks.sync_contact_with_hubspot.delay and log any exception"""
    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_contact_with_hubspot.delay",
        side_effect=(ConnectionError if raise_exc else None),
    )
    sync_hubspot_user(user)
    mock_sync.assert_called_once_with(user.id)
    if raise_exc:
        mock_exception_log.assert_called_once_with(
            "Exception calling sync_contact_with_hubspot for user %s", user.edx_username
        )
    else:
        mock_exception_log.assert_not_called()


def test_sync_hubspot_user_skips_b2b_users(mocker, settings):
    """sync_hubspot_user should skip B2B users and not call HubSpot sync"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "faketoken"  # noqa: S105

    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_contact_with_hubspot.delay"
    )
    mock_info_log = mocker.patch("hubspot_sync.task_helpers.log.info")

    user = UserFactory.create()
    contract = ContractPageFactory.create()
    user.b2b_contracts.add(contract)

    # Reset mocks after user creation to clear any calls during setup
    mock_sync.reset_mock()
    mock_info_log.reset_mock()

    sync_hubspot_user(user)

    # Should not call the sync task
    mock_sync.assert_not_called()

    # Should log that user was skipped
    mock_info_log.assert_called_once_with(
        "Skipping HubSpot sync for B2B user %s (user_id=%d)",
        user.edx_username,
        user.id,
    )


def test_sync_hubspot_user_syncs_regular_users(mocker, settings):
    """sync_hubspot_user should sync regular users (without B2B contracts)"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "faketoken"  # noqa: S105

    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_contact_with_hubspot.delay"
    )
    mock_info_log = mocker.patch("hubspot_sync.task_helpers.log.info")

    # Create a regular user without any B2B contracts
    user = UserFactory.create()

    # Reset mocks after user creation to ignore any calls during setup
    mock_sync.reset_mock()
    mock_info_log.reset_mock()

    # Call the function we're actually testing
    sync_hubspot_user(user)

    # Should call the sync task
    mock_sync.assert_called_once_with(user.id)

    # Should not log anything about B2B users
    mock_info_log.assert_not_called()

    # Should not log any skip message
    mock_info_log.assert_not_called()


@pytest.mark.parametrize("raise_exc", [True, False])
def test_sync_hubspot_product(mocker, mock_exception_log, raise_exc):
    """sync_hubspot_product should call tasks.sync_product_with_hubspot.delay and log any exception"""
    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_product_with_hubspot.delay",
        side_effect=(ConnectionError if raise_exc else None),
    )
    product = ProductFactory.build()
    sync_hubspot_product(product)
    mock_sync.assert_called_once_with(product.id)
    if raise_exc:
        mock_exception_log.assert_called_once_with(
            "Exception calling sync_product_with_hubspot for product %d", product.id
        )
    else:
        mock_exception_log.assert_not_called()


def test_sync_hubspot_deal_skips_for_course_in_enrolled_program(mocker, settings):
    """sync_hubspot_deal should skip if the order is for a course run in a program the user is enrolled in."""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "faketoken"  # noqa: S105

    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_deal_with_hubspot_targeted.apply_async"
    )
    mocker.patch("hubspot_sync.task_helpers.is_uai_order", return_value=False)

    course_run = CourseRunFactory.create()
    program = ProgramFactory.create()
    program.requirements_root.add_child(
        node_type=ProgramRequirementNodeType.COURSE,
        course=course_run.course,
    )

    with reversion.create_revision():
        product = ProductFactory.create(purchasable_object=course_run)

    order = OrderFactory.create()
    LineFactory.create(
        order=order,
        product_version=Version.objects.get_for_object(product).first(),
        purchased_object=course_run,
    )
    ProgramEnrollmentFactory.create(user=order.purchaser, program=program)

    sync_hubspot_deal(order)

    mock_sync.assert_not_called()


def test_sync_hubspot_deal_proceeds_for_course_not_in_program(
    mocker, mock_exception_log, settings
):
    """sync_hubspot_deal should proceed if the order is for a course not in any program."""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "faketoken"  # noqa: S105

    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_deal_with_hubspot_targeted.apply_async"
    )
    mocker.patch("hubspot_sync.task_helpers.is_uai_order", return_value=False)

    course_run = CourseRunFactory.create()

    with reversion.create_revision():
        product = ProductFactory.create(purchasable_object=course_run)

    order = OrderFactory.create()
    LineFactory.create(
        order=order,
        product_version=Version.objects.get_for_object(product).first(),
        purchased_object=course_run,
    )

    sync_hubspot_deal(order)

    mock_sync.assert_called_once()


def test_sync_hubspot_deal_proceeds_when_not_enrolled_in_program(
    mocker, mock_exception_log, settings
):
    """sync_hubspot_deal should proceed if the user is not enrolled in the program containing this course."""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "faketoken"  # noqa: S105

    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_deal_with_hubspot_targeted.apply_async"
    )
    mocker.patch("hubspot_sync.task_helpers.is_uai_order", return_value=False)

    course_run = CourseRunFactory.create()
    program = ProgramFactory.create()
    program.requirements_root.add_child(
        node_type=ProgramRequirementNodeType.COURSE,
        course=course_run.course,
    )

    with reversion.create_revision():
        product = ProductFactory.create(purchasable_object=course_run)

    order = OrderFactory.create()
    LineFactory.create(
        order=order,
        product_version=Version.objects.get_for_object(product).first(),
        purchased_object=course_run,
    )
    # Intentionally do not enroll the user in the program

    sync_hubspot_deal(order)

    mock_sync.assert_called_once()


@pytest.mark.parametrize("raise_exc", [True, False])
def test_sync_hubspot_cart_add(mocker, mock_exception_log, user, raise_exc):
    """sync_hubspot_cart_add should call sync_cart_add_event_with_hubspot.apply_async and log any exception"""
    mock_sync = mocker.patch(
        "hubspot_sync.task_helpers.tasks.sync_cart_add_event_with_hubspot.apply_async",
        side_effect=(ConnectionError if raise_exc else None),
    )
    product = ProductFactory.build()
    sync_hubspot_cart_add(user, product, is_uai=True)
    mock_sync.assert_called_once_with(
        args=(user.id, product.id),
        kwargs={"is_uai_course": True},
        countdown=5,
    )
    if raise_exc:
        mock_exception_log.assert_called_once_with(
            "Exception calling sync_cart_add_event_with_hubspot for user %s and product %d",
            user.edx_username,
            product.id,
        )
    else:
        mock_exception_log.assert_not_called()
