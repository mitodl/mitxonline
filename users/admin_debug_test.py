"""Tests for the user debug screen in the Django Admin"""

import pytest
import reversion
from django.contrib.auth.models import Permission
from django.urls import reverse
from reversion.models import Version

from b2b.factories import (
    ContractPageFactory,
    OrganizationPageFactory,
    UserOrganizationFactory,
)
from b2b.models import UserB2BContract
from courses.factories import (
    CourseRunCertificateFactory,
    CourseRunEnrollmentFactory,
    ProgramCertificateFactory,
    ProgramEnrollmentFactory,
)
from ecommerce.factories import LineFactory, OrderFactory, ProductFactory
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.factories import FlexiblePriceFactory
from users.admin_debug import admin_change_url, get_user_debug_context
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


def _debug_url(user):
    return reverse("admin:users_user_debug", args=[user.pk])


def _add_line(order):
    """Add a line for a new product to the order"""

    with reversion.create_revision():
        product = ProductFactory.create()
    LineFactory.create(
        order=order,
        purchased_object=product.purchasable_object,
        product_version=Version.objects.get_for_object(product).last(),
    )


def test_admin_change_url():
    """admin_change_url should handle None and unregistered models"""

    user = UserFactory.create()

    assert admin_change_url(None) is None
    assert admin_change_url(user) == reverse("admin:users_user_change", args=[user.pk])
    # UserB2BContract isn't registered in the admin
    contract = ContractPageFactory.create()
    attachment = UserB2BContract.objects.create(user=user, contract_page=contract)
    assert admin_change_url(attachment) is None


def test_debug_view_renders(admin_client):
    """The debug view should render each section for a user with data"""

    user = UserFactory.create()
    run_enrollment = CourseRunEnrollmentFactory.create(user=user, active=False)
    run_cert = CourseRunCertificateFactory.create(
        user=user, course_run=run_enrollment.run
    )
    program_enrollment = ProgramEnrollmentFactory.create(user=user)
    program_cert = ProgramCertificateFactory.create(
        user=user, program=program_enrollment.program, is_revoked=True
    )
    membership = UserOrganizationFactory.create(user=user)
    contract = ContractPageFactory.create(organization=membership.organization)
    UserB2BContract.objects.create(
        user=user, contract_page=contract, consented_to_data_sharing=True
    )
    order = OrderFactory.create(purchaser=user, reference_number="mitxonline-1")
    _add_line(order)
    flexible_price = FlexiblePriceFactory.create(
        user=user, status=FlexiblePriceStatus.APPROVED
    )

    resp = admin_client.get(_debug_url(user))

    assert resp.status_code == 200
    content = resp.content.decode()
    assert user.email in content
    assert run_enrollment.run.courseware_id in content
    assert str(run_cert.uuid) in content
    assert program_enrollment.program.readable_id in content
    assert str(program_cert.uuid) in content
    assert "(revoked)" in content
    assert membership.organization.name in content
    assert contract.name in content
    assert "mitxonline-1" in content
    assert reverse("admin:ecommerce_order_change", args=[order.pk]) in content
    assert (
        reverse("admin:flexiblepricing_flexibleprice_change", args=[flexible_price.pk])
        in content
    )


def test_debug_view_empty_user(admin_client):
    """The debug view should render for a user with no related data"""

    user = UserFactory.create(legal_address=None)

    resp = admin_client.get(_debug_url(user))

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "No legal address" in content
    assert "No program enrollments." in content
    assert "No course run enrollments." in content
    assert "No organizations or contracts." in content
    assert "No orders." in content
    assert "No financial assistance requests." in content


def test_debug_view_unknown_user(admin_client):
    """The debug view should 404 for a user that doesn't exist"""

    resp = admin_client.get(reverse("admin:users_user_debug", args=[0]))

    assert resp.status_code == 404


def test_debug_view_requires_staff(client, user):
    """Non-staff users should be redirected to the admin login"""

    client.force_login(user)

    resp = client.get(_debug_url(user))

    assert resp.status_code == 302


@pytest.mark.parametrize("grant_view_user", [False, True])
def test_debug_view_requires_superuser(client, grant_view_user):
    """Staff who aren't superusers should be denied, even with view_user"""

    staff = UserFactory.create(is_staff=True)
    if grant_view_user:
        staff.user_permissions.add(Permission.objects.get(codename="view_user"))
    client.force_login(staff)

    resp = client.get(_debug_url(staff))

    assert resp.status_code == 403


def test_debug_view_link_hidden_for_non_superusers(client, admin_client):
    """The debug view button should only be shown to superusers"""

    user = UserFactory.create()
    resp = admin_client.get(reverse("admin:users_user_change", args=[user.pk]))
    assert "debug_view_link" in resp.content.decode()

    staff = UserFactory.create(is_staff=True)
    staff.user_permissions.add(Permission.objects.get(codename="view_user"))
    client.force_login(staff)

    resp = client.get(reverse("admin:users_user_change", args=[staff.pk]))

    assert resp.status_code == 200
    assert "debug_view_link" not in resp.content.decode()


def test_debug_view_link_on_change_page(admin_client):
    """The user change page should link to the debug view"""

    user = UserFactory.create()

    resp = admin_client.get(
        reverse("admin:users_user_actions", args=[user.pk, "debug_view_link"])
    )

    assert resp.status_code == 302
    assert resp.url == _debug_url(user)


def test_b2b_grouping():
    """
    Contracts should be grouped by org, orgs without contracts should have an
    empty contract list, and contracts in orgs the user isn't in should be
    grouped under an org with no membership.
    """

    user = UserFactory.create()
    member_org = OrganizationPageFactory.create(name="A Member Org")
    empty_org = OrganizationPageFactory.create(name="B Empty Org")
    other_org = OrganizationPageFactory.create(name="C Other Org")
    UserOrganizationFactory.create(user=user, organization=member_org)
    UserOrganizationFactory.create(user=user, organization=empty_org)
    member_contracts = ContractPageFactory.create_batch(2, organization=member_org)
    other_contract = ContractPageFactory.create(organization=other_org)
    for contract in [*member_contracts, other_contract]:
        UserB2BContract.objects.create(user=user, contract_page=contract)

    groups = get_user_debug_context(user)["b2b_groups"]

    assert [group["organization"] for group in groups] == [
        member_org,
        empty_org,
        other_org,
    ]
    member_group, empty_group, other_group = groups
    assert member_group["membership"] is not None
    assert {item["contract"] for item in member_group["contracts"]} == set(
        member_contracts
    )
    assert empty_group["membership"] is not None
    assert empty_group["contracts"] == []
    assert other_group["membership"] is None
    assert [item["contract"] for item in other_group["contracts"]] == [other_contract]


@pytest.mark.parametrize(
    ("status", "expect_tier"),
    [
        (FlexiblePriceStatus.APPROVED, True),
        (FlexiblePriceStatus.AUTO_APPROVED, True),
        (FlexiblePriceStatus.PENDING_MANUAL_APPROVAL, False),
        (FlexiblePriceStatus.DENIED, False),
    ],
)
def test_flexible_price_tier_only_when_approved(status, expect_tier):
    """The approved tier should only be shown for approved requests"""

    flexible_price = FlexiblePriceFactory.create(status=status)

    [item] = get_user_debug_context(flexible_price.user)["flexible_prices"]

    assert item["tier"] == (flexible_price.tier if expect_tier else None)
    assert item["courseware"] == flexible_price.courseware_object


def test_orders_line_count():
    """Orders should include the count of items purchased"""

    order = OrderFactory.create()
    _add_line(order)
    _add_line(order)

    [item] = get_user_debug_context(order.purchaser)["orders"]

    assert item["order"].line_count == 2
