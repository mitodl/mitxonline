"""Tests for hubspot_sync.task_helpers"""

import pytest
import reversion
from django.contrib.contenttypes.models import ContentType
from mitol.hubspot_api.api import HubspotObjectType
from mitol.hubspot_api.factories import HubspotObjectFactory
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
    sync_hubspot_users_batch,
)
from users.factories import UserFactory
from users.models import User

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


def test_sync_hubspot_users_batch(mocker, settings):
    """sync_hubspot_users_batch should split users into batch create/update tasks"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "faketoken"  # noqa: S105
    mock_batch = mocker.patch(
        "hubspot_sync.task_helpers.tasks.batch_upsert_hubspot_objects.delay"
    )
    synced_users = UserFactory.create_batch(2)
    unsynced_users = UserFactory.create_batch(2)
    content_type = ContentType.objects.get_for_model(User)
    for user in synced_users:
        HubspotObjectFactory.create(
            content_type=content_type, object_id=user.id, content_object=user
        )

    sync_hubspot_users_batch(
        [user.id for user in synced_users + unsynced_users],
    )

    assert mock_batch.call_count == 2
    mock_batch.assert_any_call(
        HubspotObjectType.CONTACTS.value,
        "user",
        "users",
        create=True,
        object_ids=[user.id for user in unsynced_users],
    )
    mock_batch.assert_any_call(
        HubspotObjectType.CONTACTS.value,
        "user",
        "users",
        create=False,
        object_ids=[user.id for user in synced_users],
    )


def test_sync_hubspot_users_batch_skips_b2b_users(mocker, settings):
    """sync_hubspot_users_batch should exclude B2B users from the batch"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "faketoken"  # noqa: S105
    mock_batch = mocker.patch(
        "hubspot_sync.task_helpers.tasks.batch_upsert_hubspot_objects.delay"
    )
    user = UserFactory.create()
    b2b_user = UserFactory.create()
    b2b_user.b2b_contracts.add(ContractPageFactory.create())

    sync_hubspot_users_batch([user.id, b2b_user.id])

    mock_batch.assert_called_once_with(
        HubspotObjectType.CONTACTS.value,
        "user",
        "users",
        create=True,
        object_ids=[user.id],
    )


def test_sync_hubspot_users_batch_all_b2b(mocker, settings):
    """sync_hubspot_users_batch should dispatch nothing when all users are B2B"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "faketoken"  # noqa: S105
    mock_batch = mocker.patch(
        "hubspot_sync.task_helpers.tasks.batch_upsert_hubspot_objects.delay"
    )
    b2b_user = UserFactory.create()
    b2b_user.b2b_contracts.add(ContractPageFactory.create())

    sync_hubspot_users_batch([b2b_user.id])

    mock_batch.assert_not_called()


@pytest.mark.parametrize("user_ids", [None, [], set()])
def test_sync_hubspot_users_batch_no_users(mocker, settings, user_ids):
    """sync_hubspot_users_batch should be a no-op with no user ids"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = "faketoken"  # noqa: S105
    mock_batch = mocker.patch(
        "hubspot_sync.task_helpers.tasks.batch_upsert_hubspot_objects.delay"
    )
    sync_hubspot_users_batch(user_ids)
    mock_batch.assert_not_called()


def test_sync_hubspot_users_batch_no_token(mocker, settings):
    """sync_hubspot_users_batch should be a no-op without a HubSpot token"""
    settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN = None
    mock_batch = mocker.patch(
        "hubspot_sync.task_helpers.tasks.batch_upsert_hubspot_objects.delay"
    )
    sync_hubspot_users_batch([UserFactory.create().id])
    mock_batch.assert_not_called()


def test_sync_hubspot_users_batch_logs_exception(mocker, mock_exception_log):
    """sync_hubspot_users_batch should log exceptions from task dispatch"""
    mocker.patch(
        "hubspot_sync.task_helpers.tasks.batch_upsert_hubspot_objects.delay",
        side_effect=ConnectionError,
    )
    user = UserFactory.create()

    sync_hubspot_users_batch([user.id])

    mock_exception_log.assert_called_once_with(
        "Exception calling batch_upsert_hubspot_objects for %d user(s)", 1
    )


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
